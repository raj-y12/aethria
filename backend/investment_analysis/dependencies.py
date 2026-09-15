"""Read-only validity of an immutable investment review against current inputs."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.service import materiality_digest
from tenant_context import require_user_id
from .models import AnalysisResult
from .prompts import REVIEWER_PROMPT_VERSION, PARTNER_PROMPT_VERSION
from .validation import validate_assessments


class DependencyState(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class AnalysisDependencyStatus(BaseModel):
    state: DependencyState
    reasons: list[str] = Field(default_factory=list)
    message: str


def inspect_analysis_dependencies(*, user_id: str, opportunity_id: str, analysis: AnalysisResult,
                                  snapshot: list[dict], prior_snapshot: list[dict], policy: EvaluationPolicy,
                                  thesis_version_id: str | None, evaluation_at: datetime) -> AnalysisDependencyStatus:
    uid = require_user_id(user_id, context="inspect_analysis_dependencies")
    review = analysis.reviewer
    if review.lineage.user_id != uid or review.lineage.opportunity_id != opportunity_id:
        raise ValueError("analysis tenant/opportunity mismatch")
    if any(claim.get("user_id") not in (None, uid) for claim in snapshot):
        raise ValueError("snapshot tenant/opportunity mismatch")
    reasons = []
    if materiality_digest(prior_snapshot) != materiality_digest(snapshot):
        reasons.append("evidence_changed")
    # The snapshot hash changes as the freshness clock advances. Compare
    # material facts separately from the current evidence-policy result.
    versions = review.policy_versions
    if versions.thesis_version_id != thesis_version_id:
        reasons.append("thesis_changed")
    if (versions.policy_version != policy.policy_version_id or versions.policy_hash != policy.policy_hash
            or versions.rubric_version != policy.rubric_version or versions.partner_rules_version != policy.partner_rules_version):
        reasons.append("policy_changed")
    if review.metadata.prompt_version != REVIEWER_PROMPT_VERSION or analysis.partner.prompt_version != PARTNER_PROMPT_VERSION:
        reasons.append("analysis_instructions_changed")
    # Evaluate current eligibility without writing replacement assessments.
    try:
        current, _ = validate_assessments(user_id=uid, review=review, snapshot=snapshot,
                                         policy=policy, evaluation_at=evaluation_at)
        material_fields = {"dimension", "validated_score", "score_status", "support_status", "contradiction_status", "policy_flags"}
        if ([item.model_dump(include=material_fields) for item in current.assessments]
                != [item.model_dump(include=material_fields) for item in analysis.validation.assessments]):
            reasons.append("evidence_support_changed")
    except ValueError:
        reasons.append("evidence_changed")
    return AnalysisDependencyStatus(state=DependencyState.STALE if reasons else DependencyState.CURRENT,
        reasons=reasons, message="This review needs refreshing because its evidence, thesis, or policy has changed. Historical scores and reasoning are shown below."
        if reasons else "Review dependencies are current.")
