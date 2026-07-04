"""Unit tests for the evidence-confidence discount (Issue 1, fix 1A).

A component's normalized score is shrunk toward the neutral baseline (DEFAULT_SCORE)
as its evidence confidence falls. This is Bayesian-style shrinkage toward the prior:
low confidence => the score regresses to "unproven", regardless of how strong the label
sounds. This is what stops a `strong`/0.2 signal from publishing a 10.
"""
import math

from config.scoring_config import DEFAULT_SCORE
from services.scoring.confidence_discount import confidence_discounted_score


def test_full_confidence_leaves_score_unchanged():
    assert confidence_discounted_score(10.0, 0.8) == 10.0
    assert confidence_discounted_score(2.0, 0.95) == 2.0


def test_floor_confidence_collapses_to_baseline():
    # confidence <= floor => fully shrunk to the neutral baseline, label notwithstanding.
    assert confidence_discounted_score(10.0, 0.2) == DEFAULT_SCORE
    assert confidence_discounted_score(2.0, 0.0) == DEFAULT_SCORE


def test_midpoint_confidence_is_halfway_to_baseline():
    # confidence halfway through the [floor, full] band => score halfway to baseline.
    # floor=0.2, full=0.8 => midpoint 0.5, shrink factor 0.5.
    assert confidence_discounted_score(10.0, 0.5) == DEFAULT_SCORE + (10.0 - DEFAULT_SCORE) * 0.5
    assert confidence_discounted_score(3.0, 0.5) == DEFAULT_SCORE + (3.0 - DEFAULT_SCORE) * 0.5


def test_baseline_score_is_invariant_to_confidence():
    for c in (0.0, 0.2, 0.5, 0.8, 1.0):
        assert confidence_discounted_score(DEFAULT_SCORE, c) == DEFAULT_SCORE


def test_shrink_is_symmetric_toward_baseline():
    # A weak label on thin evidence is pulled UP toward neutral, same as a strong one is
    # pulled down — uncertainty regresses to the prior in both directions.
    high = confidence_discounted_score(10.0, 0.35)
    low = confidence_discounted_score(0.0, 0.35)
    assert math.isclose(high - DEFAULT_SCORE, DEFAULT_SCORE - low, rel_tol=1e-9)


def test_none_or_bad_confidence_is_treated_as_low():
    # Missing/garbage confidence must not silently grant full credit.
    assert confidence_discounted_score(10.0, None) == DEFAULT_SCORE
    assert confidence_discounted_score(10.0, "oops") == DEFAULT_SCORE
