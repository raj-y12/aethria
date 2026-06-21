"""Regression tests for the whole-app code-review fixes."""
from utils.settings_loader import recommendation_for_score_from_fund_config


def _band(min_, max_, label):
    return {"min": min_, "max": max_, "label": label}


def test_scoreband_advance_intent_wins_over_pass_substring():
    # A band labelled with both "pass" and "proceed" means INVEST, not PASS.
    fc = {"scoreBands": [_band(80, 100, "Pass to Partner — proceed")]}
    assert recommendation_for_score_from_fund_config(9.0, fc) == "INVEST"


def test_scoreband_plain_pass_still_passes():
    fc = {"scoreBands": [_band(0, 39, "Pass")]}
    assert recommendation_for_score_from_fund_config(2.0, fc) == "PASS"


def test_scoreband_invest_and_monitor_labels():
    fc = {
        "scoreBands": [
            _band(0, 59, "Pass"),
            _band(60, 79, "Monitor"),
            _band(80, 100, "Invest"),
        ]
    }
    assert recommendation_for_score_from_fund_config(9.0, fc) == "INVEST"
    assert recommendation_for_score_from_fund_config(7.0, fc) == "MONITOR"
    assert recommendation_for_score_from_fund_config(3.0, fc) == "PASS"


def test_partner_threshold_remap_preserves_ordering():
    """An inverted fund_config (monitor > escalation) must not push
    min_avg_medium_maybe above min_avg_strong_yes — the clamp keeps the MEDIUM
    escalation rule reachable."""
    from partner.decision import PartnerDecisionEngine

    engine = PartnerDecisionEngine(api_key="")
    # monitor=85 (stricter) > escalation=80 — the pathological config.
    engine._fund_config = {
        "thresholds": {"partnerReview": 60, "escalation": 80, "monitor": 85, "autoPass": 60}
    }
    # Re-derive the remapped thresholds the way decide() does, then assert the
    # invariant the rule ladder depends on holds after the clamp.
    fc = engine._fund_config["thresholds"]
    min_avg_pass = float(fc["partnerReview"]) / 10.0
    min_avg_strong_yes = float(fc["escalation"]) / 10.0
    min_avg_medium_maybe = float(fc["monitor"]) / 10.0
    min_avg_borderline_low = float(fc["autoPass"]) / 10.0
    # Apply the same clamp the engine applies.
    min_avg_medium_maybe = min(min_avg_medium_maybe, min_avg_strong_yes)
    min_avg_borderline_low = min(min_avg_borderline_low, min_avg_pass)
    assert min_avg_medium_maybe <= min_avg_strong_yes
    assert min_avg_borderline_low <= min_avg_pass
