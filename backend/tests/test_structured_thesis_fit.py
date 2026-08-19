"""Regression coverage: compute_structured_thesis_fit -- deterministic
replacement for Scout's self-reported confidence (product decision,
2026-08-19). Same inputs must always produce the same result."""

from fund_thesis import compute_structured_thesis_fit

PARSED_JSON = {
    "sectors": ["B2B SaaS", "AI"],
    "stage_focus": ["Seed", "Series A"],
    "geography": ["us", "europe"],
}


def test_all_three_categories_match():
    scout_output = {"sector": "B2B SaaS", "funding_stage": "Seed", "location": "London, UK"}
    result = compute_structured_thesis_fit(scout_output, PARSED_JSON)
    assert result["matched_categories"] == 3
    assert result["total_categories"] == 3
    assert all(r["matched"] for r in result["category_results"])


def test_no_categories_match():
    scout_output = {"sector": "Healthcare", "funding_stage": "Series C", "location": "Tokyo, JP"}
    result = compute_structured_thesis_fit(scout_output, PARSED_JSON)
    assert result["matched_categories"] == 0


def test_two_identical_inputs_always_produce_the_same_score():
    """The bug this replaces: the old self-reported confidence could differ
    between calls for identical inputs. This is pure field matching -- it
    cannot."""
    scout_output = {"sector": "AI", "funding_stage": "Series A", "location": "London, UK"}
    first = compute_structured_thesis_fit(scout_output, PARSED_JSON)
    second = compute_structured_thesis_fit(dict(scout_output), PARSED_JSON)
    assert first == second


def test_missing_fields_do_not_match_and_do_not_raise():
    result = compute_structured_thesis_fit({}, PARSED_JSON)
    assert result["matched_categories"] == 0


def test_empty_mandate_matches_nothing():
    scout_output = {"sector": "B2B SaaS", "funding_stage": "Seed", "location": "Berlin, DE"}
    result = compute_structured_thesis_fit(scout_output, {})
    assert result["matched_categories"] == 0
