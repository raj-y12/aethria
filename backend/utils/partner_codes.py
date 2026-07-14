"""
Canonical mapping between legacy portfolio/partner codes (YES/NO/MAYBE) and API/storage
recommendations (INVEST/PASS/MONITOR). Single source of truth for cross-layer consistency.
"""
from __future__ import annotations

from typing import Dict, Optional

LEGACY_TO_RECOMMENDATION: Dict[str, str] = {
    "YES": "INVEST",
    "NO": "PASS",
    "MAYBE": "MONITOR",
}

RECOMMENDATION_TO_LEGACY: Dict[str, str] = {
    "INVEST": "YES",
    "PASS": "NO",
    "MONITOR": "MAYBE",
}


def recommendation_from_legacy(
    legacy: Optional[str],
    *,
    default_if_unknown: Optional[str] = None,
) -> Optional[str]:
    """
    Map YES/NO/MAYBE -> INVEST/PASS/MONITOR.
    Empty/missing legacy returns default_if_unknown.
    Unknown non-empty legacy returns default_if_unknown (same as missing default).
    """
    if legacy is None:
        return default_if_unknown
    u = str(legacy).strip().upper()
    if not u:
        return default_if_unknown
    return LEGACY_TO_RECOMMENDATION.get(u, default_if_unknown)


def legacy_from_recommendation(recommendation: str) -> str:
    """Map INVEST/PASS/MONITOR -> YES/NO/MAYBE; unknown values default to MAYBE."""
    r = (recommendation or "").strip().upper()
    return RECOMMENDATION_TO_LEGACY.get(r, "MAYBE")


def normalize_recommendation(value: Optional[str]) -> Optional[str]:
    """Return a canonical recommendation for canonical or legacy input."""
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized in RECOMMENDATION_TO_LEGACY:
        return normalized
    return LEGACY_TO_RECOMMENDATION.get(normalized)
