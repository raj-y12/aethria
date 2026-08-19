"""Regression coverage: agent_config.decision_threshold validation, added
alongside the triage-funnel settings UI (2026-08-19) so the Partner decision
gate (backend/partner/engine.py) is configurable the same way
confidence_threshold already was."""

from api import _validate_settings


def test_decision_threshold_accepts_valid_fraction():
    assert _validate_settings({"agent_config": {"decision_threshold": 0.55}}) == []


def test_decision_threshold_rejects_out_of_range_number():
    errors = _validate_settings({"agent_config": {"decision_threshold": 1.5}})
    assert any("decision_threshold" in e for e in errors)


def test_decision_threshold_rejects_non_numeric_non_string():
    errors = _validate_settings({"agent_config": {"decision_threshold": [0.5]}})
    assert any("decision_threshold" in e for e in errors)


def test_decision_threshold_accepts_string_override():
    # confidence_threshold already accepts a string (e.g. a calibration
    # override token); decision_threshold mirrors that exactly.
    assert _validate_settings({"agent_config": {"decision_threshold": "0.55"}}) == []
