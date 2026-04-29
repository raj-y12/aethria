"""
Lightweight resolution when reviewer personas diverge on dimension scores.

Pulls high-spread dimensions toward a conservative blend and emits audit notes.
Pure functions — no I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Minimum integer spread across personas before adjusting the primary blend.
_SPREAD_THRESHOLD = 2
# Weight on the persona minimum when resolving (remainder on mean).
_CONSERVATIVE_MIN_WEIGHT = 0.45


def apply_resolution_to_primary(primary: Dict[str, Any], all_results: List[Dict[str, Any]]) -> Tuple[List[str], Optional[str]]:
    """
    Mutate primary dimension scores when cross-persona spread is high.

    Baseline blend (mean / weighted defensibility) should already be applied.

    Returns:
        (resolution_notes, disagreement_summary)
    """
    notes: List[str] = []
    max_spread = 0

    core_dims = ["market_score", "product_score", "technical_score", "execution_score"]
    for d in core_dims:
        vals = _int_scores(all_results, d)
        if len(vals) < 2:
            continue
        spread = max(vals) - min(vals)
        max_spread = max(max_spread, spread)
        if spread < _SPREAD_THRESHOLD:
            continue
        mean_v = sum(vals) / len(vals)
        min_v = float(min(vals))
        resolved = int(round((1.0 - _CONSERVATIVE_MIN_WEIGHT) * mean_v + _CONSERVATIVE_MIN_WEIGHT * min_v))
        resolved = max(1, min(10, resolved))
        old = primary.get(d)
        primary[d] = resolved
        notes.append(
            f"{d}: personas diverged (spread {spread}); resolved to conservative blend {resolved}"
            + (f" (prior blend {old})." if old is not None else ".")
        )

    ds_vals = _int_scores(all_results, "defensibility_score")
    if len(ds_vals) >= 2:
        spread = max(ds_vals) - min(ds_vals)
        max_spread = max(max_spread, spread)
        if spread >= _SPREAD_THRESHOLD:
            mean_v = sum(ds_vals) / len(ds_vals)
            min_v = float(min(ds_vals))
            resolved = int(round((1.0 - _CONSERVATIVE_MIN_WEIGHT) * mean_v + _CONSERVATIVE_MIN_WEIGHT * min_v))
            resolved = max(1, min(10, resolved))
            old = primary.get("defensibility_score")
            primary["defensibility_score"] = resolved
            notes.append(
                f"defensibility_score: personas diverged (spread {spread}); resolved to {resolved}"
                + (f" (prior blend {old})." if old is not None else ".")
            )

    disagreement_summary: Optional[str] = None
    if notes:
        disagreement_summary = (
            f"Material reviewer disagreement (max spread {max_spread}); "
            "primary scores adjusted toward conservative resolution where spread exceeded threshold."
        )
    elif max_spread >= 1:
        disagreement_summary = (
            f"Moderate spread across personas (max {max_spread}); primary scores use standard blend."
        )

    return notes, disagreement_summary


def _int_scores(results: List[Dict[str, Any]], key: str) -> List[int]:
    out: List[int] = []
    for r in results:
        v = r.get(key)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.append(int(round(float(v))))
    return out
