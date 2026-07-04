"""Evidence-confidence discount (Issue 1, fix 1A).

Shrinks a normalized component score toward the neutral baseline as its evidence
confidence falls. Below `floor_conf` the score collapses to the baseline (a strong-
sounding label on no evidence is worth nothing more than "unproven"); above `full_conf`
the score is taken at face value; in between it regresses linearly toward the baseline.

Pure and deterministic — no I/O, no config beyond the band constants — so it is trivially
unit-tested and replayable. Band constants live in config.scoring_config so they can be
tuned (and later swept by a validation harness) without code changes.
"""
from __future__ import annotations

from typing import Any

from config.scoring_config import DEFAULT_SCORE, EVIDENCE_DISCOUNT, EVIDENCE_GATE


def confidence_shrink_factor(confidence: Any) -> float:
    """Map evidence confidence to a shrink factor in [0, 1]: 0 = collapse to baseline,
    1 = keep the score as-is. None/garbage confidence is treated as fully uncertain (0)."""
    floor = float(EVIDENCE_DISCOUNT["floor_conf"])
    full = float(EVIDENCE_DISCOUNT["full_conf"])
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 0.0
    if full <= floor:
        return 1.0 if c >= full else 0.0
    return max(0.0, min(1.0, (c - floor) / (full - floor)))


def confidence_discounted_score(raw_score: float, confidence: Any) -> float:
    """Regress `raw_score` toward DEFAULT_SCORE by the confidence shrink factor."""
    factor = confidence_shrink_factor(confidence)
    return DEFAULT_SCORE + (float(raw_score) - DEFAULT_SCORE) * factor


def apply_evidence_gate(
    score: float, completeness: float, avg_confidence: float
) -> tuple[float, bool]:
    """Cap a dimension score at EVIDENCE_GATE['cap'] when its evidence is insufficient.

    The gate only ever caps (never raises): a low score on thin evidence stays low. A
    score that is already at/below the cap is returned unflagged because nothing changed.
    Returns (gated_score, capped).
    """
    cap = float(EVIDENCE_GATE["cap"])
    min_completeness = float(EVIDENCE_GATE["min_completeness"])
    min_avg_conf = float(EVIDENCE_GATE["min_avg_conf"])
    try:
        s = float(score)
    except (TypeError, ValueError):
        return DEFAULT_SCORE, False
    insufficient = (float(completeness) < min_completeness) or (float(avg_confidence) < min_avg_conf)
    if insufficient and s > cap:
        return cap, True
    return s, False
