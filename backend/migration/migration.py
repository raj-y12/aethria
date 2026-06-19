"""
Migration utility to convert old storage format to new Pydantic models.

Converts from old discoveries.json format to new startups.json format.
Includes all new fields in ScoutInfo, ReviewInfo, PartnerInfo, Financials.
Preserves original timestamps; populates empty financials safely; logs missing critical fields.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from utils.timeutil import utcnow

from models import Startup, ScoutInfo, ReviewInfo, PartnerInfo, Financials
from utils.storage import Storage


logger = logging.getLogger(__name__)

# Legacy decision mapping for Partner
# Legacy vocabulary intentionally retained for migration only
PARTNER_DECISION_MAP = {"INVEST": "YES", "WATCH": "MAYBE", "PASS": "NO"}


def _parse_ts(value: Any) -> datetime:
    """Parse timestamp from old entry; fallback to now."""
    if value is None:
        return utcnow()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return utcnow()
    return utcnow()


def migrate_old_to_new(old_file: str, new_file: str) -> None:
    """
    Migrate from old discoveries.json format to new startups.json format.
    Includes all new fields (defensibility_score, diligence_red_flags, next_action,
    human_review_required, conviction_level, etc.). Preserves original timestamps.
    Populates empty financials with missing-data flags so Partner decisions don't under-report risks.
    Logs entries missing key_risks, TAM, or funding_stage.
    
    Args:
        old_file: Path to old discoveries.json
        new_file: Path to new startups.json
    """
    logger.info(f"Migrating from {old_file} to {new_file}")
    path = Path(old_file)
    if not path.exists():
        logger.error(f"Old file not found: {old_file}")
        return
    with open(old_file, "r") as f:
        old_entries = json.load(f)
    if not isinstance(old_entries, list):
        logger.error("Old file is not a list of entries")
        return

    new_storage = Storage(file_path=new_file)
    migrated: List[dict] = []
    migrated_count = 0

    for idx, old_entry in enumerate(old_entries):
        entry_id = old_entry.get("id") or old_entry.get("startup_id") or f"entry_{idx}"
        timestamps = old_entry.get("timestamps", {})
        try:
            scout_data = old_entry.get("scout", {})
            discovered_at = _parse_ts(timestamps.get("discovered_at"))
            scout_info = ScoutInfo(
                startup_id=scout_data.get("id", entry_id),
                name=scout_data.get("name", ""),
                one_line=scout_data.get("one_line", ""),
                sector=scout_data.get("sector", ""),
                problem=scout_data.get("problem", ""),
                solution=scout_data.get("solution", ""),
                target_users=scout_data.get("target_users", ""),
                why_now=scout_data.get("why_now", ""),
                scout_type=scout_data.get("scout_type", "market_driven"),
                confidence_score=float(scout_data.get("confidence", 0.5)),
                funding_stage=scout_data.get("funding_stage"),
                location=scout_data.get("location"),
                est_tam=scout_data.get("est_tam"),
                discovered_at=discovered_at,
            )
            if not scout_info.est_tam:
                logger.warning(f"Entry {entry_id}: missing TAM (est_tam)")
            if not scout_info.funding_stage:
                logger.warning(f"Entry {entry_id}: missing funding_stage")

            # Financials: populate empty and set missing flags so risks aren't under-reported
            fin_data = old_entry.get("financials") or {}
            if not isinstance(fin_data, dict):
                fin_data = {}
            traction = fin_data.get("traction_metrics")
            funding = fin_data.get("funding_history")
            valuation = fin_data.get("valuation_est")
            ip_status = fin_data.get("ip_status")
            financials = Financials(
                traction_metrics=traction,
                funding_history=funding,
                valuation_est=valuation,
                ip_status=ip_status,
                revenue_missing=not bool(traction) or fin_data.get("revenue_missing", False),
                funding_missing=not bool(funding) or fin_data.get("funding_missing", False),
                valuation_missing=not bool(valuation) or fin_data.get("valuation_missing", False),
            )

            startup = Startup(
                startup_id=scout_info.startup_id,
                scout_info=scout_info,
                review_info=None,
                partner_info=None,
                financials=financials,
            )
            if old_entry.get("created_at"):
                startup.created_at = _parse_ts(old_entry["created_at"])
            if old_entry.get("updated_at"):
                startup.updated_at = _parse_ts(old_entry["updated_at"])

            review_data = old_entry.get("review")
            if review_data:
                if not review_data.get("key_risks"):
                    logger.warning(f"Entry {entry_id}: missing key_risks (critical for Partner rules)")
                reviewed_at = _parse_ts(timestamps.get("reviewed_at"))
                review_info = ReviewInfo(
                    market_score=int(review_data.get("market_score", 5)),
                    product_score=int(review_data.get("product_score", 5)),
                    technical_score=int(review_data.get("technical_score", 5)),
                    execution_score=int(review_data.get("execution_score", 5)),
                    defensibility_score=review_data.get("defensibility_score"),
                    overall_summary=review_data.get("overall_summary", ""),
                    key_risks=review_data.get("key_risks", []),
                    verdict=review_data.get("verdict", "MEDIUM"),
                    diligence_red_flags=review_data.get("diligence_red_flags", []),
                    assumption_feedback=review_data.get("assumption_feedback") or [],
                    reviewer_agent_id=review_data.get("reviewer_agent_id"),
                    reviewed_at=reviewed_at,
                    team_analysis=review_data.get("team_analysis") or None,
                    competition_analysis=review_data.get("competition_analysis") or None,
                    business_model_analysis=review_data.get("business_model_analysis") or None,
                    investment_thesis=review_data.get("investment_thesis") or None,
                    risk_mitigation=review_data.get("risk_mitigation") or None,
                    score_reasoning=review_data.get("score_reasoning") or None,
                )
                startup.review_info = review_info

            partner_data = old_entry.get("partner")
            if partner_data:
                old_decision = partner_data.get("decision", "PASS")
                new_decision = PARTNER_DECISION_MAP.get(old_decision, "NO")
                if old_decision not in ("YES", "NO", "MAYBE"):
                    new_decision = PARTNER_DECISION_MAP.get(old_decision, "NO")
                conviction = partner_data.get("conviction_level") or partner_data.get("confidence", 5)
                conviction = max(1, min(10, int(conviction)))
                partnered_at = _parse_ts(timestamps.get("partnered_at"))
                partner_info = PartnerInfo(
                    decision=new_decision,
                    rationale=partner_data.get("rationale", ""),
                    next_action=partner_data.get("next_action", ""),
                    conviction_level=conviction,
                    human_review_required=partner_data.get("human_review_required", False),
                    partner_agent_id=partner_data.get("partner_agent_id"),
                    partnered_at=partnered_at,
                )
                startup.partner_info = partner_info

            migrated.append(startup.to_dict())
            migrated_count += 1

        except Exception as e:
            logger.error(f"Error migrating entry {entry_id}: {e}", exc_info=True)
            continue

    if migrated:
        new_storage.replace_all(migrated)
    logger.info(f"Migrated {migrated_count}/{len(old_entries)} entries")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_old_to_new("data/discoveries.json", "data/startups.json")
