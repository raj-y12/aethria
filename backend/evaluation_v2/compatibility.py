"""Sole Phase 4 recommendation projection into legacy partner vocabulary."""

from evaluation_v2.models import RecommendationState


def recommendation_to_legacy(state: RecommendationState | str) -> dict:
    value = RecommendationState(state)
    if value is RecommendationState.ADVANCE:
        return {"recommendation": "INVEST", "human_review_required": False}
    if value is RecommendationState.MONITOR:
        return {"recommendation": "MONITOR", "human_review_required": False}
    if value is RecommendationState.PASS:
        return {"recommendation": "PASS", "human_review_required": False}
    return {
        "recommendation": "MONITOR",
        "human_review_required": True,
        "compatibility_reason": "insufficient_evidence",
    }
