"""
Canonical 1–10 score band semantics aligned with the active evaluation rubric
and app-front-end semantics.

Use for: memo prose, API additive rubric fields, any surface that must match Weak/Concerning/Promising/Strong.

Note: `utils.scoring.score_to_label` remains the legacy compact ladder (Exceptional/Strong/Moderate/Weak)
for existing `overall_label` / `*_label` fields — do not change those without a versioned migration.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

# (low, high, label) — inclusive bounds, 1–10 scale
RUBRIC_SCORE_BANDS: List[Tuple[int, int, str]] = [
    (1, 3, "Weak"),
    (4, 5, "Concerning"),
    (6, 7, "Promising"),
    (8, 10, "Strong"),
]


def rubric_band_for_int(score: int) -> str:
    """Map an integer 1–10 score to rubric band label; out-of-range returns em dash."""
    for lo, hi, label in RUBRIC_SCORE_BANDS:
        if lo <= score <= hi:
            return label
    return "—"


def rubric_band_for_numeric(score: Optional[float]) -> Optional[str]:
    """Map a numeric score to rubric band; None if missing or non-finite."""
    if score is None:
        return None
    try:
        bounded = max(1, min(10, int(round(float(score)))))
    except (TypeError, ValueError):
        return None
    return rubric_band_for_int(bounded)


def rubric_score_bands_markdown_footnote() -> str:
    """Standard memo footnote for score band legend."""
    return "*1–3: Weak · 4–5: Concerning · 6–7: Promising · 8–10: Strong*"
