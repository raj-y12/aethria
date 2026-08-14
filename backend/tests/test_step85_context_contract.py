from context_assembler import ContextAssembler
from founder_context import build_founder_context
from regulatory_context import build_reviewer_regulatory_context


def test_context_assembler_exposes_one_stable_snapshot_shape():
    packet = ContextAssembler().assemble(
        user_id="fund-a",
        criterion="market",
        claims=[{"user_id": "fund-a", "claim_id": "c1", "claim_type": "market_size", "status": "current", "display_text": "Market"}],
        evidence=[{"user_id": "fund-a", "claim_id": "c1", "relationship": "supports", "display_excerpt": "Market", "source_locator": "https://source.example", "verification_state": "verified", "access_class": "public"}],
    )
    assert packet["schema_version"] == "canonical-context-v1"
    assert packet["claims"] == packet["current_supported_claims"]
    assert packet["supporting_evidence"] == packet["evidence"]
    assert packet["contradicting_evidence"] == []
    assert "freshness" in packet
    assert packet["bounded"]["max_chars"] == 4000


def test_regulatory_and_founder_contexts_expose_the_same_snapshot_contract():
    regulatory = build_reviewer_regulatory_context(
        claims=[{"claim_id": "r1", "claim_type": "operational_feasibility", "status": "current", "display_text": "Operates."}],
        evidence=[{"claim_id": "r1", "relationship": "supports", "display_excerpt": "Operates.", "source_locator": "reg.example", "verification_state": "verified", "access_class": "public"}],
    )
    founder = build_founder_context({"founders": [{"name": "Ada Lovelace", "confidence": 0.9, "role": "CTO", "evidence": [{"url": "founder.example", "snippet": "Ada led engineering.", "access_class": "public"}]}]})
    required = {"schema_version", "criterion", "claims", "supporting_evidence", "contradicting_evidence", "freshness", "missing_information", "bounded"}
    assert required <= regulatory.keys()
    assert required <= founder.keys()
    assert regulatory["criterion"] == "regulatory"
    assert founder["criterion"] == "founder"
