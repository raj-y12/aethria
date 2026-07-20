"""Contracts for deterministic criteria, evaluations, and recommendations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RecommendationState(str, Enum):
    ADVANCE = "advance"
    MONITOR = "monitor"
    PASS = "pass"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CriterionRule(BaseModel):
    criterion: str = Field(min_length=1, max_length=100)
    claim_types: List[str] = Field(min_length=1)
    weight: float = Field(gt=0, le=1)
    required: bool = True


class EvidenceEligibilityPolicy(BaseModel):
    allowed_assertion_classes: List[str] = Field(min_length=1)
    allowed_relationships: List[str] = Field(min_length=1)
    require_verified_evidence: bool
    min_support_strength: float = Field(ge=0, le=1)
    min_source_quality: float = Field(ge=0, le=1)
    blocked_trust_classes: List[str] = Field(min_length=1)


class ClaimConfidencePolicy(BaseModel):
    minimum_eligible: float = Field(gt=0, le=1)
    full_confidence_at: float = Field(gt=0, le=1)
    score_cap_below_full_confidence: float = Field(ge=0, le=10)
    recommendation_confidence_cap_below_full_confidence: float = Field(ge=0, lt=1)
    zero_confidence_ineligible: Literal[True]

    @model_validator(mode="after")
    def validate_boundaries(self) -> "ClaimConfidencePolicy":
        if self.full_confidence_at < self.minimum_eligible:
            raise ValueError("full_confidence_at must be at least minimum_eligible")
        return self


class FreshnessPolicy(BaseModel):
    max_age_days: int = Field(gt=0)
    expired_action: Literal["ineligible"]
    undated_action: Literal["ineligible"]
    future_dated_action: Literal["ineligible"]
    stale_action: Literal["cap"]
    stale_score_cap: float = Field(ge=0, le=10)
    stale_confidence_cap: float = Field(ge=0, lt=1)


class SourceQualityPolicy(BaseModel):
    full_confidence_at: float = Field(ge=0, le=1)
    score_cap_below_full_quality: float = Field(ge=0, le=10)
    recommendation_confidence_cap_below_full_quality: float = Field(ge=0, lt=1)


class ScoreEligibility(BaseModel):
    eligible: bool
    reason_codes: List[str] = Field(default_factory=list)
    score_cap: float = Field(default=10, ge=0, le=10)
    confidence_cap: float = Field(default=1, ge=0, le=1)


class DecisionSafetyPolicy(BaseModel):
    evidence_eligibility: EvidenceEligibilityPolicy
    critical_risk_claim_types: List[str] = Field(min_length=1)
    hard_exclusion_claim_types: List[str] = Field(min_length=1)
    claim_confidence: ClaimConfidencePolicy
    freshness: FreshnessPolicy
    source_quality: SourceQualityPolicy


class EvaluationPolicy(BaseModel):
    policy_version_id: str = Field(min_length=1)
    policy_hash: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    partner_rules_version: str = Field(min_length=1)
    partner_rules_hash: str = Field(min_length=1)
    criteria: List[CriterionRule] = Field(min_length=1)
    advance_threshold: float = Field(ge=0, le=10)
    pass_threshold: float = Field(ge=0, le=10)
    advance_comparison: Literal["greater_than_or_equal"]
    pass_comparison: Literal["less_than"]
    minimum_scored_weight: float = Field(gt=0, le=1)
    decision_safety: DecisionSafetyPolicy
    hard_exclusion_claim_types: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "EvaluationPolicy":
        if self.pass_threshold >= self.advance_threshold:
            raise ValueError("pass_threshold must be below advance_threshold")
        return self


class CriterionResult(BaseModel):
    criterion: str
    score: Optional[float] = Field(default=None, ge=0, le=10)
    confidence: float = Field(default=0, ge=0, le=1)
    evidence_sufficiency: str
    reasoning: str
    supporting_claim_ids: List[str] = Field(default_factory=list)
    contradicting_claim_ids: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    quality_flags: List[str] = Field(default_factory=list)
    deterministic_adjustments: Dict[str, Any] = Field(default_factory=dict)


class RecommendationResult(BaseModel):
    state: RecommendationState
    attention_priority: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0, ge=0, le=1)
    decision_drivers: List[str] = Field(default_factory=list)
    principal_risks: List[str] = Field(default_factory=list)
    mandate_conflicts: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    change_conditions: List[str] = Field(default_factory=list)
    human_review_required: bool = True
    change_explanation: Optional[str] = None


class EvaluationResult(BaseModel):
    snapshot_hash: str
    criteria: List[CriterionResult]
    recommendation: RecommendationResult
