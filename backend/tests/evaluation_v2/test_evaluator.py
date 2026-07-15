from evaluation_v2.models import CriterionRule, EvaluationPolicy, RecommendationState
from evaluation_v2.service import evaluate_snapshot, snapshot_claims


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
    )


def test_same_snapshot_and_policy_produce_same_deterministic_result():
    snapshot, digest = snapshot_claims(_claims(), links=[])
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


def test_snapshot_hash_depends_on_values_not_future_live_status():
    original, original_hash = snapshot_claims(_claims(), links=[])
    changed = _claims()
    changed[0]["status"] = "contradicted"
    _, changed_hash = snapshot_claims(changed, links=[])

    assert original[0]["status_at_snapshot"] == "current"
    assert original_hash != changed_hash


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
    policy = _policy().model_copy(update={"hard_exclusion_claim_types": ["excluded_sector"]})
    snapshot, _ = snapshot_claims(claims, links=[])

    result = evaluate_snapshot(snapshot, policy)

    assert result.recommendation.state is RecommendationState.PASS
    assert result.recommendation.human_review_required is True
    assert "excluded_sector" in result.recommendation.mandate_conflicts
