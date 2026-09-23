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
