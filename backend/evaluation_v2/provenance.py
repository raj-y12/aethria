"""Read-only provenance for the existing evaluator; never an input to scoring."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from tenant_context import require_user_id


class ScoreOrigin(str, Enum):
    REVIEWER_ASSESSMENT = "REVIEWER_ASSESSMENT"
    VALIDATED_REVIEWER_ASSESSMENT = "VALIDATED_REVIEWER_ASSESSMENT"
    CANONICAL_EVALUATION = "CANONICAL_EVALUATION"
    REVIEWER_LEGACY = "REVIEWER_LEGACY"
    PARTNER_LEGACY = "PARTNER_LEGACY"
    COMPATIBILITY_PROJECTION = "COMPATIBILITY_PROJECTION"
    UNKNOWN_LEGACY = "UNKNOWN_LEGACY"


class PipelineBinding(BaseModel):
    """Server-supplied linkage; absent historical identities stay absent."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    pipeline_run_id: Optional[str] = None
    pipeline_entry_type: Optional[str] = None
    company_id: Optional[str] = None
    scout_run_id: Optional[str] = None
    source_scout_pipeline_run_id: Optional[str] = None
    evidence_plan_id: Optional[str] = None


class CriterionProvenance(BaseModel):
    criterion: str
    score_origin: ScoreOrigin = ScoreOrigin.CANONICAL_EVALUATION
    canonical_score: Optional[float] = None
    reviewer_proposed_score: Optional[float] = None
    legacy_score: Optional[float] = None
    support_status: Optional[str] = None
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    # Preserve the evaluator's exact cap/adjustment structure rather than
    # inventing a second interpretation of policy-owned constraints.
    validation: dict[str, Any] = Field(default_factory=dict)


class EvaluationProvenance(BaseModel):
    provenance_version: str = "pipeline-provenance-v1"
    pipeline_run_id: Optional[str] = None
    pipeline_entry_type: Optional[str] = None
    company_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    scout_run_id: Optional[str] = None
    source_scout_pipeline_run_id: Optional[str] = None
    evaluation_run_id: Optional[str] = None
    evidence_snapshot_hash: Optional[str] = None
    evidence_plan_id: Optional[str] = None
    reviewer_run_id: Optional[str] = None
    validation_run_id: Optional[str] = None
    partner_run_id: Optional[str] = None
    evidence_artifact_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_links: list[dict[str, Any]] = Field(default_factory=list)
    score_origin: ScoreOrigin = ScoreOrigin.CANONICAL_EVALUATION
    score_schema_version: Optional[str] = None
    evaluation_rubric_version: Optional[str] = None
    reviewer_rules_version: Optional[str] = None
    partner_rules_version: Optional[str] = None
    thesis_version_id: Optional[str] = None
    policy_version: Optional[str] = None
    policy_hash: Optional[str] = None
    partner_rules_hash: Optional[str] = None
    recommendation_origin: str = "CANONICAL_EVALUATION"
    canonical_recommendation: Optional[str] = None
    human_review_required: Optional[bool] = None
    criteria: list[CriterionProvenance] = Field(default_factory=list)


def evaluation_provenance(
    *, user_id: str, evaluation: dict[str, Any],
    criteria: list[dict[str, Any]], recommendation: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Project only a previously tenant-scoped evaluation, without resolving IDs."""
    uid = require_user_id(user_id, context="evaluation_provenance")
    # asyncpg UUID columns and JSON transport use different Python types.
    def text_field(key: str) -> Optional[str]:
        value = evaluation.get(key)
        return str(value) if value is not None else None

    if evaluation.get("user_id") not in (None, uid):
        raise ValueError("evaluation provenance tenant mismatch")
    manifest = evaluation.get("model_manifest") or {}
    recorded = manifest.get("pipeline_provenance") or {}
    binding = recorded.get("binding") or {}
    if binding.get("user_id") not in (None, uid):
        raise ValueError("pipeline provenance tenant mismatch")
    for item in [*criteria, *([recommendation] if recommendation else [])]:
        if item.get("user_id") not in (None, uid):
            raise ValueError("assessment provenance tenant mismatch")
    snapshot = evaluation.get("claim_snapshot") or []
    rec = recommendation or {}
    analysis = (evaluation.get("judgment_audit") or {}).get("investment_analysis") or {}
    analysis_lineage = (analysis.get("partner") or {}).get("lineage") or {}
    if analysis_lineage.get("user_id") not in (None, uid):
        raise ValueError("investment analysis provenance tenant mismatch")
    return EvaluationProvenance(
        **{key: binding.get(key) for key in (
            "pipeline_run_id", "pipeline_entry_type", "company_id", "scout_run_id",
            "source_scout_pipeline_run_id", "evidence_plan_id",
        )},
        opportunity_id=text_field("opportunity_id"),
        reviewer_run_id=analysis_lineage.get("reviewer_run_id"),
        validation_run_id=analysis_lineage.get("validation_run_id"),
        partner_run_id=analysis_lineage.get("partner_run_id"),
        score_origin=ScoreOrigin.VALIDATED_REVIEWER_ASSESSMENT if analysis else ScoreOrigin.CANONICAL_EVALUATION,
        recommendation_origin="PARTNER_ANALYSIS" if analysis else "CANONICAL_EVALUATION",
        evaluation_run_id=text_field("evaluation_id"),
        evidence_snapshot_hash=text_field("evidence_snapshot_hash"),
        claim_ids=[str(claim["claim_id"]) for claim in snapshot if claim.get("claim_id")],
        evidence_links=recorded.get("evidence_links") or [],
        evidence_artifact_ids=sorted({str(link["artifact_id"]) for link in recorded.get("evidence_links") or [] if link.get("artifact_id")}),
        evaluation_rubric_version=text_field("rubric_version"),
        partner_rules_version=text_field("partner_rules_version"),
        thesis_version_id=text_field("thesis_version_id"),
        policy_version=text_field("policy_version_id"),
        policy_hash=text_field("policy_hash"),
        partner_rules_hash=text_field("partner_rules_hash"),
        canonical_recommendation=rec.get("recommended_state", rec.get("state")),
        human_review_required=rec.get("human_review_required"),
        criteria=[CriterionProvenance(
            criterion=item.get("criterion", "unknown"), canonical_score=item.get("score"),
            score_origin=ScoreOrigin.VALIDATED_REVIEWER_ASSESSMENT if analysis else ScoreOrigin.CANONICAL_EVALUATION,
            reviewer_proposed_score=((item.get("deterministic_adjustments") or {}).get("assessment_validation") or {}).get("proposed_score"),
            support_status=item.get("evidence_sufficiency"),
            supporting_claim_ids=item.get("supporting_claim_ids") or [],
            contradicting_claim_ids=item.get("contradicting_claim_ids") or [],
            missing_evidence=item.get("missing_evidence") or [],
            quality_flags=item.get("quality_flags") or [],
            validation={
                "deterministic_adjustments": item.get("deterministic_adjustments") or {},
                "supporting_claims": {
                    claim_id: (recorded.get("claim_validation") or {}).get(claim_id)
                    for claim_id in item.get("supporting_claim_ids") or []
                },
            },
        ) for item in sorted(criteria, key=lambda item: str(item.get("criterion") or ""))],
    ).model_dump(mode="json")
