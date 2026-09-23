"""Safety certification of the live Reviewer/validation/Partner path.

Partner is mocked to request ADVANCE so policy blocks cannot hide behind a
cautious model. Caps constrain assessments, not score-to-action thresholds.
Grounded exclusions take precedence over missing dimensions; advancement always
requires human review. These are existing live semantics, not policy changes.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pytest

from decisions.models import HumanRulingDecision
from decisions.service import classify_override
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.policy import evaluation_policy_from_compiled
from investment_analysis.models import ReviewerDraft, PartnerDraft
from investment_analysis.service import analyze
from pipeline_contracts.models import Lineage, Identity
from utils.partner_codes import legacy_ruling_from_institutional


@dataclass(frozen=True)
class SafetyCase:
    name: str
    kind: Literal["evaluation", "override", "projection"]
    expected_state: str | None = None
    expected_human_review: bool | None = None
    expected_missing_information: str | None = None
    expected_override: str | None = None
    expected_projection: dict[str, str | None] | None = None


CASES = [
    SafetyCase(
        "ungrounded_high_score", "evaluation", expected_state="insufficient_evidence"
    ),
    SafetyCase(
        "model_inferred_high_score", "evaluation", expected_state="insufficient_evidence"
    ),
    SafetyCase(
        "required_dimension_missing",
        "evaluation",
        expected_state="insufficient_evidence",
    ),
    SafetyCase(
        "required_dimension_missing_with_grounded_critical_risk",
        "evaluation",
        expected_state="pass",
        expected_human_review=True,
    ),
    SafetyCase(
        "contradicted_scored_criterion",
        "evaluation",
        expected_state="insufficient_evidence",
        expected_human_review=True,
    ),
    SafetyCase(
        "grounded_critical_risk_with_high_scores", "evaluation", expected_state="pass"
    ),
    SafetyCase(
        "contradicted_grounded_critical_risk",
        "evaluation",
        expected_state="insufficient_evidence",
        expected_human_review=True,
    ),
    SafetyCase(
        "status_only_contradicted_grounded_critical_risk",
        "evaluation",
        expected_state="insufficient_evidence",
        expected_human_review=True,
    ),
    SafetyCase(
        "grounded_hard_exclusion_with_high_scores", "evaluation", expected_state="pass"
    ),
    SafetyCase(
        "contradicted_grounded_hard_exclusion",
        "evaluation",
        expected_state="insufficient_evidence",
        expected_human_review=True,
    ),
    SafetyCase(
        "grounded_complete_high_scores", "evaluation", expected_state="advance"
    ),
    SafetyCase("zero_claim_confidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("below_minimum_claim_confidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("minimum_claim_confidence_boundary", "evaluation", expected_state="advance"),
    SafetyCase("high_claim_confidence", "evaluation", expected_state="advance"),
    SafetyCase(
        "exact_false_critical_risk",
        "evaluation",
        expected_state="advance",
        expected_human_review=True,
    ),
    SafetyCase(
        "malformed_critical_risk",
        "evaluation",
        expected_state="insufficient_evidence",
        expected_human_review=True,
        expected_missing_information="critical risk",
    ),
    SafetyCase("expired_evidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("undated_evidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("stale_evidence", "evaluation", expected_state="advance"),
    SafetyCase("low_quality_evidence", "evaluation", expected_state="advance"),
    SafetyCase("advance_then_invest", "override", expected_override=None),
    SafetyCase(
        "advance_ruling_projection",
        "projection",
        expected_projection={"value": "MAYBE", "compatibility_reason": "advance"},
    ),
]


EVALUATION_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _support(evidence_id: str, **overrides: Any) -> dict[str, object]:
    link = {
        "evidence_item_id": evidence_id,
        "relationship": "supports",
        "support_strength": 0.9,
        "verification_state": "verified",
        "source_quality": 0.9,
        "trust_class": "independent",
        "untrusted_input": True,
        "prompt_injection_detected": False,
        "evidence_effective_at": "2026-07-01T00:00:00+00:00",
        "evidence_expires_at": "2026-08-01T00:00:00+00:00",
        "artifact_effective_at": "2026-07-01T00:00:00+00:00",
        "retrieved_at": "2026-07-01T01:00:00+00:00",
    }
    link.update(overrides)
    return link


def _claim(
    claim_id: str,
    claim_type: str,
    *,
    score: float | None = None,
    assertion_class: str = "externally_verified",
    grounded: bool = True,
    value: Any = None,
    confidence: float = 0.9,
    support_overrides: dict[str, Any] | None = None,
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    if score is not None:
        normalized["criterion_score"] = score
    if value is not None:
        normalized["value"] = value
    relationships = (
        [_support(f"evidence-{claim_id}", **(support_overrides or {}))]
        if grounded
        else []
    )
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "normalized_value": normalized,
        "unit": None,
        "period": None,
        "display_text": claim_type.replace("_", " "),
        "status_at_snapshot": "current",
        "assertion_class_at_snapshot": assertion_class,
        "operator_attribution_at_snapshot": None,
        "confidence_at_snapshot": confidence,
        "evaluation_at_snapshot": EVALUATION_AT.isoformat(),
        "supporting_evidence_ids": [
            link["evidence_item_id"] for link in relationships
        ],
        "contradicting_evidence_ids": [],
        "evidence_relationships": relationships,
    }


def _snapshot_for(name: str) -> list[dict[str, object]]:
    market = _claim("market", "market", score=9)
    execution = _claim("execution", "execution", score=9)
    if name == "ungrounded_high_score":
        return [
            _claim("market", "market", score=9, grounded=False),
            _claim("execution", "execution", score=9, grounded=False),
        ]
    if name == "model_inferred_high_score":
        return [
            _claim("market", "market", score=9, assertion_class="model_inferred"),
            _claim("execution", "execution", score=9, assertion_class="model_inferred"),
        ]
    if name == "required_dimension_missing":
        return [market]
    if name == "required_dimension_missing_with_grounded_critical_risk":
        return [market, _claim("risk", "critical_risk", value=True)]
    if name == "contradicted_scored_criterion":
        market["contradicting_evidence_ids"] = ["evidence-market-contradiction"]
        market["evidence_relationships"].append(
            _support("evidence-market-contradiction", relationship="contradicts")
        )
        return [market, execution]
    if name == "grounded_critical_risk_with_high_scores":
        return [market, execution, _claim("risk", "critical_risk", value=True)]
    if name == "contradicted_grounded_critical_risk":
        risk = _claim("risk", "critical_risk", value=True)
        risk["contradicting_evidence_ids"] = ["evidence-risk-contradiction"]
        risk["evidence_relationships"].append(
            _support("evidence-risk-contradiction", relationship="contradicts")
        )
        return [market, execution, risk]
    if name == "status_only_contradicted_grounded_critical_risk":
        risk = _claim("risk", "critical_risk", value=True)
        risk["status_at_snapshot"] = "contradicted"
        return [market, execution, risk]
    if name == "grounded_hard_exclusion_with_high_scores":
        return [
            market,
            execution,
            _claim("exclusion", "mandate_exclusion", value=True),
        ]
    if name == "contradicted_grounded_hard_exclusion":
        exclusion = _claim("exclusion", "mandate_exclusion", value=True)
        exclusion["contradicting_evidence_ids"] = [
            "evidence-exclusion-contradiction"
        ]
        exclusion["evidence_relationships"].append(
            _support("evidence-exclusion-contradiction", relationship="contradicts")
        )
        return [market, execution, exclusion]
    if name == "grounded_complete_high_scores":
        return [market, execution]
    if name in {
        "zero_claim_confidence",
        "below_minimum_claim_confidence",
        "minimum_claim_confidence_boundary",
        "high_claim_confidence",
    }:
        confidence = {
            "zero_claim_confidence": 0,
            "below_minimum_claim_confidence": 0.49,
            "minimum_claim_confidence_boundary": 0.5,
            "high_claim_confidence": 0.9,
        }[name]
        return [
            _claim("market", "market", score=9, confidence=confidence),
            _claim("execution", "execution", score=9, confidence=confidence),
        ]
    if name == "exact_false_critical_risk":
        return [market, execution, _claim("risk", "critical_risk", value=False)]
    if name == "malformed_critical_risk":
        return [market, execution, _claim("risk", "critical_risk", value="false")]
    if name in {"expired_evidence", "undated_evidence", "stale_evidence", "low_quality_evidence"}:
        overrides = {
            "expired_evidence": {"evidence_expires_at": "2026-07-19T00:00:00+00:00"},
            "undated_evidence": {
                "evidence_effective_at": None,
                "evidence_expires_at": None,
                "artifact_effective_at": None,
                "retrieved_at": None,
            },
            "stale_evidence": {
                "evidence_effective_at": "2025-01-01T00:00:00+00:00",
                "evidence_expires_at": None,
                "artifact_effective_at": "2025-01-01T00:00:00+00:00",
                "retrieved_at": "2025-01-01T00:00:00+00:00",
            },
            "low_quality_evidence": {"source_quality": 0.5},
        }[name]
        return [
            _claim("market", "market", score=9, support_overrides=overrides),
            _claim("execution", "execution", score=9, support_overrides=overrides),
        ]
    raise AssertionError(f"No evaluation snapshot for {name}")


def _safety_policy() -> EvaluationPolicy:
    partner_rules_path = (
        Path(__file__).resolve().parents[3]
        / "resources/config/partner_rules/v4.json"
    )
    partner_rules = json.loads(partner_rules_path.read_text())
    return evaluation_policy_from_compiled(
        {
            "policy_version_id": "policy-safety-v1",
            "policy_hash": "policy-safety-hash",
            "dimensions": {
                "market": {
                    "weight": 0.6,
                    "criteria": [{"id": "market", "source_components": []}],
                },
                "execution": {
                    "weight": 0.4,
                    "criteria": [{"id": "execution", "source_components": []}],
                },
            },
        },
        partner_rules=partner_rules,
    )


async def _analyze(snapshot, *, policy=None, partner_rationale=None):
    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment="Synthetic evidence assessment", assessments=[{
                "dimension": claim["claim_type"].upper(), "conclusion": "Material support",
                "proposed_score": 9, "confidence": 0.9,
                "score_rationale": "The cited factual evidence supports the proposed assessment.",
                "reasoning": [{"type": "INFERENCE", "text": "Material evidence supports this assessment.",
                               "references": {"claim_ids": [claim["claim_id"]]}}],
            } for claim in snapshot if claim["claim_type"] in {"market", "execution"}])
        return PartnerDraft(action="ADVANCE", confidence=0.9, rationale=partner_rationale or ["Test policy constraints"],
                            investment_case="Synthetic case",
                            assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]])

    return await analyze(user_id="safety-tenant", lineage=Lineage(user_id="safety-tenant"),
                         identity=Identity(name="Synthetic"), snapshot=snapshot,
                         policy=policy or _safety_policy(), evaluation_at=EVALUATION_AT,
                         context={}, generate=generate)


@pytest.mark.asyncio
async def test_partner_cannot_publish_an_unsupported_score_in_its_rationale():
    analysis = await _analyze(
        _snapshot_for("required_dimension_missing"),
        partner_rationale=["Validated assessments indicate Execution(5).", "Execution needs diligence."],
    )
    assert analysis.validation.assessments[1].validated_score is None
    assert analysis.partner.judgment.rationale == ["Execution needs diligence."]
    assert analysis.evaluation.recommendation.decision_drivers == ["Execution needs diligence."]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_decision_safety_case(case: SafetyCase) -> None:
    if case.kind == "evaluation":
        analysis = await _analyze(_snapshot_for(case.name))
        result = analysis.evaluation
        assert analysis.partner.judgment.action == "ADVANCE"
        assert result.recommendation.human_review_required
        for item in result.criteria:
            if item.score is None:
                assert item.confidence == 0
                assert item.missing_evidence
        assert result.recommendation.state.value == case.expected_state
        if case.expected_human_review is not None:
            assert (
                result.recommendation.human_review_required
                is case.expected_human_review
            )
        if case.expected_missing_information is not None:
            assert case.expected_missing_information in (
                item.lower() for item in result.recommendation.missing_information
            )
    elif case.kind == "override":
        assert classify_override(
            recommendation="advance",
            ruling=HumanRulingDecision.INVEST,
            requested=None,
        ) == case.expected_override
    else:
        projection = legacy_ruling_from_institutional("advance")
        assert projection.model_dump() == case.expected_projection


@pytest.mark.asyncio
@pytest.mark.parametrize("name,flag,cap_field", [
    ("minimum_claim_confidence_boundary", "claim_confidence_below_full", "claim_confidence"),
    ("stale_evidence", "evidence_stale", "freshness"),
    ("low_quality_evidence", "source_quality_below_full", "source_quality"),
])
async def test_caps_preserve_proposal_and_explain_validated_score(name, flag, cap_field):
    policy = _safety_policy()
    rule = getattr(policy.decision_safety, cap_field)
    score_cap = {"claim_confidence": "score_cap_below_full_confidence",
                 "freshness": "stale_score_cap",
                 "source_quality": "score_cap_below_full_quality"}[cap_field]
    confidence_cap = {"claim_confidence": "recommendation_confidence_cap_below_full_confidence",
                      "freshness": "stale_confidence_cap",
                      "source_quality": "recommendation_confidence_cap_below_full_quality"}[cap_field]
    result = await _analyze(_snapshot_for(name), policy=policy)
    for assessment, criterion in zip(result.validation.assessments, result.evaluation.criteria):
        assert assessment.proposed_score == 9
        assert assessment.validated_score == getattr(rule, score_cap)
        assert assessment.score_status == "CAPPED"
        assert flag in assessment.policy_flags
        assert assessment.cap_reason
        assert criterion.confidence == getattr(rule, confidence_cap)
        assert assessment.human_review_required


@pytest.mark.asyncio
@pytest.mark.parametrize("claim_type", ["critical_risk", "mandate_exclusion"])
@pytest.mark.parametrize("raw_value", ["false", "0", "no", 0, 1, [], {}, None])
async def test_malformed_decisive_values_block_advancement(claim_type, raw_value):
    snapshot = _snapshot_for("grounded_complete_high_scores")
    snapshot.append(_claim("decisive", claim_type, value=raw_value))
    result = await _analyze(snapshot)
    assert result.partner.operational_action == "MORE_DILIGENCE"
    assert claim_type.replace("_", " ") in result.evaluation.recommendation.missing_information
    assert result.partner.human_review_required


@pytest.mark.asyncio
@pytest.mark.parametrize("claim_type", ["critical_risk", "mandate_exclusion"])
async def test_ungrounded_decisive_claim_cannot_force_pass_or_allow_advance(claim_type):
    snapshot = _snapshot_for("grounded_complete_high_scores")
    snapshot.append(_claim("decisive", claim_type, value=True, grounded=False))
    result = await _analyze(snapshot)
    assert result.partner.operational_action == "MORE_DILIGENCE"
    assert claim_type.replace("_", " ") in result.evaluation.recommendation.missing_information


@pytest.mark.asyncio
@pytest.mark.parametrize("attributed", [False, True])
async def test_operator_evidence_requires_policy_permission_and_attribution(attributed):
    from evaluation_v2.service import evaluate_claim_score_eligibility

    claim = _claim("market", "market", assertion_class="operator_asserted", grounded=False)
    claim["operator_attribution_at_snapshot"] = "committee-review" if attributed else None
    policy = _safety_policy()
    # Permission and attribution are independent requirements.
    eligibility_policy = policy.decision_safety.evidence_eligibility
    policy.decision_safety = policy.decision_safety.model_copy(update={
        "evidence_eligibility": eligibility_policy.model_copy(update={"allowed_assertion_classes": ("externally_verified",)})})
    denied = evaluate_claim_score_eligibility(claim, policy=policy, evaluation_at=EVALUATION_AT)
    assert not denied.eligible
    policy.decision_safety = policy.decision_safety.model_copy(update={
        "evidence_eligibility": eligibility_policy.model_copy(update={"allowed_assertion_classes": ("externally_verified", "operator_asserted")})})
    eligibility = evaluate_claim_score_eligibility(claim, policy=policy, evaluation_at=EVALUATION_AT)
    assert eligibility.eligible is attributed
    if not attributed:
        assert "no_eligible_supporting_evidence" in eligibility.reason_codes


@pytest.mark.asyncio
async def test_optional_absence_stays_null_and_does_not_invent_a_score():
    policy = _safety_policy()
    policy.criteria[1].required = False
    result = await _analyze(_snapshot_for("required_dimension_missing"), policy=policy)
    absent = result.evaluation.criteria[1]
    assert absent.score is None
    assert absent.confidence == 0
    assert absent.missing_evidence
    assert result.partner.operational_action == "ADVANCE"


@pytest.mark.asyncio
async def test_zero_confidence_cap_is_preserved_without_division_or_score_invention():
    policy = _safety_policy()
    policy.decision_safety = policy.decision_safety.model_copy(update={
        "claim_confidence": policy.decision_safety.claim_confidence.model_copy(update={
            "recommendation_confidence_cap_below_full_confidence": 0})})
    result = await _analyze(_snapshot_for("minimum_claim_confidence_boundary"), policy=policy)
    assert all(item.confidence == 0 for item in result.evaluation.criteria)
    assert all(item.score_status == "BLOCKED" for item in result.validation.assessments)
    assert all(item.score is None for item in result.evaluation.criteria)
    assert result.partner.operational_action == "MORE_DILIGENCE"
    assert result.evaluation.recommendation.state.value == "insufficient_evidence"
    assert result.partner.human_review_required
