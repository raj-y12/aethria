"""Map canonical startup snapshots into the legacy portfolio read shape."""

from __future__ import annotations

from typing import Any

from portfolio.schemas import StartupRecord


def _text(value: Any) -> str:
    return str(value or "").strip()


def canonical_startup_record(row: dict[str, Any]) -> StartupRecord:
    scout = row.get("scout_info") if isinstance(row.get("scout_info"), dict) else {}
    startup_id = _text(row.get("startup_id"))
    metadata = dict(scout.get("metadata") or {}) if isinstance(scout.get("metadata"), dict) else {}
    metadata.setdefault("source", "canonical_startups")
    metadata.setdefault("canonical_startup_id", startup_id)
    discovered_at = (
        scout.get("discovered_at")
        or row.get("first_seen_at")
        or row.get("created_at")
        or ""
    )
    if hasattr(discovered_at, "isoformat"):
        discovered_at = discovered_at.isoformat()
    confidence = scout.get("confidence_score", scout.get("confidence", 0.0))
    try:
        confidence = float(confidence or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "id": startup_id,
        "startup_id": startup_id,
        "name": _text(scout.get("name")),
        "one_line": _text(scout.get("one_line")),
        "sector": _text(scout.get("sector")),
        "problem": _text(scout.get("problem")),
        "solution": _text(scout.get("solution")),
        "target_users": _text(scout.get("target_users")),
        "why_now": _text(scout.get("why_now")),
        "scout_type": _text(scout.get("scout_type")),
        "scout_confidence": confidence,
        "discovered_at": str(discovered_at),
        "version": int(row.get("version") or 1),
        "metadata": metadata,
    }
