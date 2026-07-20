import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from evaluation_v2.partner_rules import partner_rules_document
from fund_thesis import FundThesisMissingError
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.scoring.policy_store import PolicyNotPublishedError


def _compiled_policy():
    compiled = compile_policy_from_fund_config(
        {
            "scoringWeights": [
                {"key": "market", "weight": 60},
                {"key": "execution", "weight": 40},
            ],
        },
        require_publish_ready=True,
    )
    compiled["policy_version_id"] = "policy-live"
    return compiled


def _partner_rules():
    path = (
        Path(__file__).resolve().parents[3]
        / "resources/config/partner_rules/v3.json"
    )
    rules = json.loads(path.read_text())
    rules["version"] = "rules-v3"
    return rules


@pytest.mark.asyncio
async def test_resolves_exact_active_thesis_and_legacy_published_policy():
    calls = []

    async def load_thesis(user_id):
        calls.append(("thesis", user_id))
        return SimpleNamespace(version_id="thesis-live")

    async def load_policy(user_id):
        calls.append(("policy", user_id))
        return _compiled_policy()

    prerequisites = await load_evaluation_prerequisites(
        user_id=" user-a ",
        fund_intelligence_repository=None,
        load_thesis=load_thesis,
        load_policy=load_policy,
        load_partner_rules=_partner_rules,
    )

    assert calls == [("thesis", "user-a"), ("policy", "user-a")]
    assert prerequisites.thesis_version_id == "thesis-live"
    assert prerequisites.policy.policy_version_id == "policy-live"
    assert prerequisites.policy.policy_hash == _compiled_policy()["policy_hash"]
    assert prerequisites.policy.partner_rules_version == "rules-v3"


@pytest.mark.asyncio
async def test_prerequisites_retain_exact_tenant_bound_execution_inputs():
    thesis_context = {
        "thesis_id": "thesis-a",
        "version_id": "thesis-live",
        "version_number": 7,
        "raw_text": "Exact published mandate",
        "parsed_json": {"sectors": ["Infrastructure"]},
        "embedding": [],
        "embedding_model": "none",
        "alignment_mode": "rule_based",
    }
    thesis = SimpleNamespace(
        version_id="thesis-live",
        as_engine_context=lambda: thesis_context,
    )
    compiled = _compiled_policy()
    rules = _partner_rules()
    prerequisites = await load_evaluation_prerequisites(
        user_id=" user-a ",
        fund_intelligence_repository=None,
        load_thesis=lambda _user_id: thesis,
        load_policy=lambda _user_id: compiled,
        load_partner_rules=lambda: rules,
        load_fund_config=lambda _user_id: (_ for _ in ()).throw(
            AssertionError("published decisions must not reload a mutable draft")
        ),
    )

    assert prerequisites.user_id == "user-a"
    assert prerequisites.thesis_version_id == "thesis-live"
    assert prerequisites.thesis_context == thesis_context
    assert prerequisites.compiled_scoring_policy == compiled
    assert partner_rules_document(prerequisites.partner_rules) == rules
    assert prerequisites.fund_config == compiled["decision_inputs"]
    prerequisites.require_tenant(" user-a ", context="test handoff")
    with pytest.raises(RuntimeError, match="tenant"):
        prerequisites.require_tenant("user-b", context="test handoff")


@pytest.mark.asyncio
async def test_governed_policy_uses_exact_hash_bound_version_without_legacy_fallback():
    compiled = compile_policy_from_fund_config({}, require_publish_ready=True)

    class Repository:
        async def get_active_published_policy(self, *, user_id):
            assert user_id == "user-a"
            return {
                "governed_policy_version_id": "governed-policy-live",
                "policy_hash": compiled["policy_hash"],
                "policy_patch": {},
            }

    def legacy_policy(_user_id):
        raise AssertionError("legacy policy must not replace a governed policy")

    prerequisites = await load_evaluation_prerequisites(
        user_id="user-a",
        fund_intelligence_repository=Repository(),
        load_thesis=lambda _user_id: SimpleNamespace(version_id="thesis-live"),
        load_policy=legacy_policy,
        load_partner_rules=_partner_rules,
    )

    assert prerequisites.thesis_version_id == "thesis-live"
    assert prerequisites.policy.policy_version_id == "governed-policy-live"
    assert prerequisites.policy.policy_hash == compiled["policy_hash"]


@pytest.mark.asyncio
async def test_governed_not_found_uses_legacy_published_policy():
    calls = []

    class Repository:
        async def get_active_published_policy(self, *, user_id):
            assert user_id == "user-a"
            raise LookupError("no governed policy for tenant")

    def legacy_policy(user_id):
        calls.append(user_id)
        return _compiled_policy()

    prerequisites = await load_evaluation_prerequisites(
        user_id="user-a",
        fund_intelligence_repository=Repository(),
        load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
        load_policy=legacy_policy,
        load_partner_rules=_partner_rules,
    )

    assert calls == ["user-a"]
    assert prerequisites.thesis_version_id == "thesis-live"
    assert prerequisites.policy.policy_version_id == "policy-live"
    assert prerequisites.policy.policy_hash == _compiled_policy()["policy_hash"]


