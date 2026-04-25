"""
Canonical scoring helpers for reviewer and memo layers.

Primary score is always the average of the 4 core dimensions:
market, product, technical, execution.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple


CORE_SCORE_FIELDS: Tuple[str, ...] = (
    "market_score",
    "product_score",
    "technical_score",
    "execution_score",
)

DEFAULT_SCORE_SOURCE = (
    "Aggregated from multiple reviewer perspectives (optimistic, neutral, skeptical)"
)


def _to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_to_label(score: float) -> str:
    if score >= 9:
        return "Exceptional"
    if score >= 7:
        return "Strong"
    if score >= 5:
        return "Moderate"
    return "Weak"


def compute_overall_score(source: Dict[str, object]) -> Optional[float]:
    values = []
    for field in CORE_SCORE_FIELDS:
        num = _to_float(source.get(field))
        if num is not None:
            values.append(num)
    if len(values) != len(CORE_SCORE_FIELDS):
        return None
    return sum(values) / len(values)


def get_dimension_with_label(score: Optional[float]) -> Dict[str, Optional[object]]:
    if score is None:
        return {"score": None, "label": None}
    return {"score": score, "label": score_to_label(score)}


def enrich_scores(payload: Dict[str, object]) -> Dict[str, object]:
    """
    Return a shallow copy containing:
    - overall_score
    - overall_label
    - per-dimension labels under <dim>_label
    """
    out = dict(payload)
    overall = compute_overall_score(out)
    out["overall_score"] = overall
    out["overall_label"] = score_to_label(overall) if overall is not None else None
    for field in CORE_SCORE_FIELDS + ("defensibility_score",):
        score = _to_float(out.get(field))
        out[f"{field}_label"] = score_to_label(score) if score is not None else None
    return out

