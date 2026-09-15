from copy import deepcopy

from investment_analysis.grounding import financial_assertions_supported, ground_financial_text, reviewer_evidence


def test_glitch_ads_cannot_consume_glitch_studios_or_creator_ip_evidence():
    from investment_analysis.grounding import grounding_company_name
    name = grounding_company_name("Glitch", "glitchads.ai", "Glitch Ads")
    assert name == "Glitch Ads"
    rows = [claim("ads", text="Glitch Ads automates paid advertising.", url="https://glitchads.ai"),
        claim("studios", text="Glitch Studios distributes with Netflix and Amazon, 421M views.", url="https://glitchstudios.co"),
        claim("creator", text="Glitch funds animation with merchandise, not ads.", url="https://news.example/glitch-productions")]
    original = deepcopy(rows)
    packet, selected, _ = reviewer_evidence(rows, company_name=name, company_website="glitchads.ai")
    assert [row["claim_id"] for row in selected] == ["ads"]
    assert "Netflix" not in str(packet)
    assert rows == original
import pytest


def claim(key, *, text="ProVerum reports a product trial.", url="https://proverummedical.com/news", kind="source_statement", value=None):
    return {"claim_id": key, "claim_type": kind, "normalized_value": value or {}, "display_text": text,
            "supporting_evidence_ids": ["item"], "evidence_relationships": [{
                "evidence_item_id": "item", "artifact_id": "source", "source_uri": url,
                "display_excerpt": text, "verification_state": "verified", "source_quality": 1.0,
                "relationship": "supports"}]}


def test_packet_excludes_unrelated_sources_and_duplicate_claims_without_mutating_history():
    snapshot = [claim("a"), claim("duplicate"), claim("foreign", text="Proveris sells laboratory equipment.", url="https://proveris.com")]
    original = deepcopy(snapshot)
    packet, selected, aliases = reviewer_evidence(snapshot, company_name="ProVerum Limited", company_website="proverummedical.com")
    assert len(packet) == len(selected) == 1
    assert aliases == {"C1": "a"}
    assert packet[0]["claim_id"] == "C1"
    assert packet[0]["sources"][0]["url"] == "https://proverummedical.com/news"
    assert snapshot == original


def test_packet_excludes_unverified_founder_identity_and_retains_attributed_source():
    bad = claim("bad", kind="founder_identity", value={"name": "Biomedical Engineer"})
    bad["evidence_relationships"][0].update(verification_state="unverified", source_quality=0)
    packet, selected, _ = reviewer_evidence([bad, claim("good")], company_name="ProVerum", company_website="proverummedical.com")
    assert [row["claim_id"] for row in selected] == ["good"]
    assert "Biomedical Engineer" not in str(packet)


def test_empty_or_unknown_company_context_does_not_admit_unrelated_web_sources():
    packet, _, _ = reviewer_evidence([claim("foreign", text="Different startup", url="https://different.example")], company_name="ProVerum", company_website=None)
    assert packet == []


@pytest.mark.asyncio
async def test_research_drops_unrelated_domains_before_corroboration(monkeypatch):
    from evidence.retrieval import execute_evidence_plan
    from tests.evidence.test_retrieval import _FakeEvidenceRepository, _plan
    repo = _FakeEvidenceRepository()
    monkeypatch.setattr("evidence.retrieval.retrieve_source_pack_merged", lambda **kw: {"sources": [
        {"url": "https://proveris.com/news", "snippet": "Proveris makes laboratory instruments."},
        {"url": "https://news.example/proverum", "snippet": "ProVerum reports a trial."},
    ]})
    result = await execute_evidence_plan(user_id="user_test", company_id="company", opportunity_id="opp-1",
        plan=_plan(trigger_type="investment_analysis", search_questions=["clinical evidence"]),
        evidence_repository=repo, company_name="ProVerum", company_website="proverummedical.com")
    assert result["artifacts_ingested"] == 1
    assert result["verified_items"] == []


@pytest.mark.parametrize("name", ["Biomedical Engineer", "CFx Strategy", "Lead Business", "Maryam Mohammed Co", "Stack Exchange Network"])
def test_founder_extractors_reject_professional_and_organization_labels(name):
    from resolver.founder_resolver import _is_person_name
    from resolver.company_resolver import _extract_founders, EvidenceSource
    assert not _is_person_name(name)
    assert _extract_founders([EvidenceSource(url="https://proverummedical.com", title="ProVerum",
        snippet=f"{name}, founder of ProVerum.")], company="ProVerum") == []


