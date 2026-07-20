from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    EvaluationPrerequisites,
)


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
        "claim_confidence": {
            "minimum_eligible": 0.5,
            "full_confidence_at": 0.8,
            "score_cap_below_full_confidence": 7.99,
            "recommendation_confidence_cap_below_full_confidence": 0.6,
            "zero_confidence_ineligible": True,
        },
        "freshness": {
            "max_age_days": 180,
            "expired_action": "ineligible",
            "undated_action": "ineligible",
            "future_dated_action": "ineligible",
            "stale_action": "cap",
            "stale_score_cap": 7.99,
            "stale_confidence_cap": 0.6,
        },
        "source_quality": {
            "full_confidence_at": 0.8,
            "score_cap_below_full_quality": 7.99,
            "recommendation_confidence_cap_below_full_quality": 0.65,
        },
    }


def _partner_rules():
    return {
        "version": "rules-v3",
        "score_thresholds": {
            "min_avg_strong_yes": 8,
            "min_avg_pass": 5.5,
            "min_avg_medium_maybe": 7,
            "min_avg_borderline_low": 5.5,
            "max_avg_borderline_high": 7,
            "grey_zone_min": 6.5,
            "grey_zone_max": 7.5,
            "boundary_semantics": {
                "advance": "greater_than_or_equal",
                "pass": "less_than",
            },
            "minimum_scored_weight": 0.5,
        },
        "decision_safety": _decision_safety(),
        "critical_risk_keywords": ["regulatory ban"],
        "red_flag_keywords": ["missing"],
        "missing_qualitative_keywords": ["[missing]"],
        "assumption_risk_keywords": ["unvalidated assumption"],
        "next_actions": {
            "critical_risks": "Pass - critical risk",
            "low_scores": "Pass - low scores",
            "default_no": "Pass - below criteria",
            "request_cap_table": "Request cap table",
            "request_cap_table_and_review": "Request cap table and review",
            "monitor": "Monitor",
            "human_review_monitor": "Human review",
            "human_review_contradictions": "Human review contradictions",
        },
        "quality_labels": {
            "STRONG": "Investment-grade",
            "MEDIUM": "Promising",
            "WEAK": "Unproven",
        },
        "verdict_rules": {"WEAK": {}, "MEDIUM": {}, "STRONG": {}},
        "contradictory_scores": {
            "min_gap": 4,
            "high_threshold": 8,
            "low_threshold": 4,
        },
        "llm_fallback_triggers": {"grey_zone_deep_dive": True},
    }


def test_compiled_published_policy_maps_to_evidence_evaluation_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules=_partner_rules(),
    )

    assert policy.policy_version_id == "policy-live"
    assert policy.policy_hash == "hash-live"
    assert policy.partner_rules_version == "rules-v3"
    assert policy.advance_threshold == 8
    assert policy.pass_threshold == 5.5
    assert sum(item.weight for item in policy.criteria) == pytest.approx(1)
    market = next(item for item in policy.criteria if item.criterion == "market")
    assert {"market", "market_quality", "tam", "urgency"}.issubset(market.claim_types)


def test_compiled_policy_carries_versioned_decision_safety_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules=_partner_rules(),
    )

    assert policy.decision_safety.evidence_eligibility.min_support_strength == 0.5
    assert policy.decision_safety.critical_risk_claim_types == ["critical_risk"]
    assert policy.hard_exclusion_claim_types == ["mandate_exclusion"]


def test_missing_decision_safety_config_fails_closed():
    rules = _partner_rules()
    del rules["decision_safety"]
    with pytest.raises(ValueError, match="decision_safety"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    "path",
    [
        ("version",),
        ("score_thresholds", "min_avg_pass"),
        ("score_thresholds", "boundary_semantics"),
        ("decision_safety", "critical_risk_claim_types"),
        ("decision_safety", "hard_exclusion_claim_types"),
        ("critical_risk_keywords",),
        ("red_flag_keywords",),
        ("missing_qualitative_keywords",),
        ("assumption_risk_keywords",),
        ("next_actions",),
        ("decision_safety", "claim_confidence"),
        ("decision_safety", "freshness"),
        ("decision_safety", "source_quality"),
    ],
)
def test_partial_partner_rules_fail_closed(path):
    rules = deepcopy(_partner_rules())
    parent = rules
    for segment in path[:-1]:
        parent = parent[segment]
    del parent[path[-1]]

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("claim_confidence", "score_cap_below_full_confidence"),
        ("freshness", "stale_score_cap"),
        ("source_quality", "score_cap_below_full_quality"),
    ],
)
def test_weak_evidence_score_caps_must_remain_below_advance_threshold(
    section, field
):
    rules = _partner_rules()
    rules["decision_safety"][section][field] = rules["score_thresholds"][
        "min_avg_strong_yes"
    ]

    with pytest.raises(ValueError, match="score cap"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_avg_medium_maybe", -0.1),
        ("grey_zone_max", 10.1),
        ("minimum_scored_weight", 0),
        ("minimum_scored_weight", 1.1),
    ],
)
def test_partner_threshold_ranges_fail_closed(field, value):
    rules = _partner_rules()
    rules["score_thresholds"][field] = value

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    ("lower", "upper"),
    [
        ("min_avg_pass", "min_avg_medium_maybe"),
        ("min_avg_medium_maybe", "min_avg_strong_yes"),
        ("min_avg_borderline_low", "max_avg_borderline_high"),
        ("grey_zone_min", "grey_zone_max"),
    ],
)
def test_partner_threshold_ordering_fails_closed(lower, upper):
    rules = _partner_rules()
    rules["score_thresholds"][lower] = 8
    rules["score_thresholds"][upper] = 7

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.asyncio
async def test_evaluate_endpoint_uses_active_thesis_and_published_policy(monkeypatch):
    import routers.evaluations as route

    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules=_partner_rules(),
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

    async def load(**kwargs):
        assert kwargs["user_id"] == "user-a"
        return EvaluationPrerequisites(
            user_id="user-a",
            thesis_context={"version_id": "thesis-live"},
            thesis_version_id="thesis-live",
            compiled_scoring_policy=_compiled_policy(),
            partner_rules={"version": "rules-v2"},
            fund_config={},
            policy=policy,
        )

    monkeypatch.setattr(route, "load_evaluation_prerequisites", load)
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
@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        ("thesis_required", 409),
        ("published_policy_required", 409),
        ("prerequisite_unavailable", 503),
    ],
)
async def test_evaluate_endpoint_translates_prerequisite_failures(
    monkeypatch, code, expected_status
):
    import routers.evaluations as route

    class Repository:
        async def evaluate(self, **kwargs):
            raise AssertionError("repository must not run without a thesis")

    async def load(**kwargs):
        raise EvaluationPrerequisiteError(
            code=code,
            detail=f"{code} detail",
            recovery_action="Fix the prerequisite in Settings.",
        )

    monkeypatch.setattr(route, "load_evaluation_prerequisites", load)
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=Repository())),
    )

    with pytest.raises(HTTPException) as exc:
        await route.evaluate_opportunity(request, "opportunity-1")

    assert exc.value.status_code == expected_status
    assert exc.value.detail == f"{code} detail"
