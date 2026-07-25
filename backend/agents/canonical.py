"""Canonical evidence-first agent adapters.

These adapters do not call an LLM and do not own persistence. They translate the
immutable evaluation contract into explainable review and routing outputs.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class EvidenceReview(BaseModel):
    evaluation_id: str
    recommendation_id: str
    evidence_coverage: str
    scored_criteria: int = Field(ge=0)
    missing_information: List[str] = Field(default_factory=list)
    principal_risks: List[str] = Field(default_factory=list)
    decision_drivers: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class PartnerRoute(BaseModel):
    recommendation_id: str
    route: str
    human_review_required: bool = True
    rationale: List[str] = Field(default_factory=list)


class EvidenceReviewer:
    """Reviewer that reports only what the immutable evaluation contains."""

    def review(self, evaluation: Dict[str, Any]) -> EvidenceReview:
        recommendation = evaluation.get("recommendation") or {}
        criteria = list(evaluation.get("criteria") or [])
        scored = [item for item in criteria if item.get("score") is not None]
        missing = [
            str(item)
            for item in recommendation.get("missing_information") or []
            if str(item).strip()
        ]
        return EvidenceReview(
            evaluation_id=str(evaluation.get("evaluation_id") or ""),
            recommendation_id=str(evaluation.get("recommendation_id") or ""),
            evidence_coverage="sufficient" if scored and not missing else "insufficient",
            scored_criteria=len(scored),
            missing_information=missing,
            principal_risks=[str(item) for item in recommendation.get("principal_risks") or []],
            decision_drivers=[str(item) for item in recommendation.get("decision_drivers") or []],
            confidence=float(recommendation.get("confidence") or 0),
        )


class DeterministicPartner:
    """Decision router; it never changes the evaluator's recommendation."""

    def route(self, evaluation: Dict[str, Any], review: EvidenceReview) -> PartnerRoute:
        recommendation = evaluation.get("recommendation") or {}
        state = str(recommendation.get("state") or "insufficient_evidence")
        route = {
            "advance": "advance",
            "monitor": "monitor",
            "pass": "pass",
            "insufficient_evidence": "insufficient_evidence",
        }.get(state, "insufficient_evidence")
        rationale = list(review.decision_drivers) + list(review.principal_risks)
        return PartnerRoute(
            recommendation_id=review.recommendation_id,
            route=route,
            human_review_required=bool(recommendation.get("human_review_required", True)),
            rationale=rationale[:20],
        )
