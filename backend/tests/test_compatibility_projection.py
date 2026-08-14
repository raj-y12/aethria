from compatibility_projection import project_scout_for_runtime


def _snapshot():
    return {
        "contexts": {
            "funding": {"has_canonical_coverage": True, "claims": [{"claim_type": "funding_stage", "normalized_value": {"stage": "Series A"}}]},
            "market": {"has_canonical_coverage": True, "claims": [{"claim_type": "market_size", "normalized_value": {"estimate": "$5B"}}]},
            "traction": {"has_canonical_coverage": True, "claims": [{"claim_type": "traction_revenue", "normalized_value": {"revenue": "$3M ARR"}}]},
        }
    }


def test_canonical_runtime_projection_wins_over_conflicting_legacy_fields():
    projected = project_scout_for_runtime(
        {"funding_stage": "Seed", "est_tam": "$1B", "traction_facts": {"revenue": "$100K"}},
        _snapshot(),
    )
    assert projected["funding_stage"] == "Series A"
    assert projected["est_tam"] == "$5B"
    assert projected["traction_facts"]["revenue"] == "$3M ARR"
    assert set(projected["canonical_runtime_fields"]) == {"funding_stage", "est_tam", "traction_facts"}


def test_runtime_projection_falls_back_for_legacy_only_fields():
    projected = project_scout_for_runtime(
        {"funding_stage": "Seed", "competition": "Crowded", "location": "Dublin"},
        {"contexts": {"funding": {"has_canonical_coverage": False}}},
    )
    assert projected["funding_stage"] == "Seed"
    assert projected["competition"] == "Crowded"
    assert projected["location"] == "Dublin"
    assert projected["canonical_runtime_fields"] == []


def test_compatibility_projection_never_creates_claims_or_mutates_input():
    source = {"funding_stage": "Seed"}
    projected = project_scout_for_runtime(source, _snapshot())
    assert source == {"funding_stage": "Seed"}
    assert "claims" not in projected
