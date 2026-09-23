"""
Convert Scout payloads into the persisted ScoutInfo shape.
Timestamps are taken from stored data when available; fallback to utcnow().
"""
from typing import Dict, Any, Optional
from datetime import datetime
from utils.timeutil import utcnow

from uuid import uuid4
from models import ScoutInfo, Financials
from utils.traction_extraction import extract_traction_facts
from scout.tools.financials_grounding import funding_history_for_stage


def financials_from_scout_output(scout_output: Dict[str, Any]) -> Financials:
    """Build Financials from the scout's grounding-verified financial values.

    Reads `financials_grounded` (produced by scout.tools.financials_grounding.ground_financials),
    which contains only values that passed the deterministic source-citation gate, plus the
    revenue_/funding_/valuation_missing flags. When absent (e.g. ungrounded path), returns an
    empty Financials — never a guessed value.
    """
    grounded = scout_output.get("financials_grounded")
    if not isinstance(grounded, dict):
        return Financials()
    funding_history = funding_history_for_stage(grounded.get("funding_history"), scout_output.get("funding_stage"))
    return Financials(
        traction_metrics=grounded.get("traction_metrics"),
        funding_history=funding_history,
        valuation_est=grounded.get("valuation_est"),
        ip_status=grounded.get("ip_status"),
        revenue_missing=bool(grounded.get("revenue_missing", False)),
        funding_missing=bool(grounded.get("funding_missing", False) or (grounded.get("funding_history") and not funding_history)),
        valuation_missing=bool(grounded.get("valuation_missing", False)),
    )


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
    Uses discovered_at from input when available; otherwise utcnow().
    
    Args:
        scout_output: Old ScoutOutput dict (may include discovered_at from storage)
    
    Returns:
        ScoutInfo Pydantic model
    """
    discovered = _parse_timestamp(scout_output.get("discovered_at"))
    if discovered is None:
        discovered = utcnow()
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
        unknowns=scout_output.get("unknowns") or [],
        contradictions=scout_output.get("contradictions") or [],
        funding_stage=scout_output.get("funding_stage"),
        location=(str(scout_output.get("location") or "").strip() or None),
        est_tam=scout_output.get("est_tam"),
        founder_names=(
            [str(name).strip() for name in scout_output.get("founder_names") if str(name).strip()]
            if isinstance(scout_output.get("founder_names"), list)
            else None
        ),
        founder_resolution=(
            scout_output.get("founder_resolution")
            if isinstance(scout_output.get("founder_resolution"), dict)
            else None
        ),
        field_provenance=scout_output.get("field_provenance") if isinstance(scout_output.get("field_provenance"), dict) else None,
        references=scout_output.get("references") or None,
        source_evidence=scout_output.get("source_evidence") if isinstance(scout_output.get("source_evidence"), list) else None,
        traction_facts=extract_traction_facts(scout_output),
        origin_type=scout_output.get("origin_type"),
        lookup_input_type=scout_output.get("lookup_input_type"),
        lookup_query=scout_output.get("lookup_query"),
        lookup_website=scout_output.get("lookup_website"),
        lookup_id=scout_output.get("lookup_id"),
        resolution_status=(
            scout_output.get("resolution_status")
            if scout_output.get("resolution_status")
            in ("FOUND", "PARTIAL", "LOW_CONFIDENCE", "NEEDS_REVIEW", "NOT_FOUND")
            else None
        ),
        company_resolution=(
            scout_output.get("company_resolution")
            if isinstance(scout_output.get("company_resolution"), dict)
            else None
        ),
        discovered_at=discovered,
        prompt_version=scout_output.get("prompt_version"),
    )
