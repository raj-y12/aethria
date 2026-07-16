import pytest

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


def test_publish_policy_deduplicates_same_hash(monkeypatch):
    import services.scoring.policy_store as store_mod

    settings = {"fund_config": _valid_fund_config()}
    versions = []
    saved = []

    monkeypatch.setattr(store_mod, "load_settings", lambda user_id, use_cache=True: dict(settings))
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: list(versions))

    def fake_append(table, record, id_field="id", user_id=""):
        versions.append(dict(record))
        return record["id"]

    def fake_save(next_settings, user_id):
        saved.append(next_settings)
        settings.clear()
        settings.update(next_settings)

    monkeypatch.setattr(store_mod, "list_append", fake_append)
    monkeypatch.setattr(store_mod, "save_settings", fake_save)

    first = publish_policy("user_1")
    second = publish_policy("user_1")

    assert first["policy_hash"] == second["policy_hash"]
    assert len(versions) == 1
    assert saved[-1]["fund_config"]["activePolicyVersionId"] == first["policy_version_id"]


def test_load_published_policy_fails_closed_without_an_active_published_version(monkeypatch):
    import services.scoring.policy_store as store_mod

    monkeypatch.setattr(store_mod, "load_settings", lambda user_id: {"fund_config": _valid_fund_config()})
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: [])

    with pytest.raises(PolicyNotPublishedError):
        load_published_policy("user_1")


def test_load_published_policy_returns_only_the_hash_bound_active_version(monkeypatch):
    import services.scoring.policy_store as store_mod

    published = {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {},
    }
    monkeypatch.setattr(
        store_mod,
        "load_settings",
        lambda user_id: {
            "fund_config": {
                "activePolicyVersionId": "policy-live",
                "publishedPolicyHash": "hash-live",
            }
        },
    )
    monkeypatch.setattr(store_mod, "list_get_all", lambda table, user_id: [published])

    assert load_published_policy("user_1") == published