def test_short_claim_handle_resolves_to_exact_canonical_lineage():
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions
    row = claim("canonical-claim")
    _, selected, aliases = reviewer_evidence([row], company_name="ProVerum", company_website="proverummedical.com")
    review = _bind_review(ReviewerDraft(overall_assessment="Attributed trial report.", investment_case=[{
        "type": "FACT", "text": "The company reports a trial.", "references": {"claim_ids": ["C1"]}}]),
        lineage=Lineage(user_id="tenant"), identity=Identity(name="ProVerum"), policy=PolicyVersions(),
        snapshot=selected, model=None, claim_aliases=aliases)
    refs = review.investment_case[0].references
    assert refs.claim_ids == ["canonical-claim"]
    assert refs.evidence_item_ids == ["item"]
    assert refs.source_ids == ["source"]


def test_analyst_projection_omits_invalid_founder_labels_without_rewriting_history():
    from api import _backend_to_frontend
    raw = {"startup_id": "startup", "scout_info": {"founder_names": ["CFx Strategy", "Biomedical Engineer", "Conor Harkin"],
           "company_resolution": {"founder_names": ["CFx Strategy"]},
           "founder_resolution": {"founders": [{"name": "CFx Strategy"}, {"name": "Conor Harkin"}]}}}
    original = deepcopy(raw)
    result = _backend_to_frontend(raw)
    assert result["scout"]["founder_names"] == ["Conor Harkin"]
    assert result["scout"]["founder_resolution"]["founders"] == [{"name": "Conor Harkin"}]
    assert result["scout"]["company_resolution"]["founder_names"] == []
    assert raw == original


def test_uncited_factual_prose_is_explicitly_unverified():
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions
    review = _bind_review(ReviewerDraft(overall_assessment="Needs diligence.", investment_case=[{
        "type": "FACT", "text": "A regulatory milestone is claimed.", "references": {}}]),
        lineage=Lineage(user_id="tenant"), identity=Identity(), policy=PolicyVersions(), snapshot=[], model=None)
    unit = review.investment_case[0]
    assert unit.type == "UNKNOWN"
    assert unit.text.startswith("Unverified:")
    assert unit.references.claim_ids == []


def test_financial_grounding_preserves_metric_and_value_meaning():
    revenue = claim("revenue", text="Revenue was $39.6 million for the year to January 2025.")
    arr = claim("arr", text="A third-party estimate puts ARR at $60m.")
    assert financial_assertions_supported("Revenue was $39.6m for the year to January 2025.", [revenue])
    assert financial_assertions_supported("The third-party estimate puts ARR at $60m.", [arr])
    assert not financial_assertions_supported("The company raised $39.6m in funding.", [revenue])
    assert not financial_assertions_supported("The company has multi-hundred-million ARR.", [revenue, arr])


def test_unsupported_financial_prose_is_marked_before_partner_input():
    row = claim("revenue", text="Revenue was $39.6 million for the year to January 2025.")
    assert ground_financial_text("The company has multi-hundred-million ARR trajectory.", [row]).startswith("Unverified:")


def test_financial_matching_does_not_cross_metric_or_drop_estimate_attribution():
    mixed = claim("mixed", text="Funding raised $125M. Revenue is undisclosed.")
    estimate = claim("estimate", text="A third-party estimated ARR is $60M.")
    assert not financial_assertions_supported("Revenue is $125M.", [mixed])
    assert not financial_assertions_supported("ARR is $60M.", [estimate])
    assert financial_assertions_supported("A third-party estimated ARR is $60M.", [estimate])


def test_financial_matching_allows_rounding_and_requires_forecast_label_and_basis():
    actual = claim("actual", text="Reported revenue was $39.6 million for the year to January 2025.")
    forecast = claim("forecast", text="Management forecasts ARR of $80M based on signed pipeline.")
    assert financial_assertions_supported("Revenue was $40M for the year to January 2025.", [actual])
    assert financial_assertions_supported("Forecast ARR is $80M based on signed pipeline.", [forecast])
    assert not financial_assertions_supported("ARR is $80M.", [forecast])


def test_unsupported_financial_reasoning_unit_is_downgraded_before_partner_input():
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions
    funding = claim("funding", text="Funding raised $125M. Revenue is undisclosed.")
    review = _bind_review(ReviewerDraft(
        overall_assessment="Revenue is $125M.",
        investment_case=[{"type": "FACT", "text": "Revenue is $125M.", "references": {"claim_ids": ["C1"]}}],
    ), lineage=Lineage(user_id="tenant"), identity=Identity(name="Acme"),
        policy=PolicyVersions(), snapshot=[funding], model=None, claim_aliases={"C1": "funding"})
    assert review.overall_assessment.startswith("Unverified:")
    assert review.investment_case[0].text.startswith("Unverified:")
def test_partner_api_projection_preserves_canonical_action():
    from api import _partner_dict_for_frontend

    provenance = {
        "recommendation_origin": "PARTNER_ANALYSIS",
        "canonical_recommendation": "insufficient_evidence",
    }
    projected = _partner_dict_for_frontend({"recommendation": "MONITOR", "provenance": provenance})
    assert projected["recommendation"] == "MONITOR"
    assert projected["provenance"] == provenance
