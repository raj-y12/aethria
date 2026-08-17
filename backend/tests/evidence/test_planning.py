"""Sub-project 4, Phase A: the deterministic evidence-plan gap computation."""

from evaluation_v2.models import (
    CriterionRule,
    DecisionSafetyPolicy,
    EvaluationPolicy,
    EvidenceEligibilityPolicy,
)
from evidence.planning import compute_missing_evidence


def _policy(**criteria_kwargs):
    criteria = criteria_kwargs.get("criteria") or [
        CriterionRule(criterion="market", claim_types=["tam", "growth_rate", "competition"], weight=0.6),
        CriterionRule(criterion="execution", claim_types=["traction", "team_execution"], weight=0.4),
    ]
    return EvaluationPolicy(
        policy_version_id="policy-v1",
        policy_hash="policy-hash-v1",
        rubric_version="rubric-v1",
        partner_rules_version="rules-v1",
        partner_rules_hash="rules-hash-v1",
        criteria=criteria,
        advance_threshold=7.2,
        pass_threshold=4.0,
        advance_comparison="greater_than_or_equal",
        pass_comparison="less_than",
        minimum_scored_weight=0.5,
        decision_safety=DecisionSafetyPolicy(
            evidence_eligibility=EvidenceEligibilityPolicy(
                allowed_assertion_classes=["externally_verified"],
                allowed_relationships=["supports", "partially_establishes"],
                require_verified_evidence=True,
                min_support_strength=0.5,
                min_source_quality=0.4,
                blocked_trust_classes=["model", "unknown"],
            ),
            critical_risk_claim_types=["critical_risk"],
            hard_exclusion_claim_types=["excluded_sector"],
            claim_confidence={
                "minimum_eligible": 0.5,
                "full_confidence_at": 0.8,
                "score_cap_below_full_confidence": 7.19,
                "recommendation_confidence_cap_below_full_confidence": 0.6,
                "zero_confidence_ineligible": True,
            },
            freshness={
                "max_age_days": 180,
                "expired_action": "ineligible",
                "undated_action": "ineligible",
                "future_dated_action": "ineligible",
                "stale_action": "cap",
                "stale_score_cap": 7.19,
                "stale_confidence_cap": 0.6,
            },
            source_quality={
                "full_confidence_at": 0.8,
                "score_cap_below_full_quality": 7.19,
                "recommendation_confidence_cap_below_full_quality": 0.65,
            },
        ),
        hard_exclusion_claim_types=["excluded_sector"],
    )


def test_fully_covered_policy_has_no_gaps():
    policy = _policy()
    current = {"tam", "traction"}

    missing, questions = compute_missing_evidence(policy, current)

    assert missing == []
    assert questions == []


def test_fully_uncovered_policy_reports_every_criterion():
    policy = _policy()

    missing, questions = compute_missing_evidence(policy, set())

    assert missing == ["market", "execution"]
    assert len(questions) == 2
    assert "tam, growth_rate, competition" in questions[0]


def test_a_criterion_is_covered_by_any_matching_claim_type_not_just_the_first():
    """evaluate_snapshot() itself checks claim_type membership with `in
    rule.claim_types` (any position) — the gap check must match that, or a
    plan would flag a criterion evaluate() already considers scored."""
    policy = _policy()
    current = {"competition"}  # third of three claim_types for "market"

    missing, _ = compute_missing_evidence(policy, current)

    assert "market" not in missing


def test_partial_coverage_only_reports_the_uncovered_criteria():
    policy = _policy()
    current = {"tam"}  # covers market only

    missing, questions = compute_missing_evidence(policy, current)

    assert missing == ["execution"]
    assert len(questions) == 1
