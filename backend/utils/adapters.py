"""
Adapters to convert between old format and new Pydantic models.

Maintains backward compatibility during migration.
Timestamps are taken from stored data when available; fallback to datetime.now().
"""
from typing import Dict, Any, Optional
from datetime import datetime

from uuid import uuid4
from models import ScoutInfo, ReviewInfo, PartnerInfo, Financials


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse timestamp from dict input (ISO string or datetime). Returns None if missing or invalid."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def scout_output_to_scout_info(scout_output: Dict[str, Any]) -> ScoutInfo:
    """
    Convert old ScoutOutput to new ScoutInfo Pydantic model.
    Uses discovered_at from input when available; otherwise datetime.now().
    
    Args:
        scout_output: Old ScoutOutput dict (may include discovered_at from storage)
    
    Returns:
        ScoutInfo Pydantic model
    """
    discovered = _parse_timestamp(scout_output.get("discovered_at"))
    if discovered is None:
        discovered = datetime.now()
    raw_id = scout_output.get("id") or ""
    startup_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else str(uuid4())
    return ScoutInfo(
        startup_id=startup_id,
        name=scout_output.get("name", ""),
        one_line=scout_output.get("one_line", ""),
        sector=scout_output.get("sector", ""),
        problem=scout_output.get("problem", ""),
        solution=scout_output.get("solution", ""),
        target_users=scout_output.get("target_users", ""),
        why_now=scout_output.get("why_now", ""),
        scout_type=scout_output.get("scout_type", "market_driven"),
        confidence_score=scout_output.get("confidence", 0.5),
        primary_thesis=scout_output.get("primary_thesis"),
        key_assumptions=scout_output.get("key_assumptions"),
        biggest_unknown=scout_output.get("biggest_unknown"),
        funding_stage=scout_output.get("funding_stage"),
        est_tam=scout_output.get("est_tam"),
        references=scout_output.get("references") or None,
        origin_type=scout_output.get("origin_type"),
        lookup_input_type=scout_output.get("lookup_input_type"),
        lookup_query=scout_output.get("lookup_query"),
        lookup_website=scout_output.get("lookup_website"),
        lookup_id=scout_output.get("lookup_id"),
        discovered_at=discovered,
        prompt_version=scout_output.get("prompt_version"),
    )


def reviewer_output_to_review_info(reviewer_output: Dict[str, Any]) -> ReviewInfo:
    """
    Convert old ReviewerOutput to new ReviewInfo Pydantic model.
    Preserves defensibility_score and diligence_red_flags.
    Uses reviewed_at from input when available; otherwise datetime.now().
    
    Args:
        reviewer_output: Old ReviewerOutput dict (may include reviewed_at from storage)
    
    Returns:
        ReviewInfo Pydantic model
    """
    reviewed = _parse_timestamp(reviewer_output.get("reviewed_at"))
    if reviewed is None:
        reviewed = datetime.now()
    return ReviewInfo(
        market_score=reviewer_output.get("market_score", 5),
        product_score=reviewer_output.get("product_score", 5),
        technical_score=reviewer_output.get("technical_score", 5),
        execution_score=reviewer_output.get("execution_score", 5),
        defensibility_score=reviewer_output.get("defensibility_score"),
        overall_summary=reviewer_output.get("overall_summary", ""),
        key_risks=reviewer_output.get("key_risks", []),
        verdict=reviewer_output.get("verdict", "MEDIUM"),
        derived_verdict=reviewer_output.get("derived_verdict"),
        diligence_red_flags=reviewer_output.get("diligence_red_flags", []),
        assumption_feedback=reviewer_output.get("assumption_feedback") or [],
        reviewer_agent_id=reviewer_output.get("reviewer_agent_id"),
        reviewed_at=reviewed,
        team_analysis=reviewer_output.get("team_analysis") or None,
        competition_analysis=reviewer_output.get("competition_analysis") or None,
        business_model_analysis=reviewer_output.get("business_model_analysis") or None,
        investment_thesis=reviewer_output.get("investment_thesis") or None,
        risk_mitigation=reviewer_output.get("risk_mitigation") or None,
        score_reasoning=reviewer_output.get("score_reasoning") or None,
        prompt_version=reviewer_output.get("prompt_version"),
        fund_thesis_version_id=reviewer_output.get("fund_thesis_version_id"),
        thesis_alignment_score=reviewer_output.get("thesis_alignment_score"),
        thesis_matches_fund=reviewer_output.get("thesis_matches_fund"),
        thesis_fit_points=reviewer_output.get("thesis_fit_points") or None,
        thesis_deviation_points=reviewer_output.get("thesis_deviation_points") or None,
        thesis_alignment_confidence=reviewer_output.get("thesis_alignment_confidence"),
        fund_thesis_alignment_score=reviewer_output.get("fund_thesis_alignment_score"),
        weighted_defensibility_score=reviewer_output.get("weighted_defensibility_score"),
        confidence_adjusted_score=reviewer_output.get("confidence_adjusted_score"),
    )


def partner_output_to_partner_info(partner_output: Dict[str, Any]) -> PartnerInfo:
    """
    Convert old PartnerOutput to new PartnerInfo Pydantic model.
    Maps legacy decisions: INVEST → YES, WATCH → MAYBE, PASS → NO.
    Preserves next_action, human_review_required, rationale, conviction_level.
    Uses partnered_at from input when available; otherwise datetime.now().
    
    Args:
        partner_output: Old PartnerOutput dict (may include partnered_at from storage)
    
    Returns:
        PartnerInfo Pydantic model
    """
    decision_map = {
        "INVEST": "YES",
        "WATCH": "MAYBE",
        "PASS": "NO",
    }
    old_decision = partner_output.get("decision", "PASS")
    new_decision = decision_map.get(old_decision, old_decision if old_decision in ("YES", "NO", "MAYBE") else "NO")
    conviction = partner_output.get("conviction_level") or partner_output.get("confidence", 5)
    conviction = max(1, min(10, conviction))
    partnered = _parse_timestamp(partner_output.get("partnered_at"))
    if partnered is None:
        partnered = datetime.now()
    return PartnerInfo(
        decision=new_decision,
        rationale=partner_output.get("rationale", ""),
        next_action=partner_output.get("next_action", ""),
        conviction_level=conviction,
        human_review_required=partner_output.get("human_review_required", False),
        partner_agent_id=partner_output.get("partner_agent_id"),
        partnered_at=partnered,
        llm_fallback_reason=partner_output.get("llm_fallback_reason"),
        memo_at_decision=partner_output.get("memo_at_decision"),
        portfolio_context_at_decision=partner_output.get("portfolio_context_at_decision"),
        prompt_version=partner_output.get("prompt_version"),
        grey_zone_deep_dive=partner_output.get("grey_zone_deep_dive"),
    )
