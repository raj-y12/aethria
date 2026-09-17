from models import ScoutInfo
from context import derive_scout_claims
from context import merge_scout_info_enrichment


def test_post_review_enrichment_is_explicitly_derived_compatibility_data():
    scout = ScoutInfo(
        startup_id="s1", name="TestCo", one_line="Test", sector="SaaS", problem="p",
        solution="s", target_users="u", why_now="now", scout_type="market_driven", confidence_score=0.8,
    )
    enriched = merge_scout_info_enrichment(
        scout,
        review_output={"structured_signals": {"market": {"tam": {"value": "$1B", "confidence": 0.9}}}},
        gap_reference_urls=["https://gap.example"],
    )
    assert enriched.derived_compatibility["est_tam"] == "reviewer_extraction"
    assert enriched.derived_compatibility["references"] == "gap_retrieval"
    assert derive_scout_claims({"references": enriched.references, "est_tam": enriched.est_tam}) == []


def test_reviewer_references_are_not_treated_as_canonical_source_evidence():
    assert derive_scout_claims({
        "references": ["https://reviewer-gap.example"],
        "est_tam": "$2B",
        "funding_stage": "Seed",
    }) == []
