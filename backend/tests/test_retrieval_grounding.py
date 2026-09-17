from research.retrieval_grounding import retrieve_source_pack, retrieve_source_pack_merged


def test_retrieve_source_pack_uses_the_chain(monkeypatch):
    monkeypatch.setattr(
        "research.search_providers.firecrawl_search",
        lambda query, max_results, time_range=None, topic=None, days=None: [
            {"title": "Hivery", "url": "https://hivery.com", "snippet": "profile"}
        ],
    )
    pack = retrieve_source_pack(query="hivery startup", user_id="u1", max_results=3)
    assert pack["provider"] == "firecrawl"
    assert len(pack["sources"]) == 1
    assert "https://hivery.com" in pack["url_allowlist"]


def test_retrieve_source_pack_merged_dedupes_urls(monkeypatch):
    calls: list[str] = []

    def fake_firecrawl(query, max_results, time_range=None, topic=None, days=None):
        calls.append(query)
        if "funding" in query:
            return [
                {"title": "A", "url": "https://a.com", "snippet": "first"},
                {"title": "B", "url": "https://b.com", "snippet": "second"},
            ]
        return [
            {"title": "A dup", "url": "https://a.com", "snippet": "duplicate host"},
            {"title": "C", "url": "https://c.com", "snippet": "third"},
        ]

    monkeypatch.setattr("research.search_providers.firecrawl_search", fake_firecrawl)
    pack = retrieve_source_pack_merged(
        queries=["Acme startup funding", "Acme traction customers"],
        user_id="u1",
        max_per_query=5,
        max_total_sources=10,
    )
    assert len(calls) == 2
    assert [s["source_id"] for s in pack["sources"]] == ["S1", "S2", "S3"]
    urls = [s["url"] for s in pack["sources"]]
    assert urls == ["https://a.com", "https://b.com", "https://c.com"]


def test_recency_query_runs_first_as_news_and_survives_cap(monkeypatch):
    """The recency query must use the news category AND land in the pack even when
    the general queries alone would fill the cap (the breaking-news regression)."""
    seen: list[tuple[str, str | None, int | None]] = []

    def fake_firecrawl(query, max_results, time_range=None, topic=None, days=None):
        seen.append((query, topic, days))
        if "acquisition" in query:  # the recency query
            return [{"title": "BigCo acquires Acme", "url": "https://news.example/acme-deal", "snippet": "today"}]
        # general queries flood enough rows to fill a small cap on their own
        return [{"title": f"g{i}", "url": f"https://g{i}.com", "snippet": "x"} for i in range(8)]

    monkeypatch.setattr("research.search_providers.firecrawl_search", fake_firecrawl)
    pack = retrieve_source_pack_merged(
        queries=["Acme funding", "Acme product", "Acme founders"],
        recency_query="Acme latest news 2026 acquisition merger",
        user_id="u1",
        max_per_query=8,
        max_total_sources=5,
    )
    urls = [s["url"] for s in pack["sources"]]
    # The day-old acquisition news survived the cap because it was ingested first.
    assert "https://news.example/acme-deal" in urls
    # And it was fetched via the news topic with a days window.
    recency_calls = [(t, d) for q, t, d in seen if "acquisition" in q]
    assert recency_calls and recency_calls[0][0] == "news" and isinstance(recency_calls[0][1], int)


def test_retrieve_source_pack_empty_when_no_results(monkeypatch):
    monkeypatch.setattr(
        "research.search_providers.firecrawl_search",
        lambda query, max_results, time_range=None, topic=None, days=None: [],
    )
    monkeypatch.setattr("research.retrieval_grounding._fallback_search", lambda query, max_results: [])
    pack = retrieve_source_pack(query="unknown", user_id="u1", max_results=3)
    assert pack["sources"] == []
    assert pack["url_allowlist"] == set()


def test_retrieve_source_pack_merged_reports_mixed_providers(monkeypatch):
    calls = []

    def fake_firecrawl(query, max_results, time_range=None, topic=None, days=None):
        calls.append(query)
        if len(calls) == 1:
            return [{"title": "Chain result", "url": "https://chain.example", "snippet": "x"}]
        return []

    monkeypatch.setattr("research.search_providers.firecrawl_search", fake_firecrawl)
    monkeypatch.setattr(
        "research.retrieval_grounding._fallback_search",
        lambda query, max_results: [{"title": "DDG result", "url": "https://ddg.example", "snippet": "x"}],
    )
    pack = retrieve_source_pack_merged(
        queries=["first", "second"], user_id="u1", max_per_query=3, max_total_sources=5
    )
    assert pack["provider"] == "mixed"
    assert pack["providers"] == ["duckduckgo_html_fallback", "firecrawl"]


def test_retrieve_source_pack_reports_provider_chain_when_no_results(monkeypatch):
    monkeypatch.setattr(
        "research.search_providers.firecrawl_search",
        lambda query, max_results, time_range=None, topic=None, days=None: [],
    )
    monkeypatch.setattr(
        "research.retrieval_grounding._fallback_search",
        lambda query, max_results: [],
    )

    pack = retrieve_source_pack(query="unknown", user_id="u1", max_results=3)

    assert pack["retrieval_outcome"] == "no_results"
    assert pack["provider"] == "none"
    assert [item["provider"] for item in pack["provider_diagnostics"]] == [
        "firecrawl",
        "duckduckgo_html_fallback",
    ]
    assert all(item["outcome"] == "empty" for item in pack["provider_diagnostics"])
