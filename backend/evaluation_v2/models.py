"""Contracts for deterministic criteria, evaluations, and recommendations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class EvaluationPolicy(BaseModel):
    policy_version_id: str
    policy_hash: str
    rubric_version: str
    partner_rules_version: str
    partner_rules_hash: str
    criteria: List[CriterionRule] = Field(min_length=1)
    advance_threshold: float = Field(default=7.5, ge=0, le=10)
    pass_threshold: float = Field(default=4.0, ge=0, le=10)
    minimum_scored_weight: float = Field(default=0.5, ge=0, le=1)
    hard_exclusion_claim_types: List[str] = Field(default_factory=list)


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
