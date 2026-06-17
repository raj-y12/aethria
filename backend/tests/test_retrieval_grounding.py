from utils.retrieval_grounding import retrieve_source_pack, retrieve_source_pack_merged


def test_retrieve_source_pack_uses_tavily(monkeypatch):
    monkeypatch.setattr(
        "utils.retrieval_grounding.tavily_search",
        lambda query, max_results, time_range=None: [
            {"title": "Hivery", "url": "https://hivery.com", "snippet": "profile"}
        ],
    )
    pack = retrieve_source_pack(query="hivery startup", user_id="u1", max_results=3)
    assert pack["provider"] == "tavily"
    assert len(pack["sources"]) == 1
    assert "https://hivery.com" in pack["url_allowlist"]


def test_retrieve_source_pack_merged_dedupes_urls(monkeypatch):
    calls: list[str] = []

    def fake_tavily(query: str, max_results: int, time_range=None):
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

    monkeypatch.setattr("utils.retrieval_grounding.tavily_search", fake_tavily)
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


def test_recency_time_filter_scoped_to_recency_query(monkeypatch):
    """The Tavily time filter is applied to ONLY the recency query; general
    queries stay unfiltered so disambiguation isn't biased toward fresh pages."""
    seen: list[tuple[str, str | None]] = []

    def fake_tavily(query: str, max_results: int, time_range=None):
        seen.append((query, time_range))
        return [{"title": query[:8], "url": f"https://{abs(hash(query)) % 1000}.com", "snippet": "s"}]

    monkeypatch.setattr("utils.retrieval_grounding.tavily_search", fake_tavily)
    retrieve_source_pack_merged(
        queries=["acme funding", "acme traction"],
        recency_query="acme latest news acquisition",
        recency_time_range="year",
        user_id="u1",
    )
    general = [tr for q, tr in seen if "latest news" not in q]
    recency = [tr for q, tr in seen if "latest news" in q]
    assert general and all(tr is None for tr in general)
    assert recency == ["year"]


def test_retrieve_source_pack_empty_when_no_results(monkeypatch):
    monkeypatch.setattr(
        "utils.retrieval_grounding.tavily_search",
        lambda query, max_results, time_range=None: [],
    )
    pack = retrieve_source_pack(query="unknown", user_id="u1", max_results=3)
    assert pack["sources"] == []
    assert pack["url_allowlist"] == set()
