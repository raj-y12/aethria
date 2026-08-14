from reviewer.base import _format_scout_context_extras


SCOUT = {
    "scout_type": "market_driven",
    "funding_stage": "Seed",
    "location": "Dublin",
    "est_tam": "$2B",
    "traction_facts": {"revenue": "$1M ARR", "customers": 12},
    "references": ["https://acme.example/about"],
}


def test_step11_suppresses_only_fields_with_canonical_coverage():
    text = _format_scout_context_extras(
        SCOUT,
        canonical_criteria={"funding", "market", "traction"},
    )
    assert "Funding stage (scout)" not in text
    assert "Est. TAM (scout)" not in text
    assert "Traction (from retrieved evidence)" not in text
    assert "Location (scout): Dublin" in text
    assert "References: 1 item" in text


def test_step11_fallback_keeps_legacy_fields_when_canonical_coverage_is_missing():
    text = _format_scout_context_extras(SCOUT, canonical_criteria=set())
    assert "Funding stage (scout): Seed" in text
    assert "Est. TAM (scout): $2B" in text
    assert "Traction (from retrieved evidence)" in text


def test_step11_migration_does_not_treat_partial_coverage_as_ready():
    text = _format_scout_context_extras(
        SCOUT,
        canonical_criteria={"funding"},
    )
    assert "Funding stage (scout)" not in text
    assert "Est. TAM (scout): $2B" in text
    assert "Traction (from retrieved evidence)" in text


def test_step11_reports_measurable_legacy_context_reduction():
    before = _format_scout_context_extras(SCOUT, canonical_criteria=set())
    after = _format_scout_context_extras(
        SCOUT,
        canonical_criteria={"funding", "market", "traction"},
    )
    assert len(after) < len(before)
    assert len(before) - len(after) >= 80
