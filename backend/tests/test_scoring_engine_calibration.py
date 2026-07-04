"""Integration tests: wiring the evidence discount (1A) + gate (1B) into the engine.

Calibration is opt-in. When off (default) the published scores are unchanged and the
calibrated values are emitted in a `calibration` shadow block for offline comparison.
When on, the discounted/gated values are published.
"""
from services.scoring.scoring_engine import DeterministicScoringEngine


# A 'strong' network-effects signal asserted at low confidence (the Issue-1 artifact).
LOW_CONF_SCOUT = {"name": "NascentCo", "sector": "devtools", "solution": "Some solution"}
LOW_CONF_REVIEW = {
    "structured_signals": {
        "defensibility": {"network_effects": {"label": "strong", "confidence": 0.2, "reasoning": "x"}}
    }
}

# A 'strong' signal asserted at HIGH confidence but as the ONLY evidenced component in its
# dimension (completeness 1/5 = 0.2): the discount keeps the score (confidence is high) but
# the evidence-sufficiency gate must cap the thinly-covered dimension.
THIN_COVERAGE_SCOUT = {"name": "OneSignalCo", "sector": "devtools", "solution": ""}
THIN_COVERAGE_REVIEW = {
    "structured_signals": {
        "defensibility": {"network_effects": {"label": "strong", "confidence": 0.9, "reasoning": "x"}}
    }
}


def test_low_confidence_subscore_is_discounted_when_calibration_on():
    engine = DeterministicScoringEngine(evidence_calibration=True)
    result = engine.score(LOW_CONF_SCOUT, LOW_CONF_REVIEW)
    ne = result["defensibility"]["components"]["network_effects"]
    # strong -> 10.0 raw, but confidence 0.2 (<= floor) collapses it to the 5.0 baseline.
    assert ne["score"] == 5.0


def test_thinly_covered_dimension_is_capped_when_calibration_on():
    engine = DeterministicScoringEngine(evidence_calibration=True)
    result = engine.score(THIN_COVERAGE_SCOUT, THIN_COVERAGE_REVIEW)
    defn = result["defensibility"]
    assert defn["evidence_capped"] is True
    assert defn["score"] <= 6.0


def test_calibration_off_leaves_published_scores_unchanged_but_emits_shadow():
    raw = DeterministicScoringEngine(evidence_calibration=False)
    result = raw.score(LOW_CONF_SCOUT, LOW_CONF_REVIEW)
    # Published value is the current (undiscounted) behavior.
    assert result["defensibility"]["components"]["network_effects"]["score"] == 10.0
    # The calibrated shadow is always computed so we can diff before flipping the flag.
    assert "calibration" in result
    assert "overall_score" in result["calibration"]
    assert result["defensibility"]["components"]["network_effects"].get("evidence_capped") is None
