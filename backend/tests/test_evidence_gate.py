"""Unit tests for the evidence-sufficiency gate (Issue 1, fix 1B).

A dimension score is capped at EVIDENCE_GATE['cap'] unless enough of its components are
actually evidenced (completeness) at a high enough average confidence. This stops a
couple of strong-sounding but thinly-evidenced signals from aggregating into a "Strong"
dimension. Returns (gated_score, capped: bool).
"""
from config.scoring_config import EVIDENCE_GATE
from services.scoring.confidence_discount import apply_evidence_gate

CAP = EVIDENCE_GATE["cap"]


def test_well_evidenced_high_score_passes_through():
    score, capped = apply_evidence_gate(8.5, completeness=0.8, avg_confidence=0.7)
    assert score == 8.5
    assert capped is False


def test_thin_completeness_caps_the_score():
    # Only 1 of 5 components evidenced (0.2 < 0.4) => capped even at high confidence.
    score, capped = apply_evidence_gate(9.0, completeness=0.2, avg_confidence=0.9)
    assert score == CAP
    assert capped is True


def test_low_confidence_caps_the_score():
    score, capped = apply_evidence_gate(9.0, completeness=1.0, avg_confidence=0.2)
    assert score == CAP
    assert capped is True


def test_score_below_cap_is_never_raised_and_not_flagged():
    # The gate only ever caps; a low score with thin evidence stays low and is not
    # marked capped (capping a 4 to 6 would be inventing optimism).
    score, capped = apply_evidence_gate(4.0, completeness=0.2, avg_confidence=0.1)
    assert score == 4.0
    assert capped is False


def test_score_at_cap_with_thin_evidence_is_not_flagged():
    # Exactly at the cap means no change was applied, so nothing to flag.
    score, capped = apply_evidence_gate(CAP, completeness=0.2, avg_confidence=0.1)
    assert score == CAP
    assert capped is False
