"""Deterministic normalization for extracted structured signals."""

from __future__ import annotations

import re
from typing import Any, Optional

from config.scoring_config import DEFAULT_SCORE, THRESHOLDS


def _clamp(score: float) -> float:
    return max(0.0, min(10.0, float(score)))


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def normalize_tam(value: Any) -> float:
    if value is None:
        return DEFAULT_SCORE
    text = str(value).strip().lower()
    if not text:
        return DEFAULT_SCORE
    number = _parse_float(text)
    if number is None:
        return DEFAULT_SCORE
    multiplier = 1.0
    if any(token in text for token in ("tn", "trillion")) or re.search(r"\d\s*t\b|\d+t\b", text):
        multiplier = 1_000_000_000_000
    elif any(token in text for token in ("bn", "billion")) or re.search(r"\d\s*b\b|\d+b\b", text):
        multiplier = 1_000_000_000
    elif any(token in text for token in ("mn", "million")) or re.search(r"\d\s*m\b|\d+m\b", text):
        multiplier = 1_000_000
    elif any(token in text for token in ("k", "thousand")):
        multiplier = 1_000
    usd = number * multiplier
    t = THRESHOLDS["tam_usd"]
    if usd >= t["xl"]:
        return 10.0
    if usd >= t["large"]:
        return 8.5
    if usd >= t["mid"]:
        return 7.0
    if usd >= t["small"]:
        return 5.5
    return 4.0


def normalize_growth(value: Any) -> float:
    pct = _parse_float(value)
    if pct is None:
        return DEFAULT_SCORE
    t = THRESHOLDS["growth_pct"]
    if pct >= t["hyper"]:
        return 10.0
    if pct >= t["strong"]:
        return 8.5
    if pct >= t["healthy"]:
        return 7.0
    if pct >= t["slow"]:
        return 5.5
    return 4.0


_LABEL_SYNONYMS: dict[str, str] = {
    "rapid": "fast",
    "explosive": "hyper",
    "very_high": "high",
    "very high": "high",
    "extremely_high": "extreme",
    "extremely high": "extreme",
    "significant": "strong",
    "substantial": "strong",
    "established": "recognized",
    "nascent": "emerging",
    "lightweight": "simple",
    "sophisticated": "complex",
    "advanced": "mature",
    "solid": "strong",
    "excellent": "strong",
    "minimal": "low",
    "top": "elite",
    "world_class": "elite",
    "world class": "elite",
    "considerable": "high",
    "dominant": "very_high",
    "unmatched": "extreme",
    "proven": "credible_team",
    "experienced": "credible_team",
    "pre_revenue": "early_adoption",
    "pre-revenue": "early_adoption",
    "seed": "early_adoption",
    "growth": "scaling",
}


# Sentinel returned when a label is outside the recognized vocabulary for a component.
# NaN is used so it propagates as "not a real score"; the scoring engine detects it and
# treats the component as no-evidence (excluded from aggregation) rather than silently
# scoring an unrecognized label as a neutral 5.0 (audit C2 / off-vocabulary).
UNRECOGNIZED_LABEL = float("nan")


def is_unrecognized(score: float) -> bool:
    return score != score  # NaN is the only value not equal to itself


def _map_label(value: Any, mapping: dict[str, float]) -> float:
    if value is None:
        return DEFAULT_SCORE
    key = str(value).strip().lower()
    if not key:
        return DEFAULT_SCORE
    if key in mapping:
        return _clamp(mapping[key])
    resolved = _LABEL_SYNONYMS.get(key)
    if resolved and resolved in mapping:
        return _clamp(mapping[resolved])
    return UNRECOGNIZED_LABEL


def normalize_urgency(label: Any) -> float:
    return _map_label(
        label,
        {
            "critical": 9.5,
            "very_high": 9.0,
            "high": 8.0,
            "important": 7.0,
            "medium": 6.0,
            "low": 4.5,
            "none": 3.0,
        },
    )


def normalize_timing(label: Any) -> float:
    return _map_label(
        label,
        {
            "perfect": 9.5,
            "excellent": 9.0,
            "favorable": 8.0,
            "good": 7.0,
            "neutral": 5.5,
            "unclear": 5.0,
            "poor": 3.5,
        },
    )


