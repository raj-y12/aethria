from datetime import datetime, timezone

import pytest

from context import ContextAssembler, derive_competition_claims, derive_scout_claims


def test_competitors_are_extracted_only_from_explicit_source_language():
    claims = derive_competition_claims(
        {
            "name": "Acme",
            "source_evidence": [
                {"url": "https://acme.example/market", "snippet": "Acme competes with Stripe and Adyen for European enterprise payments."}
            ],
        }
    )
    assert {claim["claim_type"] for claim in claims} == {
        "competitor_existence", "competitor_product_overlap", "competitor_segment_overlap", "competitor_geography_overlap"
    }
    assert {claim["normalized_value"]["competitor_name"] for claim in claims} == {"Stripe", "Adyen"}


def test_generic_competitive_language_is_not_promoted_to_canonical_fact():
    assert derive_competition_claims({"source_evidence": [{"url": "https://x.example", "snippet": "This is a crowded and competitive market."}]}) == []


def test_competition_claims_preserve_provenance_and_unknowns():
    claims = derive_competition_claims({"source_evidence": [{"url": "https://x.example", "snippet": "Acme competes with Stripe."}]})
    assert claims[0]["_supporting_indexes"] == [0]
    assert claims[0]["normalized_value"]["source_status"] == "supported"
    packet = ContextAssembler().assemble(
        user_id="fund-a", criterion="competition", claims=[
            {"user_id": "fund-a", "claim_id": "c1", **claims[0], "status": "current", "confidence": 0.8, "display_text": claims[0]["display_text"]}
        ], evidence=[
            {"user_id": "fund-a", "claim_id": "c1", "relationship": "supports", "display_excerpt": "Acme competes with Stripe.", "source_locator": "https://x.example", "access_class": "public", "effective_at": datetime.now(timezone.utc).isoformat()}
        ])
    assert packet["has_canonical_coverage"] is True
    assert "competitor_existence" in packet["text"]


def test_private_competition_evidence_is_not_context_coverage():
    packet = ContextAssembler().assemble(
        user_id="fund-a", criterion="competition",
        claims=[{"user_id": "fund-a", "claim_id": "c1", "claim_type": "competitor_existence", "normalized_value": {"competitor_name": "Stripe"}, "status": "current", "confidence": 0.8, "display_text": "Stripe competes."}],
        evidence=[{"user_id": "fund-a", "claim_id": "c1", "relationship": "supports", "display_excerpt": "Stripe competes.", "source_locator": "https://private.example", "access_class": "restricted"}],
    )
    assert packet["has_canonical_coverage"] is False
    assert packet["fallback"] == "legacy_context"


def test_stale_competition_claim_is_unknown_and_conflicting_evidence_is_visible():
    packet = ContextAssembler().assemble(
        user_id="fund-a", criterion="competition",
        claims=[
            {"user_id": "fund-a", "claim_id": "c-old", "claim_type": "competitor_existence", "normalized_value": {"competitor_name": "OldCo"}, "status": "stale", "display_text": "OldCo competes."},
            {"user_id": "fund-a", "claim_id": "c-live", "claim_type": "competitor_existence", "normalized_value": {"competitor_name": "LiveCo"}, "status": "current", "confidence": 0.8, "display_text": "LiveCo competes."},
        ],
        evidence=[
            {"user_id": "fund-a", "claim_id": "c-live", "relationship": "supports", "display_excerpt": "LiveCo competes.", "source_locator": "https://current.example", "access_class": "public"},
            {"user_id": "fund-a", "claim_id": "c-live", "relationship": "contradicts", "display_excerpt": "LiveCo is not active in this category.", "source_locator": "https://other.example", "access_class": "public"},
        ],
    )
    assert "OldCo" not in packet["text"]
    assert packet["materially_contradicted_claims"][0]["claim_id"] == "c-live"
    assert {row["relationship"] for row in packet["evidence"]} == {"supports", "contradicts"}


def test_competition_claims_never_turn_into_a_no_competitors_judgment():
    claims = derive_competition_claims({"source_evidence": [{"url": "https://x.example", "snippet": "Acme competes with Stripe."}]})
    assert all("no competition" not in claim["display_text"].lower() for claim in claims)


def test_scout_bridge_includes_competition_claims_only_when_source_backed():
    claims = derive_scout_claims({
        "source_evidence": [{
            "url": "https://example.com/market",
            "snippet": "The company competes with Acme and Beta in Europe.",
        }],
    })
    assert {row["claim_type"] for row in claims} >= {
        "competitor_existence", "competitor_product_overlap", "competitor_geography_overlap",
    }
    assert all(row["_supporting_indexes"] == [0] for row in claims if row["claim_type"].startswith("competitor_"))


def test_scout_bridge_does_not_promote_reviewer_competition_judgment():
    claims = derive_scout_claims({
        "source_evidence": [{
            "url": "https://example.com/market",
            "snippet": "The market is crowded and incumbents have strong moats.",
        }],
    })
    assert not any(row["claim_type"].startswith("competitor_") for row in claims)