@pytest.mark.asyncio
async def test_production_legacy_loader_binds_exact_published_fund_config(monkeypatch):
    import evaluation_v2.prerequisites as prerequisites_module

    fund_config = {
        "activePolicyVersionId": "policy-live",
        "publishedPolicyHash": "pending",
        "scoringWeights": [
            {"key": "market", "weight": 70},
            {"key": "execution", "weight": 30},
        ],
        "scoreBands": [
            {"id": "pass", "min": 0, "max": 59, "label": "Pass"},
            {"id": "invest", "min": 60, "max": 100, "label": "Invest"},
        ],
    }
    compiled = compile_policy_from_fund_config(fund_config, require_publish_ready=True)
    compiled["policy_version_id"] = "policy-live"
    fund_config["publishedPolicyHash"] = compiled["policy_hash"]
    settings = {"fund_config": fund_config, "agent_config": {"scouts_enabled": True}}
    calls = []

    def load_settings(user_id, *, use_cache=False):
        calls.append(("settings", user_id, use_cache))
        return settings

    def load_published_policy(user_id, *, settings):
        calls.append(("policy", user_id, settings))
        return compiled

    monkeypatch.setattr(prerequisites_module, "load_settings", load_settings)
    monkeypatch.setattr(
        prerequisites_module, "load_published_policy", load_published_policy
    )

    prerequisites = await load_evaluation_prerequisites(
        user_id="user-a",
        fund_intelligence_repository=None,
        load_thesis=lambda _: SimpleNamespace(
            version_id="thesis-live",
            as_engine_context=lambda: {"version_id": "thesis-live"},
        ),
        load_partner_rules=_partner_rules,
    )

    assert calls == [
        ("settings", "user-a", False),
        ("policy", "user-a", settings),
    ]
    assert "decision_inputs" in compiled
    assert prerequisites.fund_config == compiled["decision_inputs"]
    assert prerequisites.compiled_scoring_policy is compiled


@pytest.mark.asyncio
async def test_published_bundle_isolated_from_current_draft_mutation():
    published = compile_policy_from_fund_config(
        {
            "thresholds": {
                "autoPass": 39,
                "monitor": 59,
                "escalation": 75,
                "partnerReview": 60,
            },
            "scoreBands": [
                {"id": "pass", "min": 0, "max": 59, "label": "Pass"},
                {"id": "invest", "min": 80, "max": 100, "label": "Invest"},
            ],
        },
        require_publish_ready=True,
    )
    published["policy_version_id"] = "policy-live"
    draft_loader_calls = []

    prerequisites = await load_evaluation_prerequisites(
        user_id="user-a",
        fund_intelligence_repository=None,
        load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
        load_policy=lambda _: published,
        load_partner_rules=_partner_rules,
        load_fund_config=lambda _: draft_loader_calls.append("called") or {
            "thresholds": {"partnerReview": 99}
        },
    )

    assert draft_loader_calls == []
    assert prerequisites.fund_config == published["decision_inputs"]


@pytest.mark.asyncio
async def test_missing_thesis_has_operator_recovery():
    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=None,
            load_thesis=lambda _: None,
            load_policy=lambda _: _compiled_policy(),
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "thesis_required"
    assert "Settings" in exc.value.recovery_action


@pytest.mark.asyncio
async def test_missing_thesis_error_is_operator_correctable_not_unavailable():
    def missing_thesis(_user_id):
        raise FundThesisMissingError("active thesis not found")

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=None,
            load_thesis=missing_thesis,
            load_policy=lambda _: _compiled_policy(),
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "thesis_required"
    assert "Settings" in exc.value.recovery_action


@pytest.mark.asyncio
async def test_missing_published_policy_has_operator_recovery():
    def missing_policy(_user_id):
        raise PolicyNotPublishedError("not published")

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=None,
            load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
            load_policy=missing_policy,
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "published_policy_required"
    assert "Publish" in exc.value.recovery_action


@pytest.mark.asyncio
async def test_governed_policy_hash_mismatch_is_unavailable_not_missing():
    class Repository:
        async def get_active_published_policy(self, *, user_id):
            return {
                "governed_policy_version_id": "governed-policy-live",
                "policy_hash": "not-the-compiled-hash",
                "policy_patch": {},
            }

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=Repository(),
            load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
            load_policy=lambda _: _compiled_policy(),
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "prerequisite_unavailable"
    assert "hash" in exc.value.detail
    assert "Republish" in exc.value.recovery_action


@pytest.mark.asyncio
async def test_transient_thesis_store_failure_is_not_mislabeled_as_missing():
    def unavailable_thesis(_user_id):
        raise RuntimeError("database timeout")

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=None,
            load_thesis=unavailable_thesis,
            load_policy=lambda _: _compiled_policy(),
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "prerequisite_unavailable"
    assert "thesis" in exc.value.detail
    assert "Retry" in exc.value.recovery_action


@pytest.mark.asyncio
async def test_transient_governed_policy_store_failure_does_not_fall_back_to_legacy():
    class Repository:
        async def get_active_published_policy(self, *, user_id):
            raise RuntimeError("database timeout")

    def legacy_policy(_user_id):
        raise AssertionError("transient governed failure must not look like no policy")

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=Repository(),
            load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
            load_policy=legacy_policy,
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "prerequisite_unavailable"
    assert "governed policy" in exc.value.detail


@pytest.mark.asyncio
async def test_none_governed_policy_response_is_unavailable_without_legacy_fallback():
    class Repository:
        async def get_active_published_policy(self, *, user_id):
            return None

    def legacy_policy(_user_id):
        raise AssertionError("malformed governed response must not trigger fallback")

    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=Repository(),
            load_thesis=lambda _: SimpleNamespace(version_id="thesis-live"),
            load_policy=legacy_policy,
            load_partner_rules=_partner_rules,
        )

    assert exc.value.code == "prerequisite_unavailable"
    assert "governed policy" in exc.value.detail
