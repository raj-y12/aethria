"""Contracts for deterministic criteria, evaluations, and recommendations."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)


_PolicyNumber = StrictInt | StrictFloat
_PolicyString = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]


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


class FactBand(BaseModel):
    """A policy-owned lower bound and its fixed rubric anchor."""

    minimum: float
    score: float = Field(ge=0, le=10)
    label: str = Field(min_length=1, max_length=100)


class FactRule(BaseModel):
    """A typed fact whose score is derived from published policy, not an LLM."""

    claim_type: str = Field(min_length=1, max_length=100)
    dimension: str = Field(min_length=1, max_length=100)
    unit: Literal["usd", "percentage"]
    bands: List[FactBand] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_descending_bands(self) -> "FactRule":
        minima = [band.minimum for band in self.bands]
        if minima != sorted(minima, reverse=True) or len(set(minima)) != len(minima):
            raise ValueError("fact rule band minimums must be unique and descending")
        return self


class EvidenceEligibilityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_assertion_classes: tuple[_PolicyString, ...] = Field(min_length=1)
    allowed_relationships: tuple[_PolicyString, ...] = Field(min_length=1)
    require_verified_evidence: StrictBool
    min_support_strength: _PolicyNumber = Field(ge=0, le=1)
    min_source_quality: _PolicyNumber = Field(ge=0, le=1)
    blocked_trust_classes: tuple[_PolicyString, ...] = Field(min_length=1)


class ClaimConfidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_eligible: _PolicyNumber = Field(gt=0, le=1)
    full_confidence_at: _PolicyNumber = Field(gt=0, le=1)
    score_cap_below_full_confidence: _PolicyNumber = Field(ge=0, le=10)
    recommendation_confidence_cap_below_full_confidence: _PolicyNumber = Field(
        ge=0, lt=1
    )
    zero_confidence_ineligible: Literal[True]

    @model_validator(mode="after")
    def validate_boundaries(self) -> "ClaimConfidencePolicy":
        if self.full_confidence_at < self.minimum_eligible:
            raise ValueError("full_confidence_at must be at least minimum_eligible")
        return self


class FreshnessPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_age_days: StrictInt = Field(gt=0)
    expired_action: Literal["ineligible"]
    undated_action: Literal["ineligible"]
    future_dated_action: Literal["ineligible"]
    stale_action: Literal["cap"]
    stale_score_cap: _PolicyNumber = Field(ge=0, le=10)
    stale_confidence_cap: _PolicyNumber = Field(ge=0, lt=1)


class SourceQualityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    full_confidence_at: _PolicyNumber = Field(ge=0, le=1)
    score_cap_below_full_quality: _PolicyNumber = Field(ge=0, le=10)
    recommendation_confidence_cap_below_full_quality: _PolicyNumber = Field(
        ge=0, lt=1
    )


class ScoreEligibility(BaseModel):
    eligible: bool
    reason_codes: List[str] = Field(default_factory=list)
    score_cap: float = Field(default=10, ge=0, le=10)
    confidence_cap: float = Field(default=1, ge=0, le=1)


class DecisionSafetyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_eligibility: EvidenceEligibilityPolicy
    critical_risk_claim_types: tuple[_PolicyString, ...] = Field(min_length=1)
    hard_exclusion_claim_types: tuple[_PolicyString, ...] = Field(min_length=1)
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
    fact_rules: List[FactRule] = Field(default_factory=list)

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
