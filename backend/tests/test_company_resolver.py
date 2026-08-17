"""
Company Resolver: status mapping, evidence extraction, transparency guarantees.

Pins the analyst-not-judge contract:
- weak evidence => PARTIAL / LOW_CONFIDENCE / NEEDS_REVIEW (kept + explained), never a drop
- NOT_FOUND only when there is genuinely no credible evidence
- every resolution carries queries used, evidence, missing fields, and a stage log
"""
import asyncio
from typing import Any, Dict, List

import pytest

import resolver.company_resolver as cr
from resolver.company_resolver import (
    CompanyResolution,
    EvidenceSource,
    build_fallback_scout_payload,
    resolve_company,
)

USER = "user_2test_resolver"


def _pack(sources: List[Dict[str, str]], provider: str = "exa") -> Dict[str, Any]:
    return {
        "provider": provider,
        "query": "q",
        "sources": sources,
        "url_allowlist": {s["url"] for s in sources},
    }


def test_extract_founders_rejects_role_attributed_to_a_different_company():
    """Regression: live-verified on Vercel. A BusinessWire headline genuinely
    about Vercel ("Vercel Appoints Mitchell Hashimoto, Co-Founder of HashiCorp
    ... to Board of Directors") matched the founder-role pattern and credited
    Mitchell Hashimoto as a Vercel founder -- he's HashiCorp's co-founder,
    joining Vercel's board, not founding Vercel."""
    sources = [
        EvidenceSource(
            url="https://www.businesswire.com/vercel-hashimoto",
            title="Vercel Appoints Mitchell Hashimoto, Co-Founder of HashiCorp, to Board of Directors",
            snippet="Vercel today announced Mitchell Hashimoto, Co-Founder of HashiCorp, has joined its board.",
        ),
    ]
    assert cr._extract_founders(sources, company="Vercel") == []


def test_extract_founders_still_finds_a_real_founder_of_the_target_company():
    sources = [
        EvidenceSource(
            url="https://example.com/acme",
            title="Acme announces new funding round",
            snippet="Jane Smith, co-founder of Acme, announced the round today.",
        ),
    ]
    assert cr._extract_founders(sources, company="Acme") == ["Jane Smith"]


def test_not_found_when_no_evidence(monkeypatch):
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack([]))
    res = resolve_company("Totally Nonexistent Startup Zzz", user_id=USER)
    assert res.resolution_status == "NOT_FOUND"
    assert res.queries_used  # transparent about what was searched
    assert res.stage_log
    assert "website" in res.missing_fields


def test_strong_identity_is_found(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics — Home",
            "url": "https://acmerobotics.com",
            "snippet": "Acme Robotics builds warehouse automation robots for 3PL operators.",
        },
        {
            "title": "Acme Robotics | LinkedIn",
            "url": "https://www.linkedin.com/company/acme-robotics",
            "snippet": "Acme Robotics. Robotics. 11-50 employees.",
        },
        {
            "title": "Acme Robotics - Crunchbase Company Profile",
            "url": "https://www.crunchbase.com/organization/acme-robotics",
            "snippet": "Acme Robotics raised $12M Series A.",
        },
        {
            "title": "Acme Robotics raises $12M",
            "url": "https://techcrunch.com/2025/01/10/acme-robotics-raises",
            "snippet": "Acme Robotics, founded by Jane Smith and John Doe, raised $12M.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Acme Robotics", user_id=USER)
    assert res.resolution_status == "FOUND"
    assert res.website == "https://acmerobotics.com"
    assert res.linkedin_url and "linkedin.com/company" in res.linkedin_url
    assert res.crunchbase_url and "crunchbase.com/organization" in res.crunchbase_url
    assert "Jane Smith" in res.founder_names
    assert res.confidence >= 0.7
    assert res.description


def test_profile_from_different_company_is_not_attached_or_used_for_founders(monkeypatch):
    sources = [
        {
            "title": "Aethria — AI deal flow",
            "url": "https://aethria.co",
            "snippet": "Aethria builds software for venture capital deal flow.",
        },
        {
            "title": "Aethria Solutions | LinkedIn",
            "url": "https://www.linkedin.com/company/aethriasolutions",
            "snippet": "Aethria Solutions was founded by Arjuna Jayasinghe.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))

    res = resolve_company("Aethria", user_id=USER, website_hint="aethria.co")

    assert res.linkedin_url is None
    assert "Arjuna Jayasinghe" not in res.founder_names
    assert "Arjuna Jayasinghe" not in (res.description or "")


def test_attached_yc_profile_is_extracted_for_founders(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics — Home",
            "url": "https://acmerobotics.com",
            "snippet": "Acme Robotics builds warehouse automation robots.",
        },
        {
            "title": "Acme Robotics | Y Combinator",
            "url": "https://www.ycombinator.com/companies/acme-robotics",
            "snippet": "Acme Robotics is a YC company.",
        },
    ]
    extracted = []

    def fake_extract(urls):
        extracted.extend(urls)
        return [
            {
                "url": urls[0],
                "content": "Acme Robotics was founded by Jane Smith and John Doe.",
            }
        ]

    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    monkeypatch.setattr(cr, "extract_pages", fake_extract)

    res = resolve_company("Acme Robotics", user_id=USER)

    assert extracted == ["https://www.ycombinator.com/companies/acme-robotics"]
    assert res.founder_names == ["Jane Smith", "John Doe"]


def test_weak_evidence_is_partial_or_low_confidence_not_dropped(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics mentioned in industry roundup",
            "url": "https://some-blog.example.com/warehouse-robots",
            "snippet": "Startups like Acme Robotics are entering the market.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Acme Robotics", user_id=USER)
    assert res.resolution_status in ("PARTIAL", "LOW_CONFIDENCE")
    assert res.evidence_sources
    assert res.missing_fields  # explains what's missing instead of dropping
    assert res.notes


def test_website_hint_prevents_not_found(monkeypatch):
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack([]))
    res = resolve_company("Stealthy Co", user_id=USER, website_hint="stealthy.co")
    assert res.resolution_status != "NOT_FOUND"
    assert res.website == "https://stealthy.co"


