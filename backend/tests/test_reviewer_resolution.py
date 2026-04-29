"""Tests for reviewer score resolution when personas diverge."""

from services.reviewer_resolution import apply_resolution_to_primary


def test_resolution_pulls_high_spread_dimensions_toward_conservative():
    primary = {
        "market_score": 7,
        "product_score": 6,
        "technical_score": 5,
        "execution_score": 6,
        "defensibility_score": 7,
    }
    personas = [
        {"reviewer_type": "DefaultReviewer", "market_score": 8, "product_score": 6, "technical_score": 5, "execution_score": 6, "defensibility_score": 8},
        {"reviewer_type": "SkepticalReviewer", "market_score": 4, "product_score": 6, "technical_score": 5, "execution_score": 6, "defensibility_score": 6},
        {"reviewer_type": "OpportunistReviewer", "market_score": 9, "product_score": 6, "technical_score": 5, "execution_score": 6, "defensibility_score": 9},
    ]
    notes, summary = apply_resolution_to_primary(primary, personas)
    assert primary["market_score"] != 7  # spread 5 >= 2 → adjusted
    assert isinstance(notes, list)
    assert summary is not None


def test_no_notes_when_spread_low():
    primary = {"market_score": 6, "product_score": 6, "technical_score": 6, "execution_score": 6}
    personas = [
        {"market_score": 7, "product_score": 6, "technical_score": 6, "execution_score": 6},
        {"market_score": 6, "product_score": 6, "technical_score": 6, "execution_score": 6},
    ]
    notes, summary = apply_resolution_to_primary(primary, personas)
    assert notes == []
    assert summary is None or "Moderate" in summary

