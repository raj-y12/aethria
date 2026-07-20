"""
Canonical mapping between legacy portfolio/partner codes (YES/NO/MAYBE) and API/storage
recommendations (INVEST/PASS/MONITOR). Single source of truth for cross-layer consistency.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


class RecommendationCode(str, Enum):
    """Institutional system recommendation; it is not a human fund ruling."""

    ADVANCE = "ADVANCE"
    MONITOR = "MONITOR"
    PASS = "PASS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class HumanRulingCode(str, Enum):
    """Explicit operator/fund ruling."""

    ADVANCE = "ADVANCE"
    MONITOR = "MONITOR"
    PASS = "PASS"
    INVEST = "INVEST"


class LegacyProjection(BaseModel):
    """A deliberately visible, potentially lossy legacy projection."""

    value: str
    compatibility_reason: Optional[str] = None

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

LEGACY_PARTNER_TO_INSTITUTIONAL: Dict[str, RecommendationCode] = {
    "INVEST": RecommendationCode.ADVANCE,
    "MONITOR": RecommendationCode.MONITOR,
    "PASS": RecommendationCode.PASS,
}

LEGACY_RULING_TO_INSTITUTIONAL: Dict[str, HumanRulingCode] = {
    "YES": HumanRulingCode.INVEST,
    "MAYBE": HumanRulingCode.MONITOR,
    "NO": HumanRulingCode.PASS,
}


def _required_code(value: Optional[str], *, label: str) -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        raise ValueError(f"Unknown {label}: {value!r}")
    return normalized


def institutional_recommendation_from_legacy_partner(
    recommendation: str,
) -> RecommendationCode:
    normalized = _required_code(recommendation, label="legacy partner recommendation")
    try:
        return LEGACY_PARTNER_TO_INSTITUTIONAL[normalized]
    except KeyError as exc:
        raise ValueError(
            f"Unknown legacy partner recommendation: {recommendation!r}"
        ) from exc


def legacy_partner_from_institutional_recommendation(
    recommendation: str,
) -> LegacyProjection:
    normalized = _required_code(recommendation, label="institutional recommendation")
    try:
        code = RecommendationCode(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Unknown institutional recommendation: {recommendation!r}"
        ) from exc
    if code is RecommendationCode.ADVANCE:
        return LegacyProjection(value="MONITOR", compatibility_reason="advance")
    if code is RecommendationCode.INSUFFICIENT_EVIDENCE:
        return LegacyProjection(
            value="MONITOR", compatibility_reason="insufficient_evidence"
        )
    return LegacyProjection(value=code.value)


def institutional_ruling_from_legacy(ruling: str) -> HumanRulingCode:
    normalized = _required_code(ruling, label="legacy human ruling")
    try:
        return LEGACY_RULING_TO_INSTITUTIONAL[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown legacy human ruling: {ruling!r}") from exc


def legacy_ruling_from_institutional(ruling: str) -> LegacyProjection:
    normalized = _required_code(ruling, label="institutional human ruling")
    try:
        code = HumanRulingCode(normalized)
    except ValueError as exc:
        raise ValueError(f"Unknown institutional human ruling: {ruling!r}") from exc
    if code is HumanRulingCode.ADVANCE:
        return LegacyProjection(value="MAYBE", compatibility_reason="advance")
    if code is HumanRulingCode.MONITOR:
        return LegacyProjection(value="MAYBE")
    if code is HumanRulingCode.PASS:
        return LegacyProjection(value="NO")
    return LegacyProjection(value="YES")


def ruling_aligns_with_recommendation(
    recommendation: Optional[str], ruling: str
) -> bool:
    if recommendation is None or not str(recommendation).strip():
        return True
    rec = RecommendationCode(_required_code(recommendation, label="recommendation"))
    human = HumanRulingCode(_required_code(ruling, label="human ruling"))
    if rec is RecommendationCode.ADVANCE:
        return human in {HumanRulingCode.ADVANCE, HumanRulingCode.INVEST}
    if rec is RecommendationCode.MONITOR:
        return human is HumanRulingCode.MONITOR
    if rec is RecommendationCode.PASS:
        return human is HumanRulingCode.PASS
    return False


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
