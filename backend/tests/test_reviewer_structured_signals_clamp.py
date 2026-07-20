"""Optional grounding clamp on reviewer structured_signals."""

import pytest

from utils.reviewer_structured_signals_clamp import clamp_structured_signals_evidence


def test_ungrounded_label_is_cleared_by_default(monkeypatch):
    monkeypatch.delenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", raising=False)
    monkeypatch.delenv("REVIEWER_SIGNALS_STRICT_CLEAR", raising=False)
    signals = {"defensibility": {"network_effects": {
        "label": "strong", "confidence": 0.9, "evidence": "speculation"
    }}}
    clamped = clamp_structured_signals_evidence(
        {"references": ["https://example.com/company"]}, signals
    )
    component = clamped["defensibility"]["network_effects"]
    assert component.get("label") is None
    assert component.get("value") is None
    assert component["confidence"] <= 0.2


def test_clamp_noop_when_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", "false")
    scout = {"problem": "x" * 80, "references": []}
    sig = {
        "market": {
            "tam": {
                "value": "$1",
                "confidence": 0.9,
                "evidence": "no scout overlap here",
                "reasoning": "guess",
            }
        }
    }
    out = clamp_structured_signals_evidence(scout, sig)
    assert out["market"]["tam"]["confidence"] == 0.9


def test_clamp_lowers_confidence_when_ungrounded(monkeypatch):
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", "1")
    scout = {
        "problem": "Enterprise buyers face long procurement cycles for security software today.",
        "references": [],
    }
    sig = {
        "market": {
            "tam": {
                "value": "$1",
                "confidence": 0.9,
                "evidence": "Completely fabricated with no overlap.",
                "reasoning": "guess",
            }
        }
    }
    out = clamp_structured_signals_evidence(scout, sig)
    assert float(out["market"]["tam"]["confidence"]) <= 0.2


def test_clamp_keeps_high_confidence_when_scout_substring(monkeypatch):
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", "1")
    long_problem = "Enterprise buyers face long procurement cycles for security software today."
    scout = {"problem": long_problem, "references": []}
    sig = {
        "market": {
            "tam": {
                "value": "$12B",
                "confidence": 0.85,
                "evidence": "Enterprise buyers face long procurement",
                "reasoning": "quoted scout",
            }
        }
    }
    out = clamp_structured_signals_evidence(scout, sig)
    assert float(out["market"]["tam"]["confidence"]) == pytest.approx(0.85)


def test_clamp_keeps_when_allowlisted_url_in_evidence(monkeypatch):
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", "1")
    scout = {
        "problem": "short",
        "references": ["https://news.example.com/article"],
    }
    sig = {
        "market": {
            "tam": {
                "value": "$1",
                "confidence": 0.8,
                "evidence": "See https://news.example.com/article for sizing.",
                "reasoning": "url",
            }
        }
    }
    out = clamp_structured_signals_evidence(scout, sig)
    assert float(out["market"]["tam"]["confidence"]) == pytest.approx(0.8)


def test_clamp_clears_label_when_strict_clear(monkeypatch):
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", "1")
    monkeypatch.setenv("REVIEWER_SIGNALS_STRICT_CLEAR", "1")
    scout = {"problem": "x" * 80, "references": []}
    sig = {
        "market": {
            "urgency": {
                "label": "high",
                "value": None,
                "confidence": 0.7,
                "evidence": "no overlap at all in this evidence string",
                "reasoning": "x",
            }
        }
    }
    out = clamp_structured_signals_evidence(scout, sig)
    cell = out["market"]["urgency"]
    assert float(cell["confidence"]) <= 0.2
    assert "label" not in cell
    assert cell.get("value") is None
