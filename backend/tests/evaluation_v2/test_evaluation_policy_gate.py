from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from evaluation_v2.policy import evaluation_policy_from_compiled


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


def _decision_safety():
    return {
        "evidence_eligibility": {
            "allowed_assertion_classes": ["externally_verified", "operator_asserted"],
            "allowed_relationships": ["supports", "partially_establishes"],
            "require_verified_evidence": True,
            "min_support_strength": 0.5,
            "min_source_quality": 0.4,
            "blocked_trust_classes": ["model", "unknown"],
        },
        "critical_risk_claim_types": ["critical_risk"],
        "hard_exclusion_claim_types": ["mandate_exclusion"],
    }


def test_compiled_published_policy_maps_to_evidence_evaluation_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules={
            "version": "rules-v2",
            "score_thresholds": {"min_avg_strong_yes": 8, "min_avg_pass": 5.5},
            "decision_safety": _decision_safety(),
        },
    )

    assert policy.policy_version_id == "policy-live"
    assert policy.policy_hash == "hash-live"
    assert policy.partner_rules_version == "rules-v2"
    assert policy.advance_threshold == 8
    assert policy.pass_threshold == 5.5
    assert sum(item.weight for item in policy.criteria) == pytest.approx(1)
    market = next(item for item in policy.criteria if item.criterion == "market")
    assert {"market", "market_quality", "tam", "urgency"}.issubset(market.claim_types)


def test_compiled_policy_carries_versioned_decision_safety_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules={
            "version": "2.0",
            "score_thresholds": {"min_avg_strong_yes": 8, "min_avg_pass": 5.5},
            "decision_safety": {
                "evidence_eligibility": {
                    "allowed_assertion_classes": ["externally_verified", "operator_asserted"],
                    "allowed_relationships": ["supports", "partially_establishes"],
                    "require_verified_evidence": True,
                    "min_support_strength": 0.5,
                    "min_source_quality": 0.4,
                    "blocked_trust_classes": ["model", "unknown"],
                },
                "critical_risk_claim_types": ["critical_risk"],
                "hard_exclusion_claim_types": ["mandate_exclusion"],
            },
        },
    )

    assert policy.decision_safety.evidence_eligibility.min_support_strength == 0.5
    assert policy.decision_safety.critical_risk_claim_types == ["critical_risk"]
    assert policy.hard_exclusion_claim_types == ["mandate_exclusion"]


def test_missing_decision_safety_config_fails_closed():
    with pytest.raises(ValueError, match="decision_safety"):
        evaluation_policy_from_compiled(
            _compiled_policy(), partner_rules={"version": "2.0"}
        )


@pytest.mark.asyncio
async def test_evaluate_endpoint_uses_active_thesis_and_published_policy(monkeypatch):
    import routers.evaluations as route

    thesis = SimpleNamespace(version_id="thesis-live")
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules={"version": "rules-v2", "decision_safety": _decision_safety()},
    )

    class Repository:
        async def evaluate(self, **kwargs):
            assert kwargs["thesis_version_id"] == "thesis-live"
            assert kwargs["policy"] == policy
            return {"evaluation_id": "evaluation-1"}

        async def get_current(self, **kwargs):
            return {
                "evaluation": {"evaluation_id": "evaluation-1"},
                "criteria": [],
                "recommendation": {"recommended_state": "monitor"},
            }

    monkeypatch.setattr(route, "get_service_client", lambda: object())
    monkeypatch.setattr(route, "get_active_thesis", lambda client, user_id: thesis)
    monkeypatch.setattr(route, "load_published_policy", lambda user_id: _compiled_policy())
    monkeypatch.setattr(
        route,
        "get_partner_rules",
        lambda: {"version": "rules-v2", "decision_safety": _decision_safety()},
    )
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=Repository())),
    )

    result = await route.evaluate_opportunity(request, "opportunity-1")

    assert result == {
        "evaluation": {"evaluation_id": "evaluation-1"},
        "criteria": [],
        "recommendation": {"recommended_state": "monitor"},
    }


@pytest.mark.asyncio
async def test_evaluate_endpoint_fails_closed_when_thesis_is_missing(monkeypatch):
    import routers.evaluations as route

    class Repository:
        async def evaluate(self, **kwargs):
            raise AssertionError("repository must not run without a thesis")

    monkeypatch.setattr(route, "get_service_client", lambda: object())
    monkeypatch.setattr(route, "get_active_thesis", lambda client, user_id: None)
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=Repository())),
    )

    with pytest.raises(HTTPException) as exc:
        await route.evaluate_opportunity(request, "opportunity-1")

    assert exc.value.status_code == 409
    assert exc.value.detail == "An active fund thesis is required before evaluation"
