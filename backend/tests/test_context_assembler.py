from datetime import datetime, timezone

import pytest

from context import ContextAssembler
from context import CanonicalContextProvider


NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _rows():
    claims = [
        {"user_id": "fund-a", "claim_id": "m-1", "claim_type": "market_size", "status": "current", "confidence": 0.8, "display_text": "A $2B market."},
        {"user_id": "fund-a", "claim_id": "f-1", "claim_type": "funding_stage", "status": "current", "confidence": 0.7, "display_text": "Seed stage."},
        {"user_id": "fund-a", "claim_id": "old", "claim_type": "traction_revenue", "status": "superseded", "confidence": 0.9, "display_text": "Old revenue."},
        {"user_id": "fund-a", "claim_id": "stale", "claim_type": "traction_revenue", "status": "current", "confidence": 0.9, "display_text": "Expired revenue."},
    ]
    evidence = [
        {"user_id": "fund-a", "claim_id": "m-1", "relationship": "supports", "display_excerpt": "A $2B market.", "source_locator": "market.example", "access_class": "public", "verification_state": "verified", "source_quality": 0.9},
        {"user_id": "fund-a", "claim_id": "f-1", "relationship": "supports", "display_excerpt": "Seed stage.", "source_locator": "funding.example", "access_class": "tenant_confidential", "verification_state": "verified", "source_quality": 0.8},
        {"user_id": "fund-a", "claim_id": "stale", "relationship": "supports", "display_excerpt": "Expired revenue.", "source_locator": "old.example", "access_class": "public", "verification_state": "verified", "expires_at": "2026-08-01T00:00:00+00:00"},
    ]
    return claims, evidence


def test_assembler_selects_canonical_claims_with_supporting_provenance():
    claims, evidence = _rows()
    packet = ContextAssembler().assemble(
        user_id="fund-a", criterion="market", claims=claims, evidence=evidence, now=NOW
    )

    assert packet["criterion"] == "market"
    assert [item["claim_id"] for item in packet["current_supported_claims"]] == ["m-1"]
    assert packet["evidence"][0]["source_locator"] == "market.example"
    assert packet["has_canonical_coverage"] is True
    assert packet["chars"] <= 4000


def test_assembler_keeps_supporting_and_contradicting_evidence_separate():
    claims, evidence = _rows()
    claims.append({"user_id": "fund-a", "claim_id": "p-1", "claim_type": "product_capability", "status": "current", "confidence": 0.8, "display_text": "Product capability."})
    evidence.extend([
        {"user_id": "fund-a", "claim_id": "p-1", "relationship": "supports", "display_excerpt": "Product exists.", "source_locator": "product.example", "access_class": "public", "verification_state": "verified"},
        {"user_id": "fund-a", "claim_id": "p-1", "relationship": "contradicts", "display_excerpt": "Product not available.", "source_locator": "news.example", "access_class": "public", "verification_state": "verified"},
    ])
    packet = ContextAssembler().assemble(user_id="fund-a", criterion="product", claims=claims, evidence=evidence, now=NOW)

    assert packet["current_supported_claims"][0]["claim_id"] == "p-1"
    assert packet["materially_contradicted_claims"][0]["claim_id"] == "p-1"
    assert {item["relationship"] for item in packet["evidence"]} == {"supports", "contradicts"}


def test_assembler_filters_private_and_cross_tenant_rows_fail_closed():
    claims, evidence = _rows()
    claims.append({"user_id": "fund-b", "claim_id": "b-1", "claim_type": "market_size", "status": "current", "display_text": "Other tenant."})
    with pytest.raises(ValueError, match="tenant"):
        ContextAssembler().assemble(user_id="fund-a", criterion="market", claims=claims, evidence=evidence, now=NOW)

    packet = ContextAssembler().assemble(user_id="fund-a", criterion="funding", claims=claims[:4], evidence=evidence, now=NOW)
    assert [item["claim_id"] for item in packet["current_supported_claims"]] == ["f-1"]


def test_assembler_returns_safe_fallback_for_insufficient_coverage_and_deterministic_order():
    claims, evidence = _rows()
    packet = ContextAssembler().assemble(user_id="fund-a", criterion="competition", claims=claims, evidence=evidence, now=NOW)

    assert packet["has_canonical_coverage"] is False
    assert packet["fallback"] == "legacy_context"
    assert packet["missing_information"] == ["competition"]
    assert packet["text"].startswith("CANONICAL CONTEXT [competition]")


def test_commercial_packet_preserves_unknown_economics_when_only_one_dimension_is_known():
    packet = ContextAssembler().assemble(
        user_id="fund-a", criterion="commercial",
        claims=[{"user_id": "fund-a", "claim_id": "c1", "claim_type": "revenue_model", "status": "current", "confidence": 0.8, "display_text": "Subscription revenue."}],
        evidence=[{"user_id": "fund-a", "claim_id": "c1", "relationship": "supports", "display_excerpt": "Subscription revenue.", "source_locator": "source.example", "access_class": "public"}],
    )
    assert packet["has_canonical_coverage"] is True
    assert "pricing" in packet["missing_information"]
    assert "unit_economics" in packet["missing_information"]


@pytest.mark.asyncio
async def test_provider_resolves_one_tenant_ledger_into_criterion_packets():
    class Identity:
        async def get_opportunity_by_legacy_projection(self, *, user_id, legacy_startup_id):
            assert user_id == "fund-a"
            assert legacy_startup_id == "startup-1"
            return type("Opportunity", (), {"opportunity_id": "opp-1"})()

    class Evidence:
        async def get_ledger(self, *, user_id, opportunity_id):
            return {"claims": [{"user_id": user_id, "claim_id": "m", "claim_type": "market_size", "display_text": "Market", "status": "current"}], "claim_evidence_links": [{"user_id": user_id, "claim_id": "m", "relationship": "supports", "display_excerpt": "Market", "source_locator": "x", "access_class": "public"}]}

    loaded = await CanonicalContextProvider(Identity(), Evidence())("fund-a", "startup-1")
    assert loaded["contexts"]["market"]["has_canonical_coverage"] is True
    assert loaded["contexts"]["competition"]["has_canonical_coverage"] is False
    assert loaded["contexts"]["commercial"]["has_canonical_coverage"] is False
    assert loaded["contexts"]["funding"]["has_canonical_coverage"] is False


def test_assembler_context_is_deterministic_and_bounded_for_large_evidence():
    claims = [{"user_id": "fund-a", "claim_id": "m", "claim_type": "market_size", "status": "current", "display_text": "Market"}]
    evidence = [{"user_id": "fund-a", "claim_id": "m", "relationship": "supports", "display_excerpt": "x" * 5000, "source_locator": "z", "access_class": "public"}]
    assembler = ContextAssembler()
    first = assembler.assemble(user_id="fund-a", criterion="market", claims=claims, evidence=evidence, max_chars=240, now=NOW)
    second = assembler.assemble(user_id="fund-a", criterion="market", claims=claims, evidence=evidence, max_chars=240, now=NOW)

    assert first == second
    assert first["chars"] <= 240
    assert first["text"].endswith("[context truncated]")
