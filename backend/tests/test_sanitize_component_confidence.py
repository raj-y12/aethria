"""Regression tests for _sanitize_component confidence/value preservation (Issue 1 root cause).

The reviewer emits each signal as EITHER label-only OR value-only (see
base._normalize_structured_signals_contract). The sanitizer must keep the provided
confidence (and the provided value) for those valid shapes, and only force the low-
confidence missing placeholder when the component genuinely carries no evidence.
"""
from services.scoring.extraction_layer import _sanitize_component


def test_label_only_signal_preserves_confidence():
    out = _sanitize_component({"label": "strong", "confidence": 0.9, "reasoning": "x"})
    assert out["label"] == "strong"
    assert out["confidence"] == 0.9


def test_value_only_signal_preserves_value_and_confidence():
    out = _sanitize_component({"value": "5B", "confidence": 0.8, "reasoning": "y"})
    assert out["value"] == "5B"
    assert out["confidence"] == 0.8


def test_missing_label_token_is_dropped_to_low_confidence():
    out = _sanitize_component({"label": "[MISSING]", "confidence": 0.9})
    assert "label" not in out
    assert out["value"] is None
    assert out["confidence"] == 0.2


def test_missing_value_token_is_nulled_to_low_confidence():
    out = _sanitize_component({"value": "[MISSING: tam]", "confidence": 0.9})
    assert out["value"] is None
    assert out["confidence"] == 0.2


def test_genuinely_empty_component_is_low_confidence():
    out = _sanitize_component({"reasoning": "nothing extracted"})
    assert out.get("label") is None
    assert out["value"] is None
    assert out["confidence"] == 0.2
