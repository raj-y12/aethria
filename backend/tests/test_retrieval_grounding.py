from utils.retrieval_grounding import retrieve_source_pack, retrieve_source_pack_merged


def test_retrieve_source_pack_uses_tavily_first(monkeypatch):
    monkeypatch.setattr(
        "utils.retrieval_grounding.get_scout_retrieval_provider",
        lambda _uid: "tavily",
    )
    monkeypatch.setattr(
        "utils.retrieval_grounding.tavily_search",
        lambda query, max_results: [
            {"title": "Hivery", "url": "https://hivery.com", "snippet": "profile"}
        ],
    )
    pack = retrieve_source_pack(query="hivery startup", user_id="u1", max_results=3)
    assert pack["provider"] == "tavily"
    assert len(pack["sources"]) == 1
    assert "https://hivery.com" in pack["url_allowlist"]


def test_retrieve_source_pack_falls_back_to_serpapi(monkeypatch):
    monkeypatch.setattr(
        "utils.retrieval_grounding.get_scout_retrieval_provider",
        lambda _uid: "tavily",
    )
    monkeypatch.setattr("utils.retrieval_grounding.tavily_search", lambda query, max_results: [])
    monkeypatch.setattr(
        "utils.serp_client.search_serp_results",
        lambda query, user_id, num_results: [
            {"title": "Example", "url": "https://example.com", "snippet": ""}
        ],
    )
    pack = retrieve_source_pack(query="example startup", user_id="u1", max_results=3)
    assert pack["provider"] == "serpapi"
    assert len(pack["sources"]) == 1


def test_retrieve_source_pack_merged_dedupes_urls(monkeypatch):
    calls: list[str] = []

    def fake_tavily(query: str, max_results: int):
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

    monkeypatch.setattr(
        "utils.retrieval_grounding.get_scout_retrieval_provider",
        lambda _uid: "tavily",
    )
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


def test_retrieve_source_pack_empty_when_no_provider_results(monkeypatch):
    monkeypatch.setattr(
        "utils.retrieval_grounding.get_scout_retrieval_provider",
        lambda _uid: "tavily",
    )
    monkeypatch.setattr("utils.retrieval_grounding.tavily_search", lambda query, max_results: [])
    monkeypatch.setattr("utils.serp_client.search_serp_results", lambda query, user_id, num_results: [])
    pack = retrieve_source_pack(query="unknown", user_id="u1", max_results=3)
    assert pack["sources"] == []
    assert pack["url_allowlist"] == set()
