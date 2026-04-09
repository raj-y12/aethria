from utils.retrieval_grounding import retrieve_source_pack


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
