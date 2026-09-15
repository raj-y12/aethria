"""Constrain Reviewer proposals using existing evidence policy; never invent scores."""
from datetime import datetime
from uuid import uuid4

from evaluation_v2.models import CriterionResult, EvaluationPolicy
from evaluation_v2.service import evaluate_claim_score_eligibility
from evaluation_v2.provenance import ScoreOrigin
from pipeline_contracts.adapters import DIMENSIONS
from pipeline_contracts.models import (
    AssessmentValidationResult, ValidatedAssessment, ReviewerOutput,
    ValidationStatus, SupportStatus, ContradictionStatus, References, ReasoningType,
)
from tenant_context import require_user_id
from .grounding import financial_assertions_supported

_CAP_EXPLANATIONS = {
    "claim_confidence_below_full": "The factual claims are not yet established with high confidence.",
    "evidence_stale": "The supporting evidence is older than the fund's freshness policy permits for a higher score.",
    "source_quality_below_full": "The supporting sources lack the reliability required for a higher score.",
}

def validate_assessments(*, user_id: str, review: ReviewerOutput, snapshot: list[dict],
                         policy: EvaluationPolicy, evaluation_at: datetime) -> tuple[AssessmentValidationResult, list[CriterionResult]]:
    uid = require_user_id(user_id, context="validate_investment_assessments")
    if review.lineage.user_id != uid:
        raise ValueError("review tenant mismatch")
    claims = {str(claim["claim_id"]): claim for claim in snapshot}
    proposed = {item.dimension: item for item in review.assessments}
    if len(proposed) != len(review.assessments):
        raise ValueError("duplicate Reviewer dimension")
    validated, criteria = [], []
    for rule in policy.criteria:
        dimension = DIMENSIONS.get(rule.criterion)
        if dimension is None:
            raise ValueError(f"unsupported policy dimension: {rule.criterion}")
        assessment = proposed.get(dimension)
        all_references = {claim_id for unit in assessment.reasoning_units for claim_id in unit.references.claim_ids} if assessment else set()
        unknown_ids = all_references - set(claims)
        if unknown_ids:
            raise ValueError("assessment references a claim outside the supplied tenant snapshot")
        # Unknowns (including invalid citations downgraded by the binding layer),
        # assumptions and opinions are context, not evidence supporting a score.
        references = sorted({claim_id for unit in assessment.reasoning_units
                             if unit.type in {ReasoningType.FACT, ReasoningType.INFERENCE}
                             for claim_id in unit.references.claim_ids}) if assessment else []
        eligibility = {key: evaluate_claim_score_eligibility(claims[key], policy=policy, evaluation_at=evaluation_at) for key in references}
        supported = [key for key in references if eligibility[key].eligible]
        contradicted = [key for key in references if claims[key].get("status_at_snapshot") == "contradicted" or claims[key].get("contradicting_evidence_ids")]
        missing = []
        flags = sorted({reason for result in eligibility.values() for reason in result.reason_codes})
        if not assessment:
            missing.append("Reviewer did not assess this dimension.")
        elif assessment.proposed_score is None:
            missing.append("Reviewer could not justify a numerical assessment.")
        if not references:
            missing.append("No material supporting claims were cited.")
        elif len(supported) != len(references):
            missing.append("One or more material claims lack eligible evidence.")
        cited_claims = [claims[key] for key in references]
        financial_support = bool(assessment) and financial_assertions_supported(
            assessment.score_rationale, cited_claims,
        ) if assessment else False
        if assessment and not financial_support:
            missing.append("Material financial assertion is not supported with the cited metric and value.")
        can_score = (assessment is not None and assessment.proposed_score is not None and bool(references)
                     and len(supported) == len(references) and financial_support)
        cap = min((result.score_cap for result in eligibility.values()), default=None)
        score = min(assessment.proposed_score, cap) if can_score else None
        status = ValidationStatus.BLOCKED if not can_score else ValidationStatus.CAPPED if score < assessment.proposed_score else ValidationStatus.VALIDATED
        confidence = min([assessment.confidence if assessment and assessment.confidence is not None else 0.0] + [result.confidence_cap for result in eligibility.values()]) if can_score else 0.0
        evidence_ids = sorted({evidence_id for key in supported for evidence_id in claims[key].get("supporting_evidence_ids") or []})
        source_ids = sorted({str(link["artifact_id"]) for key in supported
                             for link in claims[key].get("evidence_relationships") or []
                             if link.get("artifact_id") and link.get("evidence_item_id") in evidence_ids})
        cap_reasons = [_CAP_EXPLANATIONS.get(flag, flag.replace("_", " ")) for flag in flags] if status == ValidationStatus.CAPPED else missing
        audit = ValidatedAssessment(
            reviewer_assessment_id=assessment.assessment_id if assessment else None,
            dimension=dimension, proposed_score=assessment.proposed_score if assessment else None,
            validated_score=score, score_origin=ScoreOrigin.VALIDATED_REVIEWER_ASSESSMENT,
            score_status=status, cap_value=cap if status == ValidationStatus.CAPPED else None,
            cap_reason="; ".join(cap_reasons) or None,
            evidence_coverage=len(supported) / len(references) if references else None,
            support_status=SupportStatus.SUPPORTED if can_score else SupportStatus.UNSUPPORTED,
            contradiction_status=ContradictionStatus.PRESENT if contradicted else ContradictionStatus.NONE_RECORDED,
            policy_flags=flags, human_review_required=bool(missing or contradicted or status == ValidationStatus.CAPPED),
            references=References(claim_ids=supported, evidence_item_ids=evidence_ids, source_ids=source_ids),
            contradicting_claim_ids=contradicted, policy_versions=review.policy_versions,
        )
        validated.append(audit)
        reasoning = assessment.score_rationale if assessment else "Not assessed by Reviewer."
        if cap_reasons:
            reasoning += " Evidence limitation: " + "; ".join(cap_reasons)
        criteria.append(CriterionResult(
            criterion=rule.criterion, score=score, confidence=confidence,
            evidence_sufficiency="insufficient" if not can_score else "partial" if contradicted else "sufficient",
            reasoning=reasoning, supporting_claim_ids=supported, contradicting_claim_ids=contradicted,
            missing_evidence=missing, quality_flags=flags,
            deterministic_adjustments={"assessment_validation": audit.model_dump(mode="json")},
        ))
    result = AssessmentValidationResult(
        lineage=review.lineage.model_copy(update={"validation_run_id": str(uuid4())}),
        policy_versions=review.policy_versions, assessments=validated,
        human_review_required=any(item.human_review_required for item in validated),
    )
    return result, criteria
