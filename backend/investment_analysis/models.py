"""Model-facing drafts carry evidence references; execution identities are server-owned."""
from enum import Enum
from typing import Any
from pydantic import Field
from pipeline_contracts.models import (
    Contract, AnalysisSectionType, Confidence, Score, ReasoningType, ReviewStatus,
    References, ReviewerOutput, AssessmentValidationResult, Lineage,
)
from evaluation_v2.models import EvaluationResult


class ReasoningDraft(Contract):
    type: ReasoningType
    text: str = Field(min_length=1)
    references: References = Field(default_factory=References)


class AssessmentDraft(Contract):
    dimension: AnalysisSectionType
    conclusion: str = Field(min_length=1)
    proposed_score: Score | None = None
    score_rationale: str = Field(min_length=1)
    confidence: Confidence | None = None
    reasoning: list[ReasoningDraft] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class SectionDraft(Contract):
    name: AnalysisSectionType
    status: ReviewStatus
    reasoning: list[ReasoningDraft] = Field(default_factory=list)


class ReviewerDraft(Contract):
    overall_assessment: str = Field(min_length=1)
    assessments: list[AssessmentDraft] = Field(default_factory=list)
    analysis_sections: list[SectionDraft] = Field(default_factory=list)
    investment_case: list[ReasoningDraft] = Field(default_factory=list)
    risks: list[ReasoningDraft] = Field(default_factory=list)
    unknowns: list[ReasoningDraft] = Field(default_factory=list)
    contradictions: list[ReasoningDraft] = Field(default_factory=list)
    diligence_priorities: list[ReasoningDraft] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list, max_length=5)


class PartnerAction(str, Enum):
    ADVANCE = "ADVANCE"
    PASS = "PASS"
    MONITOR = "MONITOR"
    MORE_DILIGENCE = "MORE_DILIGENCE"


class PartnerDraft(Contract):
    action: PartnerAction
    rationale: list[str] = Field(min_length=1)
    assessment_ids: list[str] = Field(default_factory=list)
    principal_risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    confidence: Confidence
    investment_case: str = Field(min_length=1)
    challenge_to_review: str | None = None


class PartnerDecision(Contract):
    lineage: Lineage
    judgment: PartnerDraft
    operational_action: PartnerAction
    constraints: list[str] = Field(default_factory=list)
    human_review_required: bool
    prompt_version: str
    model: str | None = None


class AnalysisResult(Contract):
    review_reused: bool = False
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, str]] = Field(default_factory=list)
    reviewer: ReviewerOutput
    validation: AssessmentValidationResult
    partner: PartnerDecision
    evaluation: EvaluationResult
