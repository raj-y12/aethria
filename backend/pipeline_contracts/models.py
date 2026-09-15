"""Composable target contracts. Their existence conveys no runtime authority."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

from evaluation_v2.provenance import ScoreOrigin

# Named wire-compatible aliases; these are opaque references, never lookup keys
# without the enclosing explicit tenant context.
Identifier = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
ClaimId = Identifier
EvidenceItemId = Identifier
SourceId = Identifier
AssessmentId = Identifier
ReasoningUnitId = Identifier
ReviewerRunId = Identifier
ValidationRunId = Identifier
PartnerRunId = Identifier
EvidenceSnapshotHash = Identifier
Score = Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasoningType(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    OPINION = "OPINION"
    UNKNOWN = "UNKNOWN"


class ReviewStatus(str, Enum):
    PRESENT = "PRESENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_ASSESSED = "NOT_ASSESSED"


class SupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ContradictionStatus(str, Enum):
    PRESENT = "PRESENT"
    NONE_RECORDED = "NONE_RECORDED"
    UNKNOWN = "UNKNOWN"


class AnalysisSectionType(str, Enum):
    TEAM = "TEAM"
    MARKET = "MARKET"
    PRODUCT = "PRODUCT"
    TECHNOLOGY = "TECHNOLOGY"
    TRACTION = "TRACTION"
    CUSTOMERS = "CUSTOMERS"
    GTM = "GTM"
    BUSINESS_MODEL = "BUSINESS_MODEL"
    COMPETITION = "COMPETITION"
    DEFENSIBILITY = "DEFENSIBILITY"
    EXECUTION = "EXECUTION"
    CAPITAL_EFFICIENCY = "CAPITAL_EFFICIENCY"
    THESIS_FIT = "THESIS_FIT"


class ValidationStatus(str, Enum):
    NOT_VALIDATED = "NOT_VALIDATED"
    VALIDATED = "VALIDATED"
    CAPPED = "CAPPED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    # Current evaluator did not validate a Reviewer proposal.
    CURRENT_EVALUATION = "CURRENT_EVALUATION"


class RecommendationOrigin(str, Enum):
    PARTNER_ANALYSIS = "PARTNER_ANALYSIS"
    CANONICAL_EVALUATION = "CANONICAL_EVALUATION"
    PARTNER_CANONICAL_MAPPING = "PARTNER_CANONICAL_MAPPING"
    PARTNER_LEGACY = "PARTNER_LEGACY"
    DETERMINISTIC_PARTNER = "DETERMINISTIC_PARTNER"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    COMPATIBILITY_PROJECTION = "COMPATIBILITY_PROJECTION"
    UNKNOWN_LEGACY = "UNKNOWN_LEGACY"


class Decision(str, Enum):
    INVEST = "INVEST"
    PASS = "PASS"
    MONITOR = "MONITOR"


class References(Contract):
    claim_ids: list[ClaimId] = Field(default_factory=list)
    evidence_item_ids: list[EvidenceItemId] = Field(default_factory=list)
    source_ids: list[SourceId] = Field(default_factory=list)


class Lineage(Contract):
    user_id: Identifier
    company_id: Identifier | None = None
    opportunity_id: Identifier | None = None
    pipeline_run_id: Identifier | None = None
    scout_run_id: Identifier | None = None
    reviewer_run_id: ReviewerRunId | None = None
    evaluation_run_id: Identifier | None = None
    validation_run_id: ValidationRunId | None = None
    partner_run_id: PartnerRunId | None = None
    evidence_snapshot_hash: EvidenceSnapshotHash | None = None


class PolicyVersions(Contract):
    thesis_version_id: Identifier | None = None
    policy_version: Identifier | None = None
    policy_hash: Identifier | None = None
    rubric_version: Identifier | None = None
    reviewer_rules_version: Identifier | None = None
    partner_rules_version: Identifier | None = None


class StageMetadata(Contract):
    model: str | None = None
    prompt_version: str | None = None


class Identity(Contract):
    name: str | None = None
    website: str | None = None
    resolution_status: str | None = None


class ReasoningUnit(Contract):
    reasoning_unit_id: ReasoningUnitId
    type: ReasoningType
    text: str
    references: References = Field(default_factory=References)


class SourceReference(Contract):
    source_id: SourceId | None = None
    uri: str | None = None
    description: str | None = None


class EvidenceItem(Contract):
    evidence_item_id: EvidenceItemId
    source_ids: list[SourceId] = Field(default_factory=list)
    excerpt: str | None = None


class EvidenceSummary(Contract):
    coverage: Confidence | None = None
    support_status: SupportStatus = SupportStatus.UNKNOWN
    references: References = Field(default_factory=References)


class AnalysisSection(Contract):
    name: AnalysisSectionType
    status: ReviewStatus = ReviewStatus.UNKNOWN
    reasoning_units: list[ReasoningUnit] = Field(default_factory=list)


class LegacyExtension(Contract):
    """Lossless original JSON, isolated from target semantics. Never a write model."""
    adapter_version: Literal["current-v1"] = "current-v1"
    payload_kind: Literal["scout", "reviewer", "evaluation", "partner", "evidence_review", "partner_route"]
    original_payload: dict[str, JsonValue]
    projection_id_origin: Literal["tenant_scoped_content_digest"] = "tenant_scoped_content_digest"
    mismatches: list[str] = Field(default_factory=list)


class Envelope(Contract):
    contract_version: Literal["pipeline-contract-v1"] = "pipeline-contract-v1"
    lineage: Lineage
    policy_versions: PolicyVersions = Field(default_factory=PolicyVersions)
    metadata: StageMetadata = Field(default_factory=StageMetadata)
    compatibility: LegacyExtension | None = None

    @model_validator(mode="after")
    def validate_nested_scope(self):
        # Composition must never combine separate tenants or known companies/
        # opportunities. Opaque references are not resolved by this layer.
        def walk(value):
            if isinstance(value, Envelope) and value is not self:
                for field in ("user_id", "company_id", "opportunity_id"):
                    parent, child = getattr(self.lineage, field), getattr(value.lineage, field)
                    if parent is not None and child is not None and parent != child:
                        raise ValueError(f"contract {field} mismatch")
            if isinstance(value, BaseModel):
                for field in type(value).model_fields:
                    walk(getattr(value, field))
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)
        for field in type(self).model_fields:
            walk(getattr(self, field))
        return self


class ScoutOutput(Envelope):
    identity: Identity
    facts: list[ReasoningUnit] = Field(default_factory=list)
    unknowns: list[ReasoningUnit] = Field(default_factory=list)
    contradictions: list[ReasoningUnit] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)


class ReviewerAssessment(Contract):
    assessment_id: AssessmentId
    dimension: AnalysisSectionType
    conclusion: str | None = None
    proposed_score: Score | None = None
    score_origin: ScoreOrigin | None = None
    score_rationale: str | None = None
    confidence: Confidence | None = None
    reasoning_units: list[ReasoningUnit] = Field(default_factory=list)
    support_status: SupportStatus = SupportStatus.UNKNOWN
    status: ReviewStatus = ReviewStatus.UNKNOWN


class ReviewerOutput(Envelope):
    identity: Identity
    assessments: list[ReviewerAssessment] = Field(default_factory=list)
    investment_case: list[ReasoningUnit] = Field(default_factory=list)
    analysis_sections: list[AnalysisSection] = Field(default_factory=list)
    risks: list[ReasoningUnit] = Field(default_factory=list)
    contradictions: list[ReasoningUnit] = Field(default_factory=list)
    unknowns: list[ReasoningUnit] = Field(default_factory=list)
    diligence_priorities: list[ReasoningUnit] = Field(default_factory=list)
    overall_assessment: str | None = None
    status: ReviewStatus = ReviewStatus.UNKNOWN


class ReviewContext(Contract):
    fund_thesis: str | None = None
    mandate: list[str] = Field(default_factory=list)
    portfolio_context: list[str] | None = None
    analyst_context: list[str] = Field(default_factory=list)


class ReviewerInput(Envelope):
    scout: ScoutOutput
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    context: ReviewContext = Field(default_factory=ReviewContext)
    prior_review: ReviewerOutput | None = None


class ValidatedAssessment(Contract):
    reviewer_assessment_id: AssessmentId | None = None
    canonical_criterion_assessment_id: Identifier | None = None
    dimension: AnalysisSectionType
    proposed_score: Score | None = None
    validated_score: Score | None = None
    score_origin: ScoreOrigin | None = None
    score_status: ValidationStatus = ValidationStatus.UNKNOWN
    cap_value: Score | None = None
    cap_reason: str | None = None
    evidence_coverage: Confidence | None = None
    support_status: SupportStatus = SupportStatus.UNKNOWN
    contradiction_status: ContradictionStatus = ContradictionStatus.UNKNOWN
    policy_flags: list[str] = Field(default_factory=list)
    human_review_required: bool | None = None
    references: References = Field(default_factory=References)
    contradicting_claim_ids: list[ClaimId] = Field(default_factory=list)
    policy_versions: PolicyVersions = Field(default_factory=PolicyVersions)


class AssessmentValidationResult(Envelope):
    assessments: list[ValidatedAssessment] = Field(default_factory=list)
    human_review_required: bool | None = None


class PartnerInput(Envelope):
    identity: Identity
    reviewer: ReviewerOutput
    validation: AssessmentValidationResult
    strongest_evidence: list[ReasoningUnit] = Field(default_factory=list)
    material_unknowns: list[ReasoningUnit] = Field(default_factory=list)
    contradictions: list[ReasoningUnit] = Field(default_factory=list)
    context: ReviewContext = Field(default_factory=ReviewContext)
    prior_decision: PartnerOutput | None = None
    analyst_overrides: list[ReasoningUnit] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assessment_references(self):
        known = {item.assessment_id for item in self.reviewer.assessments}
        for item in self.validation.assessments:
            if item.reviewer_assessment_id is not None and item.reviewer_assessment_id not in known:
                raise ValueError("validation references an absent Reviewer assessment")
        return self


class PolicyResult(Contract):
    human_review_required: bool | None = None
    mandate_gate: str | None = None
    policy_changed_recommendation: bool | None = None
    guard_changed_recommendation: bool | None = None


class PartnerOutput(Envelope):
    # DeterministicPartner currently routes canonical states, not INVEST/PASS.
    # A route remains in compatibility; decision is unknown, never remapped here.
    decision: Decision | None = None
    recommendation_origin: RecommendationOrigin = RecommendationOrigin.UNKNOWN_LEGACY
    rationale: list[str] = Field(default_factory=list)
    investment_case: list[ReasoningUnit] = Field(default_factory=list)
    principal_risks: list[ReasoningUnit] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    conviction: Confidence | None = None
    policy_result: PolicyResult = Field(default_factory=PolicyResult)
    assessment_ids: list[AssessmentId] = Field(default_factory=list)