def test_ambiguous_same_slug_domains_need_review(monkeypatch):
    sources = [
        {
            "title": "Aethria — AI deal flow",
            "url": "https://aethria.com",
            "snippet": "Aethria automates venture deal flow.",
        },
        {
            "title": "Aethria | Home",
            "url": "https://aethria.co",
            "snippet": "Aethria is a wellness brand.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Aethria", user_id=USER)
    assert res.resolution_status == "NEEDS_REVIEW"
    assert res.alternative_matches
    assert any("disambiguate" in n.lower() for n in res.notes)


def test_retrieval_error_degrades_gracefully(monkeypatch):
    def boom(**kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(cr, "retrieve_source_pack_merged", boom)
    res = resolve_company("Acme Robotics", user_id=USER)
    # No exception; explained NOT_FOUND with stage log showing the provider error.
    assert res.resolution_status == "NOT_FOUND"
    assert any("provider error" in s.reason.lower() for s in res.stage_log)


def test_fallback_payload_from_resolution_evidence():
    res = CompanyResolution(
        query="Acme Robotics",
        canonical_name="Acme Robotics",
        website="https://acmerobotics.com",
        confidence=0.5,
        resolution_status="PARTIAL",
        evidence_sources=[
            EvidenceSource(
                url="https://acmerobotics.com",
                title="Acme Robotics",
                snippet="Acme Robotics builds warehouse robots.",
                source_type="official_site",
                match_score=1.0,
                supports="Company identity (official website)",
            )
        ],
        missing_fields=["linkedin_url", "founder_names"],
    )
    payload = build_fallback_scout_payload(res, scout_type="market_driven", company_name="Acme Robotics")
    assert payload is not None
    assert payload["name"] == "Acme Robotics"
    assert payload["resolution_status"] == "NEEDS_REVIEW"
    assert payload["references"]
    assert any("acmerobotics.com" in r for r in payload["references"])
    # Must satisfy the strict scout schema so persistence cannot reject it.
    from scout.schema import validate_scout_output

    validate_scout_output(payload)


def test_fallback_payload_requires_some_evidence():
    res = CompanyResolution(query="Ghost", canonical_name="Ghost", resolution_status="NOT_FOUND")
    assert build_fallback_scout_payload(res, scout_type="market_driven", company_name="Ghost") is None


def test_engine_lookup_persists_fallback_when_scout_fails(monkeypatch):
    """run_named_lookup must persist a NEEDS_REVIEW row (not vanish) when the scout
    LLM stage fails but the resolver found evidence."""
    from scout.engine import ScoutEngine

    stored: List[Dict[str, Any]] = []

    class FakeStorage:
        _user_id = USER
        _client = None

        def add_discovery(self, payload, *, pipeline_run_id=None):
            stored.append(payload)
            return payload.get("id")

    engine = ScoutEngine(api_key="sk-test", storage=FakeStorage(), tenant_user_id=USER)
    try:
        resolution = CompanyResolution(
            query="Acme Robotics",
            canonical_name="Acme Robotics",
            website="https://acmerobotics.com",
            confidence=0.55,
            resolution_status="PARTIAL",
            evidence_sources=[
                EvidenceSource(
                    url="https://acmerobotics.com",
                    title="Acme Robotics",
                    snippet="Warehouse robots.",
                    source_type="official_site",
                    match_score=1.0,
                )
            ],
        )

        async def no_result(*a, **kw):
            return None

        for scout in engine.scouts:
            monkeypatch.setattr(scout, "discover_company", no_result)

        startup_id = asyncio.run(
            engine.run_named_lookup("Acme Robotics", resolution=resolution)
        )
        assert startup_id is not None
        assert stored and stored[0]["resolution_status"] == "NEEDS_REVIEW"
        assert stored[0]["company_resolution"]["canonical_name"] == "Acme Robotics"
        assert engine.last_lookup_outcome["status"] == "NEEDS_REVIEW"
    finally:
        engine.close()


def test_engine_lookup_uses_existing_id_returned_by_storage(monkeypatch):
    """A tenant-scoped duplicate must continue with the persisted row, not the
    newly generated scout UUID that was never inserted."""
    from scout.engine import ScoutEngine

    state_writes = []

    class NoPhantomStateClient:
        def table(self, name):
            state_writes.append(name)
            raise AssertionError("duplicate lookup must not persist state for the unused scout UUID")

    class FakeStorage:
        _user_id = USER
        _client = NoPhantomStateClient()

        def add_discovery(self, payload, *, pipeline_run_id=None):
            assert payload["id"] != "existing-startup"
            return "existing-startup"

    engine = ScoutEngine(api_key="sk-test", storage=FakeStorage(), tenant_user_id=USER)
    try:
        resolution = CompanyResolution(
            query="Acme Robotics",
            canonical_name="Acme Robotics",
            website="https://acmerobotics.com",
            confidence=0.8,
            resolution_status="FOUND",
            evidence_sources=[
                EvidenceSource(
                    url="https://acmerobotics.com",
                    title="Acme Robotics",
                    snippet="Warehouse robots.",
                    source_type="official_site",
                    match_score=1.0,
                )
            ],
        )

        async def no_result(*a, **kw):
            return None

        for scout in engine.scouts:
            monkeypatch.setattr(scout, "discover_company", no_result)

        startup_id = asyncio.run(
            engine.run_named_lookup(
                "Acme Robotics",
                resolution=resolution,
                pipeline_run_id="11111111-1111-4111-8111-111111111111",
            )
        )

        assert startup_id == "existing-startup"
        assert engine.last_lookup_outcome["status"] == "ALREADY_IN_DEAL_FLOW"
        assert engine.last_lookup_outcome["startup_id"] == "existing-startup"
        assert state_writes == []
    finally:
        engine.close()


def test_engine_lookup_not_found_sets_transparent_outcome(monkeypatch):
    from scout.engine import ScoutEngine

    engine = ScoutEngine(api_key="sk-test", storage=None, tenant_user_id=USER)
    try:
        resolution = CompanyResolution(
            query="Ghost Co",
            canonical_name="Ghost Co",
            resolution_status="NOT_FOUND",
            queries_used=["Ghost Co startup", "Ghost Co company"],
        )
        startup_id = asyncio.run(
            engine.run_named_lookup("Ghost Co", resolution=resolution)
        )
        assert startup_id is None
        outcome = engine.last_lookup_outcome
        assert outcome["status"] == "NOT_FOUND"
        assert "No credible evidence" in outcome["message"]
        assert outcome["resolution"]["queries_used"]
    finally:
        engine.close()


def test_distinct_domain_extensions_become_separate_candidates(monkeypatch):
    sources = [
        {
            "title": "Lyra — Irish fintech",
            "url": "https://lyra.ie",
            "snippet": "Lyra is a Dublin-based payments startup for SMEs.",
        },
        {
            "title": "Lyra — US analytics",
            "url": "https://lyra.com",
            "snippet": "Lyra builds healthcare analytics software in San Francisco.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Lyra", user_id=USER)
    domains = {c.website for c in res.candidates}
    assert "https://lyra.ie" in domains
    assert "https://lyra.com" in domains
    assert len(res.candidates) >= 2
    for c in res.candidates:
        assert c.description  # each snapshot has a one-line description


def test_single_clear_company_yields_one_candidate(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics — Home",
            "url": "https://acmerobotics.com",
            "snippet": "Acme Robotics builds warehouse automation robots.",
        },
        {
            "title": "Acme Robotics | LinkedIn",
            "url": "https://www.linkedin.com/company/acme-robotics",
            "snippet": "Acme Robotics. Robotics. 11-50 employees.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Acme Robotics", user_id=USER)
    company_domains = {c.website for c in res.candidates}
    assert company_domains == {"https://acmerobotics.com"}


def test_website_hint_collapses_to_single_candidate(monkeypatch):
    sources = [
        {"title": "Lyra IE", "url": "https://lyra.ie", "snippet": "Dublin payments startup."},
        {"title": "Lyra US", "url": "https://lyra.com", "snippet": "US healthcare analytics."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Lyra", user_id=USER, website_hint="lyra.ie")
    assert res.website == "https://lyra.ie"
    assert [c.website for c in res.candidates] == ["https://lyra.ie"]


def test_no_candidates_when_no_evidence(monkeypatch):
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack([]))
    res = resolve_company("Totally Nonexistent Startup Zzz", user_id=USER)
    assert res.candidates == []


def test_candidate_name_is_prettified_for_hyphenated_domain(monkeypatch):
    sources = [
        {
            "title": "Acme Robotics",
            "url": "https://acme-robotics.com",
            "snippet": "Acme Robotics builds warehouse automation robots.",
        },
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    res = resolve_company("Acme Robotics", user_id=USER)
    names = {c.name for c in res.candidates}
    assert "acme-robotics" not in names  # not the raw slug
