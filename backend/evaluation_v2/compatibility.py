"""Sole Phase 4 recommendation projection into legacy partner vocabulary."""

from evaluation_v2.models import RecommendationState
from utils.partner_codes import legacy_partner_from_institutional_recommendation


def recommendation_to_legacy(state: RecommendationState | str) -> dict:
    value = RecommendationState(state)
    projection = legacy_partner_from_institutional_recommendation(value.value)
    response = {
        "recommendation": projection.value,
        "human_review_required": value is RecommendationState.INSUFFICIENT_EVIDENCE,
    }
    if projection.compatibility_reason is not None:
        response["compatibility_reason"] = projection.compatibility_reason
    return response
