"""Reviewer gap-triggered supplemental retrieval."""

from reviewer.gap_retrieval import (
    build_gap_queries,
    enrich_scout_for_reviewer_llm,
    fetch_reviewer_gap_pack,
    scout_has_information_gaps,
)


def test_scout_has_gaps_when_tam_and_refs_weak():
    assert scout_has_information_gaps(
        {
            "name": "Acme",
            "est_tam": None,
            "funding_stage": "Seed",
            "references": ["https://acme.com"],
        }
    )


def test_no_gaps_when_well_filled():
    assert not scout_has_information_gaps(
        {
            "name": "Acme",
            "est_tam": "$5B",
            "funding_stage": "Series A",
            "founder_names": ["Jane Doe"],
            "references": ["https://acme.com", "https://news.com/acme"],
        }
    )


def test_build_gap_queries_orders_tam_funding_team():
    qs = build_gap_queries(
        {
            "name": "Acme AI",
            "est_tam": None,
            "funding_stage": "Unknown",
            "references": [],
        }
    )
    assert len(qs) >= 2
    assert any("TAM" in q or "market" in q for q in qs)
    assert any("funding" in q for q in qs)


def test_build_gap_queries_covers_product_and_technical_evidence():
    """TAM isn't the only thin dimension — product (pain_alignment/ux/retention) and
    technical/competitive (engineering_quality/competition) components have no dedicated
    Scout field, so they ride the same thin-evidence gate rather than a per-field check."""
    qs = build_gap_queries(
        {
            "name": "Acme AI",
            "est_tam": "$5B",
            "funding_stage": "Series A",
            "references": ["https://acme.com", "https://news.com/acme"],
        }
    )
    assert any("customer" in q and "retention" in q for q in qs)
    assert any("technology" in q and "competitors" in q for q in qs)


def test_enrich_adds_supplement_when_pack_non_empty(monkeypatch):
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL", "1")
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL_ONLY_WHEN_GAPS", "1")

    def fake_pack(scout, user_id):
        return {
            "sources": [
                {"source_id": "S1", "title": "x", "url": "https://a.com", "snippet": "z"},
            ],
            "url_allowlist": {"https://a.com"},
        }

    monkeypatch.setattr("reviewer.gap_retrieval.fetch_reviewer_gap_pack", fake_pack)
    base = {
        "name": "Co",
        "est_tam": None,
        "funding_stage": "Seed",
        "references": [],
    }
    out = enrich_scout_for_reviewer_llm(base, "user-1")
    assert "_reviewer_web_supplement" in out
    assert "S1" in out["_reviewer_web_supplement"]
    assert "https://a.com" in (out.get("_reviewer_gap_reference_urls") or [])


def test_enrich_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL", "0")
    out = enrich_scout_for_reviewer_llm(
        {"name": "Co", "est_tam": None, "funding_stage": None, "references": []},
        "user-1",
    )
    assert "_reviewer_web_supplement" not in out


def test_enrich_skips_broad_gap_search_when_operator_context_is_present(monkeypatch):
    """Add-context already supplies the deliberate evidence delta; do not add
    several unrelated retrieval searches before the re-review."""
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL", "1")

    def unexpected_pack(*args, **kwargs):
        raise AssertionError("broad gap retrieval should be skipped for add-context")

    monkeypatch.setattr("reviewer.gap_retrieval.fetch_reviewer_gap_pack", unexpected_pack)
    out = enrich_scout_for_reviewer_llm(
        {
            "name": "Acme",
            "est_tam": None,
            "funding_stage": "Unknown",
            "references": [],
            "operator_context": "[Content of operator-provided link https://acme.example/news]\nNew pilot data",
        },
        "user-1",
    )

    assert "_reviewer_web_supplement" not in out


def test_reviewer_gap_retrieval_keeps_trusted_external_corroboration(monkeypatch):
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL", "1")
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL_ONLY_WHEN_GAPS", "1")

    def fake_retrieve(**kwargs):
        return {
            "provider": "exa",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Aethria Solutions",
                    "url": "https://aethriasolutions.com",
                    "snippet": "A different similarly named services company.",
                },
                {
                    "source_id": "S2",
                    "title": "Aethria",
                    "url": "https://aethria.co",
                    "snippet": "Official product site.",
                },
                {
                    "source_id": "S3",
                    "title": "Aethria raises a seed round",
                    "url": "https://techcrunch.com/2026/01/01/aethria-seed-round",
                    "snippet": "Aethria was founded by Jane Smith and John Doe.",
                },
            ],
            "url_allowlist": {
                "https://aethriasolutions.com",
                "https://aethria.co",
                "https://techcrunch.com/2026/01/01/aethria-seed-round",
            },
        }

    monkeypatch.setattr("research.retrieval_grounding.retrieve_source_pack_merged", fake_retrieve)
    pack = fetch_reviewer_gap_pack(
        {
            "name": "Aethria",
            "lookup_website": "aethria.co",
            "est_tam": None,
            "funding_stage": "Unknown",
            "references": ["Aethria official website - https://aethria.co"],
        },
        "user-1",
    )

    assert pack is not None
    urls = [source["url"] for source in pack["sources"]]
    assert urls == [
        "https://aethria.co",
        "https://techcrunch.com/2026/01/01/aethria-seed-round",
    ]
    assert pack["url_allowlist"] == set(urls)


def test_reviewer_gap_retrieval_runs_for_missing_founders_even_when_other_fields_exist(monkeypatch):
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL", "1")
    monkeypatch.setenv("REVIEWER_GAP_RETRIEVAL_ONLY_WHEN_GAPS", "1")
    captured = {}

    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {"provider": "exa", "sources": [{"url": "https://techcrunch.com/aethria"}]}

    monkeypatch.setattr("research.retrieval_grounding.retrieve_source_pack_merged", fake_retrieve)
    pack = fetch_reviewer_gap_pack(
        {
            "name": "Aethria",
            "est_tam": "$4B",
            "funding_stage": "Seed",
            "founder_names": [],
            "references": ["Aethria - https://aethria.co", "Aethria - https://linkedin.com/company/aethria"],
        },
        "user-1",
    )

    assert pack is not None
    assert any("founders" in query for query in captured["queries"])
    assert captured["category"] == "people"