def normalize_competition(label: Any) -> float:
    return _map_label(
        label,
        {
            "fragmented": 8.5,
            "moderate": 7.0,
            "crowded": 5.0,
            "intense": 4.0,
            "winner_take_all": 3.5,
            "unknown": 5.0,
        },
    )


def normalize_confidence_label(label: Any) -> float:
    return _map_label(label, {"high": 8.5, "medium": 6.0, "low": 4.0})


def normalize_traction(label: Any) -> float:
    return _map_label(
        label,
        {
            "pre-product": 2,
            "mvp": 4,
            "early_adoption": 5,
            "early_revenue": 6,
            "scaling": 8,
            "strong_scale": 10,
            "missing": 5,
        },
    )


def normalize_growth_velocity(value_or_label: Any) -> float:
    pct = _parse_float(value_or_label)
    if pct is not None:
        if pct >= 60:
            return 10.0
        if pct >= 35:
            return 8.0
        if pct >= 15:
            return 6.0
        if pct >= 5:
            return 4.0
        return 2.0
    return _map_label(value_or_label, {"flat": 2, "slow": 4, "moderate": 6, "fast": 8, "hyper": 10})


def normalize_gtm(label: Any) -> float:
    return _map_label(label, {"unclear": 3, "some_channels": 6, "repeatable": 8, "strong_edge": 10})


def normalize_team_execution(label: Any) -> float:
    return _map_label(label, {"weak": 3, "decent": 6, "credible_team": 7, "strong": 8, "elite": 10})


def normalize_operational_velocity(label: Any) -> float:
    return _map_label(label, {"slow": 3, "moderate": 6, "fast": 8, "exceptional": 10})


def normalize_value_prop(label: Any) -> float:
    return _map_label(label, {"vague": 3, "understandable": 6, "clear": 8, "exceptional": 10})


def normalize_pain_alignment(label: Any) -> float:
    return _map_label(label, {"weak": 3, "moderate": 6, "strong": 8, "critical": 10})


def normalize_differentiation(label: Any) -> float:
    return _map_label(label, {"none": 2, "slight": 5, "clear": 7, "strong": 9})


def normalize_ux(label: Any) -> float:
    return _map_label(label, {"clunky": 3, "usable": 6, "smooth": 8, "exceptional": 10})


def normalize_retention(value_or_label: Any) -> float:
    pct = _parse_float(value_or_label)
    if pct is not None:
        if pct >= 80:
            return 10.0
        if pct >= 65:
            return 8.0
        if pct >= 45:
            return 6.0
        return 4.0
    return _map_label(value_or_label, {"missing": 5, "weak": 4, "moderate": 6, "strong": 8, "very_strong": 10})


def normalize_complexity(label: Any) -> float:
    return _map_label(label, {"simple": 3, "moderate": 6, "complex": 8, "deeptech": 10})


def normalize_engineering_quality(label: Any) -> float:
    return _map_label(label, {"weak": 3, "decent": 6, "strong": 8, "elite": 10})


def normalize_scalability(label: Any) -> float:
    return _map_label(label, {"low": 3, "medium": 6, "high": 8, "extreme": 10})


def normalize_data_advantage(label: Any) -> float:
    return _map_label(label, {"none": 2, "limited": 5, "growing": 7, "strong": 10})


def normalize_architecture(label: Any) -> float:
    return _map_label(label, {"prototype": 3, "early": 6, "mature": 8, "robust": 10})


def normalize_network_effects(label: Any) -> float:
    return _map_label(label, {"none": 2, "weak": 5, "moderate": 7, "strong": 10})


def normalize_switching_costs(label: Any) -> float:
    return _map_label(label, {"low": 3, "medium": 6, "high": 8, "very_high": 10})


def normalize_proprietary_data(label: Any) -> float:
    return _map_label(label, {"none": 2, "some": 5, "strong": 8, "dominant": 10})


def normalize_barriers(label: Any) -> float:
    return _map_label(label, {"easy": 2, "some": 5, "hard": 8, "very_hard": 10})


def normalize_brand(label: Any) -> float:
    return _map_label(label, {"unknown": 3, "emerging": 6, "recognized": 8, "leader": 10})
