from datetime import datetime, timezone

import pytest

from evaluation_v2.models import (
    CriterionRule,
    DecisionSafetyPolicy,
    EvaluationPolicy,
    EvidenceEligibilityPolicy,
    RecommendationState,
)
from evaluation_v2.service import evaluate_snapshot, snapshot_claims


EVALUATION_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _claims():
    return [
        {
            "claim_id": "claim-market",
            "claim_type": "market",
            "normalized_value": {"criterion_score": 8.0},
            "display_text": "Market growth is supported by two independent sources.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        },
        {
            "claim_id": "claim-execution",
            "claim_type": "execution",
            "normalized_value": {"criterion_score": 7.0},
            "display_text": "Three shipped product iterations are documented.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.8,
        },
    ]


def _verified_link(claim_id, **overrides):
    link = {
        "claim_id": claim_id,
        "evidence_item_id": f"evidence-{claim_id}",
        "relationship": "supports",
        "support_strength": 0.9,
        "verification_state": "verified",
        "source_quality": 0.8,
        "trust_class": "independent",
        "untrusted_input": False,
        "prompt_injection_detected": False,
        "evidence_effective_at": "2026-07-01T00:00:00+00:00",
        "evidence_expires_at": "2026-08-01T00:00:00+00:00",
        "artifact_effective_at": "2026-07-01T00:00:00+00:00",
        "retrieved_at": "2026-07-01T01:00:00+00:00",
    }
    link.update(overrides)
    return link


def _policy():
    return EvaluationPolicy(
        policy_version_id="policy-v1",
        policy_hash="policy-hash-v1",
        rubric_version="rubric-v1",
        partner_rules_version="rules-v1",
        partner_rules_hash="rules-hash-v1",
        criteria=[
            CriterionRule(criterion="market", claim_types=["market"], weight=0.6),
            CriterionRule(criterion="execution", claim_types=["execution"], weight=0.4),
        ],
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
            )
            ,
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


def test_same_snapshot_and_policy_produce_same_deterministic_result():
    snapshot, digest = snapshot_claims(
        _claims(),
        links=[_verified_link("claim-market"), _verified_link("claim-execution")],
    )
    first = evaluate_snapshot(snapshot, _policy())
    second = evaluate_snapshot(snapshot, _policy())

    assert first == second
    assert first.recommendation.state is RecommendationState.ADVANCE
    assert first.snapshot_hash == digest


def test_missing_evidence_is_unscored_not_converted_to_zero():
    snapshot, _ = snapshot_claims(_claims()[:1], links=[])
    result = evaluate_snapshot(snapshot, _policy())

    execution = next(item for item in result.criteria if item.criterion == "execution")
    assert execution.score is None
    assert execution.evidence_sufficiency == "insufficient"
    assert "execution" in result.recommendation.missing_information


def test_required_unscored_criterion_forces_insufficient_evidence_despite_high_average():
    claims = [_claims()[0]]
    links = [_verified_link("claim-market")]
    snapshot, _ = snapshot_claims(claims, links)

    result = evaluate_snapshot(snapshot, _policy())

    assert result.criteria[0].score == 8.0
    assert next(
        criterion
        for criterion in result.criteria
        if criterion.criterion == "execution"
    ).score is None
    assert result.recommendation.state is RecommendationState.INSUFFICIENT_EVIDENCE
    assert "execution" in result.recommendation.missing_information
    assert "Resolve missing evidence: execution" in result.recommendation.change_conditions
    assert result.recommendation.human_review_required is True


def test_optional_unscored_criterion_never_receives_numeric_placeholder():
    policy = _policy().model_copy(deep=True)
    policy.criteria[1].required = False
    snapshot, _ = snapshot_claims([_claims()[0]], [_verified_link("claim-market")])

    result = evaluate_snapshot(snapshot, policy)

    execution = next(
        criterion
        for criterion in result.criteria
        if criterion.criterion == "execution"
    )
    assert execution.score is None


def test_all_unscored_criteria_have_zero_confidence_and_insufficient_evidence():
    snapshot, _ = snapshot_claims(_claims(), links=[])

    result = evaluate_snapshot(snapshot, _policy())

    assert all(criterion.score is None for criterion in result.criteria)
    assert result.recommendation.confidence == 0
    assert result.recommendation.state is RecommendationState.INSUFFICIENT_EVIDENCE


def test_snapshot_hash_depends_on_values_not_future_live_status():
    original, original_hash = snapshot_claims(_claims(), links=[])
    changed = _claims()
    changed[0]["status"] = "contradicted"
    _, changed_hash = snapshot_claims(changed, links=[])

    assert original[0]["status_at_snapshot"] == "current"
    assert original_hash != changed_hash


def test_snapshot_hash_changes_when_grounding_metadata_changes():
    links = [_verified_link("claim-market")]
    _, original_hash = snapshot_claims(_claims(), links)
    changed_links = [_verified_link("claim-market", source_quality=0.2)]
    _, changed_hash = snapshot_claims(_claims(), changed_links)

    assert original_hash != changed_hash


def test_ungrounded_external_claim_is_unscored_and_cannot_advance():
    snapshot, _ = snapshot_claims(_claims(), links=[])

    result = evaluate_snapshot(snapshot, _policy())

    assert all(item.score is None for item in result.criteria)
    assert result.recommendation.state is RecommendationState.INSUFFICIENT_EVIDENCE


def test_model_inferred_claim_cannot_establish_decisive_criterion():
    claims = _claims()
    claims[0]["assertion_class"] = "model_inferred"
    links = [_verified_link("claim-market")]
    snapshot, _ = snapshot_claims(claims, links)

    market = next(
        item
        for item in evaluate_snapshot(snapshot, _policy()).criteria
        if item.criterion == "market"
    )

    assert market.score is None
    assert "assertion_class_not_allowed" in market.quality_flags


def test_verified_supported_claim_is_score_eligible():
    links = [_verified_link("claim-market"), _verified_link("claim-execution")]
    snapshot, _ = snapshot_claims(_claims(), links)

    result = evaluate_snapshot(snapshot, _policy())

    assert result.recommendation.state is RecommendationState.ADVANCE


def test_attributed_operator_claim_is_score_eligible_when_policy_allows_it():
    claims = _claims()
    for claim in claims:
        claim["assertion_class"] = "operator_asserted"
        claim["operator_attribution"] = "investment-committee-review-2026-07-20"
    policy = _policy()
    policy.decision_safety.evidence_eligibility.allowed_assertion_classes.append(
        "operator_asserted"
    )
    snapshot, _ = snapshot_claims(claims, links=[])

    result = evaluate_snapshot(snapshot, policy)

    assert result.recommendation.state is RecommendationState.ADVANCE


def test_unattributed_operator_claim_is_unscored():
    claims = _claims()
    claims[0]["assertion_class"] = "operator_asserted"
    policy = _policy()
    policy.decision_safety.evidence_eligibility.allowed_assertion_classes.append(
        "operator_asserted"
    )
    snapshot, _ = snapshot_claims(claims, links=[])

    market = next(
        item
        for item in evaluate_snapshot(snapshot, policy).criteria
        if item.criterion == "market"
    )

    assert market.score is None
    assert "no_eligible_supporting_evidence" in market.quality_flags


def test_untrusted_input_is_provenance_not_an_eligibility_filter():
    links = [
        _verified_link("claim-market", untrusted_input=True),
        _verified_link("claim-execution", untrusted_input=True),
    ]
    snapshot, _ = snapshot_claims(_claims(), links)

    result = evaluate_snapshot(snapshot, _policy())

    assert result.recommendation.state is RecommendationState.ADVANCE


def test_hard_exclusion_is_deterministic_pass_with_driver():
    claims = _claims() + [
        {
            "claim_id": "claim-exclusion",
            "claim_type": "excluded_sector",
            "normalized_value": {"value": True},
            "display_text": "Company operates in an excluded sector.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 1,
        }
    ]
    policy = _policy()
    policy.decision_safety.hard_exclusion_claim_types = ["excluded_sector"]
    snapshot, _ = snapshot_claims(claims, links=[_verified_link("claim-exclusion")])

    result = evaluate_snapshot(snapshot, policy)

    assert result.recommendation.state is RecommendationState.PASS
    assert result.recommendation.human_review_required is True
    assert "excluded_sector" in result.recommendation.mandate_conflicts


def test_grounded_critical_risk_forces_pass_despite_high_supported_scores():
    claims = _claims() + [
        {
            "claim_id": "claim-critical-risk",
            "claim_type": "critical_risk",
            "normalized_value": {"value": True},
            "display_text": "Regulatory ban risk in primary market.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 1,
        }
    ]
    for claim in claims[:2]:
        claim["normalized_value"] = {"criterion_score": 9.0}
    policy = _policy()
    policy.decision_safety.critical_risk_claim_types = ["critical_risk"]
    snapshot, _ = snapshot_claims(
        claims,
        links=[
            _verified_link("claim-market"),
            _verified_link("claim-execution"),
            _verified_link("claim-critical-risk"),
        ],
    )

    result = evaluate_snapshot(snapshot, policy)

    assert result.recommendation.state is RecommendationState.PASS
    assert result.recommendation.human_review_required is True
    assert "Regulatory ban risk in primary market." in result.recommendation.principal_risks


def test_ungrounded_critical_risk_is_uncertainty_not_an_automatic_pass():
    claims = _claims() + [
        {
            "claim_id": "claim-critical-risk",
            "claim_type": "critical_risk",
            "normalized_value": {"value": True},
            "display_text": "Unverified regulatory ban risk in primary market.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 1,
        }
    ]
    for claim in claims[:2]:
        claim["normalized_value"] = {"criterion_score": 9.0}
    policy = _policy()
    policy.decision_safety.critical_risk_claim_types = ["critical_risk"]
    snapshot, _ = snapshot_claims(
        claims,
        links=[_verified_link("claim-market"), _verified_link("claim-execution")],
    )

    result = evaluate_snapshot(snapshot, policy)

    assert result.recommendation.state is RecommendationState.ADVANCE
    assert result.recommendation.human_review_required is True
    assert (
        "Unverified regulatory ban risk in primary market."
        in result.recommendation.missing_information
    )


@pytest.mark.parametrize(
    ("claim_confidence", "expected_state"),
    [
        (0.0, RecommendationState.INSUFFICIENT_EVIDENCE),
        (0.49, RecommendationState.INSUFFICIENT_EVIDENCE),
        (0.5, RecommendationState.MONITOR),
        (0.9, RecommendationState.ADVANCE),
    ],
    ids=["zero", "below-minimum", "minimum-boundary", "high"],
)
def test_claim_confidence_constrains_recommendation(claim_confidence, expected_state):
    claims = _claims()
    for claim in claims:
        claim["normalized_value"] = {"criterion_score": 9.0}
        claim["confidence"] = claim_confidence
    snapshot, _ = snapshot_claims(
        claims,
        [_verified_link("claim-market"), _verified_link("claim-execution")],
        evaluation_at=EVALUATION_AT,
    )

    result = evaluate_snapshot(snapshot, _policy(), evaluation_at=EVALUATION_AT)

    assert result.recommendation.state is expected_state
    if claim_confidence < 0.8:
        assert result.recommendation.confidence < 0.8


@pytest.mark.parametrize(
    "raw_value",
    ["false", "0", "no", 0, 1, [], {}, None],
)
def test_malformed_decisive_boolean_is_uncertainty_not_pass(raw_value):
    claims = _claims()
    for claim in claims:
        claim["normalized_value"] = {"criterion_score": 9.0}
    normalized = {} if raw_value is None else {"value": raw_value}
    claims.append(
        {
            "claim_id": "claim-risk",
            "claim_type": "critical_risk",
            "normalized_value": normalized,
            "display_text": "Malformed decisive risk value.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        }
    )
    snapshot, _ = snapshot_claims(
        claims,
        [
            _verified_link("claim-market"),
            _verified_link("claim-execution"),
            _verified_link("claim-risk"),
        ],
        evaluation_at=EVALUATION_AT,
    )

    result = evaluate_snapshot(snapshot, _policy(), evaluation_at=EVALUATION_AT)

    assert result.recommendation.state is RecommendationState.ADVANCE
    assert result.recommendation.human_review_required is True
    assert "Malformed decisive risk value." in result.recommendation.missing_information


@pytest.mark.parametrize(
    ("raw_value", "expected_state", "is_uncertain"),
    [
        (True, RecommendationState.PASS, False),
        (False, RecommendationState.ADVANCE, False),
    ],
)
def test_exact_decisive_booleans_have_deterministic_meaning(
    raw_value, expected_state, is_uncertain
):
    claims = _claims()
    for claim in claims:
        claim["normalized_value"] = {"criterion_score": 9.0}
    claims.append(
        {
            "claim_id": "claim-risk",
            "claim_type": "critical_risk",
            "normalized_value": {"value": raw_value},
            "display_text": "Exact decisive risk value.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        }
    )
    snapshot, _ = snapshot_claims(
        claims,
        [
            _verified_link("claim-market"),
            _verified_link("claim-execution"),
            _verified_link("claim-risk"),
        ],
        evaluation_at=EVALUATION_AT,
    )

    result = evaluate_snapshot(snapshot, _policy(), evaluation_at=EVALUATION_AT)

    assert result.recommendation.state is expected_state
    assert (
        "Exact decisive risk value." in result.recommendation.missing_information
    ) is is_uncertain


@pytest.mark.parametrize(
    ("link_overrides", "expected_state", "quality_flag"),
    [
        ({}, RecommendationState.ADVANCE, None),
        (
            {"evidence_expires_at": "2026-07-19T00:00:00+00:00"},
            RecommendationState.INSUFFICIENT_EVIDENCE,
            "evidence_expired",
        ),
        (
            {
                "evidence_effective_at": None,
                "evidence_expires_at": None,
                "artifact_effective_at": None,
                "retrieved_at": None,
            },
            RecommendationState.INSUFFICIENT_EVIDENCE,
            "evidence_undated",
        ),
        (
            {
                "evidence_effective_at": "2025-01-01T00:00:00+00:00",
                "evidence_expires_at": None,
                "artifact_effective_at": "2025-01-01T00:00:00+00:00",
                "retrieved_at": "2025-01-01T00:00:00+00:00",
            },
            RecommendationState.MONITOR,
            "evidence_stale",
        ),
        (
            {"source_quality": 0.5},
            RecommendationState.MONITOR,
            "source_quality_below_full",
        ),
    ],
    ids=["fresh", "expired", "undated", "stale", "low-quality"],
)
def test_freshness_and_source_quality_constrain_decisions(
    link_overrides, expected_state, quality_flag
):
    claims = _claims()
    for claim in claims:
        claim["normalized_value"] = {"criterion_score": 9.0}
    links = [
        _verified_link("claim-market", **link_overrides),
        _verified_link("claim-execution", **link_overrides),
    ]
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=EVALUATION_AT)

    result = evaluate_snapshot(snapshot, _policy(), evaluation_at=EVALUATION_AT)

    assert result.recommendation.state is expected_state
    if quality_flag:
        assert all(quality_flag in item.quality_flags for item in result.criteria)
    if expected_state is not RecommendationState.ADVANCE:
        assert result.recommendation.confidence < 0.8


def test_snapshot_hash_captures_freshness_inputs_and_evaluation_timestamp():
    links = [_verified_link("claim-market")]
    _, original = snapshot_claims(_claims(), links, evaluation_at=EVALUATION_AT)
    _, changed_date = snapshot_claims(
        _claims(),
        [_verified_link("claim-market", retrieved_at="2026-07-02T00:00:00+00:00")],
        evaluation_at=EVALUATION_AT,
    )
    _, changed_clock = snapshot_claims(
        _claims(),
        links,
        evaluation_at=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
    )

    assert original != changed_date
    assert original != changed_clock


@pytest.mark.parametrize(
    ("score", "expected_state"),
    [
        (3.99, RecommendationState.PASS),
        (4.0, RecommendationState.MONITOR),
        (4.01, RecommendationState.MONITOR),
        (7.19, RecommendationState.MONITOR),
        (7.2, RecommendationState.ADVANCE),
        (7.21, RecommendationState.ADVANCE),
    ],
)
def test_explicit_threshold_boundaries(score, expected_state):
    claims = _claims()
    for claim in claims:
        claim["normalized_value"] = {"criterion_score": score}
        claim["confidence"] = 0.9
    snapshot, _ = snapshot_claims(
        claims,
        [_verified_link("claim-market"), _verified_link("claim-execution")],
        evaluation_at=EVALUATION_AT,
    )

    result = evaluate_snapshot(snapshot, _policy(), evaluation_at=EVALUATION_AT)

    assert result.recommendation.state is expected_state
