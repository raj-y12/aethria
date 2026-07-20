from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.scoring.policy_store import PolicyNotPublishedError


def _compiled_policy():
    return {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {
            "market": {
                "weight": 60,
                "criteria": [
                    {
                        "id": "market_quality",
                        "source_components": ["tam", "urgency"],
                    }
                ],
            },
            "execution": {
                "weight": 40,
                "criteria": [
                    {
                        "id": "founder_execution",
                        "source_components": ["traction", "operational_velocity"],
                    }
                ],
            },
        },
    }


def _partner_rules():
    return {
        "version": "rules-v2",
        "decision_safety": {
            "evidence_eligibility": {
                "allowed_assertion_classes": [
                    "externally_verified",
                    "operator_asserted",
                ],
                "allowed_relationships": ["supports", "partially_establishes"],
                "require_verified_evidence": True,
                "min_support_strength": 0.5,
                "min_source_quality": 0.4,
                "blocked_trust_classes": ["model", "unknown"],
            },
            "critical_risk_claim_types": ["critical_risk"],
            "hard_exclusion_claim_types": ["mandate_exclusion"],
        },
    }


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
    assert prerequisites.policy.policy_hash == "hash-live"
    assert prerequisites.policy.partner_rules_version == "rules-v2"


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
