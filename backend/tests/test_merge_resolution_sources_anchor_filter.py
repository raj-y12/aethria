"""Regression coverage (live-observed on Notion): _merge_resolution_sources
used to merge every one of Company Resolver's evidence_sources into the Scout
LLM's citable source pack with zero anchor filtering -- for a common-word
company name, Company Resolver's search legitimately turns up several
unrelated lookalike companies alongside the real one (e.g. "Notion" pulled in
"Notion Technologies", "Notionink Design Labs", "Notion State", and random
LinkedIn people-profiles), and ALL of it got merged in as if it were evidence
about the one company that was actually picked (resolution.website). The
Scout LLM then produced a reference list mixing several different companies,
and the reviewer correctly couldn't ground anything against it -- its own
summary said "the Notion reference appears to be a mislabel or incomplete."
Only sources that anchor to the picked company should be merged; the rest
belong in resolution.alternative_matches, not in the citable evidence pool."""

from resolver.company_resolver import CompanyResolution, EvidenceSource
from scout.base import Scout


class DummyScout(Scout):
    pass


def _scout() -> "DummyScout":
    return DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )


def _resolution() -> CompanyResolution:
    return CompanyResolution(
        query="Notion",
        canonical_name="Notion",
        website="https://notion.com",
        resolution_status="FOUND",
        confidence=0.9,
        evidence_sources=[
            EvidenceSource(
                url="https://notion.com",
                title="Notion — Home",
                snippet="Notion is a workspace for teams.",
                source_type="official_site",
                match_score=1.0,
            ),
            EvidenceSource(
                url="https://www.linkedin.com/company/notionhq",
                title="Notion | LinkedIn",
                snippet="Notion. Software Development.",
                source_type="linkedin",
                match_score=1.0,
            ),
            # Different, unrelated companies that happen to share the "notion" token.
            EvidenceSource(
                url="https://notiontechnologies.com/",
                title="Notion Technologies — Home",
                snippet="Notion Technologies builds industrial sensors.",
                source_type="official_site",
                match_score=0.85,
            ),
            EvidenceSource(
                url="https://notionink.com/",
                title="Notionink Design Labs",
                snippet="Notionink Design Labs is a product studio.",
                source_type="official_site",
                match_score=0.85,
            ),
            EvidenceSource(
                url="https://scramblelabs.com/",
                title="Scramble Labs",
                snippet="Scramble Labs is an unrelated startup.",
                source_type="other",
                match_score=1.0,
            ),
            # A person unrelated to Notion, surfaced by a generic founder-query hit.
            EvidenceSource(
                url="https://www.linkedin.com/in/someoneelse",
                title="Someone Else — LinkedIn",
                snippet="Founder at Notion Technologies.",
                source_type="other",
                match_score=1.0,
            ),
        ],
    )


def test_merge_resolution_sources_drops_lookalike_companies_not_anchored_to_the_picked_website():
    scout = _scout()
    merged = scout._merge_resolution_sources({"sources": []}, _resolution())
    urls = {s["url"] for s in merged["sources"]}

    assert "https://notion.com" in urls
    # Known, documented tradeoff: the real company's own LinkedIn page has a
    # vanity slug ("notionhq") that doesn't exactly match the domain-derived
    # slug ("notion"), so the strict slug-equality check this reuses from
    # _assign_identity_fields (deliberately strict -- see
    # test_profile_from_different_company_is_not_attached_or_used_for_founders,
    # which requires exactly this strictness to reject a DIFFERENT company's
    # LinkedIn page) also excludes this legitimate one here. Losing a
    # marginal LinkedIn citation is a much smaller cost than the original
    # bug (11 wrong-company sources), and the company's own official site
    # remains the primary evidence either way.
    assert "https://www.linkedin.com/company/notionhq" not in urls
    # Lookalike domains classified as their own official_site are filtered by
    # exact host match against the picked website -- unambiguous.
    assert "https://notiontechnologies.com/" not in urls
    assert "https://notionink.com/" not in urls
    # A source that never mentions the target company at all is filtered.
    assert "https://scramblelabs.com/" not in urls
    # Known, documented limitation: a source that names a SUPERSTRING of a
    # single-generic-word company ("Notion Technologies" contains the
    # "notion" token) still passes the token check -- text matching alone
    # can't fully disambiguate this without more than a company name to go
    # on. Not asserted as excluded here; this is the residual gap noted in
    # _profile_matches_anchor's docstring, not something this fix claims to
    # solve completely.


def test_merge_resolution_sources_keeps_news_coverage_that_names_the_anchor_company():
    scout = _scout()
    resolution = _resolution()
    resolution.evidence_sources.append(
        EvidenceSource(
            url="https://techcrunch.com/notion-raises",
            title="Notion raises new round",
            snippet="Notion, at notion.com, announced funding today.",
            source_type="news",
            match_score=0.7,
        )
    )
    merged = scout._merge_resolution_sources({"sources": []}, resolution)
    urls = {s["url"] for s in merged["sources"]}
    assert "https://techcrunch.com/notion-raises" in urls


def test_merge_resolution_sources_is_a_noop_passthrough_when_resolution_missing():
    scout = _scout()
    assert scout._merge_resolution_sources({"sources": [{"url": "https://x.com"}]}, None) == {
        "sources": [{"url": "https://x.com"}]
    }
