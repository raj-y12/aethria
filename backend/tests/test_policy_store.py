import pytest

from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.scoring.policy_store import (
    PolicyNotPublishedError,
    load_published_policy,
    publish_policy,
)


def _valid_fund_config():
    return {
        "rubric": [
            {
                "id": "market_conviction",
                "dimension": "market",
                "name": "Market conviction",
                "weight": 100,
                "examples": {
                    "score3": "Weak",
                    "score5": "Neutral",
                    "score7": "Good",
                    "score9": "Great",
                },
            }
        ]
    }


@pytest.mark.asyncio
async def test_publish_policy_deduplicates_same_hash(monkeypatch):
    import services.scoring.policy_store as store_mod

    settings = {"fund_config": _valid_fund_config()}
    versions = []
    saved = []

    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: list(versions))

    def fake_append(table, record, id_field="id", user_id=""):
        versions.append(dict(record))
        return record["id"]

    async def fake_save(next_settings, user_id, **_kwargs):
        saved.append(next_settings)
        settings.clear()
        settings.update(next_settings)

    monkeypatch.setattr(store_mod, "list_append", fake_append)
    monkeypatch.setattr(store_mod, "save_settings", fake_save)

    class Repository:
        pass

    first = await publish_policy(
        "user_1", settings=settings, settings_repository=Repository()
    )
    second = await publish_policy(
        "user_1", settings=settings, settings_repository=Repository()
    )

    assert first["policy_hash"] == second["policy_hash"]
    assert len(versions) == 1
    assert saved[-1]["fund_config"]["activePolicyVersionId"] == first["policy_version_id"]


def test_load_published_policy_fails_closed_without_an_active_published_version(monkeypatch):
    import services.scoring.policy_store as store_mod

    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: [])

    with pytest.raises(PolicyNotPublishedError):
        load_published_policy("user_1", settings={"fund_config": _valid_fund_config()})


def test_load_published_policy_rejects_old_partial_policy_record(monkeypatch):
    import services.scoring.policy_store as store_mod

    published = {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {},
    }
    settings = {
        "fund_config": {
                "activePolicyVersionId": "policy-live",
                "publishedPolicyHash": "hash-live",
            }
        }
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: [published])

    with pytest.raises(PolicyNotPublishedError, match="complete"):
        load_published_policy("user_1", settings=settings)


def test_load_published_policy_recomputes_complete_bundle_hash(monkeypatch):
    import services.scoring.policy_store as store_mod

    published = compile_policy_from_fund_config(_valid_fund_config())
    published["policy_version_id"] = "policy-live"
    decision_inputs = published.get("decision_inputs")
    assert isinstance(decision_inputs, dict)
    decision_inputs["thresholds"]["partnerReview"] = 99
    settings = {
        "fund_config": {
                "activePolicyVersionId": "policy-live",
                "publishedPolicyHash": published["policy_hash"],
            }
        }
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: [published])

    with pytest.raises(PolicyNotPublishedError, match="hash"):
        load_published_policy("user_1", settings=settings)


def test_load_published_policy_returns_the_normalized_validated_bundle(monkeypatch):
    import services.scoring.policy_store as store_mod

    published = compile_policy_from_fund_config(_valid_fund_config())
    published["policy_version_id"] = "policy-live"
    published["id"] = "policy-live"
    published["published_at"] = "2026-07-21T00:00:00+00:00"
    published["decision_inputs"]["thresholds"]["partnerReview"] = "60.0"
    settings = {
        "fund_config": {
                "activePolicyVersionId": "policy-live",
                "publishedPolicyHash": published["policy_hash"],
            }
        }
    monkeypatch.setattr(
        store_mod, "list_get_all", lambda table, user_id: [published]
    )

    loaded = load_published_policy("user_1", settings=settings)

    assert loaded["decision_inputs"]["thresholds"]["partnerReview"] == 60.0
    assert isinstance(
        loaded["decision_inputs"]["thresholds"]["partnerReview"], float
    )
    assert loaded["scoring_runtime_hash"] == published["scoring_runtime_hash"]
