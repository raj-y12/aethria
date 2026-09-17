"""Exa provider contract tests (all network calls are stubbed).

Two layers are covered separately on purpose:

* `exa_client.exa_search` — the pure HTTP client: request shape, filters,
  dedup, ranking, and every failure mode.
* `search_providers.ExaSearchProvider` — the composition: Exa finds URLs,
  Firecrawl reads them, and the fallback to Exa highlights is labelled.
"""
from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from research.exa_client import exa_search, query_intent, semantic_query
from research.search_providers import provider_search, reset_providers
from research.search_results import ProviderSearchResults


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _payload(results, cost=0.007):
    return {"results": results, "requestId": "req", "costDollars": {"total": cost}}


def _result(url, title="Acme", **extra):
    return {"url": url, "title": title, "highlights": ["highlight text"], **extra}


@pytest.fixture(autouse=True)
def _provider_environment(monkeypatch):
    for name in (
        "EXA_API_KEY", "FIRECRAWL_API_KEY",
        "RETRIEVAL_PRIMARY_PROVIDER", "RETRIEVAL_PROVIDER_ORDER",
        "EXA_INCLUDE_DOMAINS", "EXA_EXCLUDE_DOMAINS", "EXA_ENRICH_WITH_FIRECRAWL",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_providers()
    yield
    reset_providers()


@pytest.fixture
def captured_body(monkeypatch):
    """Capture the JSON body Exa is sent, returning a configurable payload."""
    state = {"body": None, "payload": _payload([_result("https://acme.com")])}

    def fake_urlopen(request, *args, **kwargs):
        state["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(state["payload"])

    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setattr("research.exa_client.urlopen", fake_urlopen)
    return state


# --- client: success, dedup, ranking ---------------------------------------


def test_successful_discovery_normalizes_and_preserves_metadata(captured_body):
    captured_body["payload"] = _payload([
        _result(
            "https://acme.com",
            title="Acme",
            publishedDate="2026-07-01T00:00:00.000Z",
            author="Ada Byron",
            score=0.91,
        )
    ])

    rows = exa_search("acme robotics", max_results=5)

    assert [r["url"] for r in rows] == ["https://acme.com"]
    assert rows[0]["published_date"] == "2026-07-01T00:00:00.000Z"
    assert rows[0]["author"] == "Ada Byron"
    assert rows[0]["score"] == 0.91
    assert rows[0]["highlight"] == "highlight text"
    assert rows.diagnostics["provider"] == "exa"
    assert rows.diagnostics["outcome"] == "success"
    assert rows.diagnostics["cost_usd"] == 0.007


def test_duplicate_urls_are_collapsed_before_firecrawl(captured_body):
    captured_body["payload"] = _payload([
        _result("https://acme.com/about", title="About"),
        _result("https://acme.com/about/", title="About trailing slash"),
        _result("https://acme.com/about?utm_source=x", title="About tracked"),
        _result("https://other.com/x", title="Other"),
    ])

    rows = exa_search("acme", max_results=10)

    assert [r["url"] for r in rows] == ["https://acme.com/about", "https://other.com/x"]


def test_company_domains_outrank_directories_and_listicles(captured_body):
    captured_body["payload"] = _payload([
        _result("https://www.crunchbase.com/organization/acme", title="Acme profile", score=0.99),
        _result("https://blog.example.com/top-10-robotics-startups", title="Top 10", score=0.95),
        _result("https://acme.com", title="Acme", score=0.5),
    ])

    rows = exa_search("robotics startups building warehouse automation", max_results=10)

    assert rows[0]["url"] == "https://acme.com"


def test_resolver_lookups_keep_aggregators_they_rely_on(captured_body):
    """Crunchbase/LinkedIn are identity anchors for the company resolver."""
    captured_body["payload"] = _payload([
        _result("https://www.crunchbase.com/organization/acme", title="Acme profile", score=0.99),
        _result("https://acme.com", title="Acme", score=0.5),
    ])

    rows = exa_search("Acme Inc official company profile", max_results=10, category="company")

    assert rows[0]["url"] == "https://www.crunchbase.com/organization/acme"


# --- client: request shape, filters ----------------------------------------


def test_named_company_lookup_uses_exa_company_category(captured_body):
    exa_search("Acme Inc official site", max_results=5, category="company")

    assert captured_body["body"]["category"] == "company"


def test_named_lookup_query_is_not_rewritten_into_a_discovery_phrase(captured_body):
    """Measured: prefixing a named lookup buries the company it names."""
    exa_search("Anthropic official company site", max_results=5, category="company")

    assert captured_body["body"]["query"] == "Anthropic official company site"


def test_open_discovery_query_is_rewritten_to_seek_companies(captured_body):
    exa_search('"climate tech" OR "energy" warehouse automation', max_results=5, category="general")

    assert captured_body["body"]["query"].startswith("Companies working on")
    assert '"' not in captured_body["body"]["query"]


def test_open_discovery_funding_query_seeks_companies_that_raised(captured_body):
    exa_search("climate tech startup seed funding raised", max_results=5, category="general")

    assert captured_body["body"]["query"].startswith("Startups that recently raised funding in")


def test_people_category_maps_to_exa_people_search(captured_body):
    exa_search("who founded Acme", max_results=5, category="people")

    assert captured_body["body"]["category"] == "people"


def test_domain_filters_are_forwarded(monkeypatch, captured_body):
    monkeypatch.setenv("EXA_INCLUDE_DOMAINS", "acme.com, techcrunch.com")
    monkeypatch.setenv("EXA_EXCLUDE_DOMAINS", "spam.example")

    exa_search("recent funding news for robotics", max_results=5, category="news")

    assert captured_body["body"]["includeDomains"] == ["acme.com", "techcrunch.com"]
    assert captured_body["body"]["excludeDomains"] == ["spam.example"]


def test_date_filter_is_sent_as_start_published_date(captured_body):
    exa_search("latest robotics news", max_results=5, category="news", time_range="week")

    assert captured_body["body"]["startPublishedDate"].endswith("Z")


def test_restricted_filters_are_dropped_for_company_and_people(monkeypatch, captured_body):
    """Exa 400s if these are sent with the company/people categories."""
    monkeypatch.setenv("EXA_EXCLUDE_DOMAINS", "spam.example")

    exa_search("Acme Inc", max_results=5, category="company", time_range="week")

    assert "excludeDomains" not in captured_body["body"]
    assert "startPublishedDate" not in captured_body["body"]


def test_full_page_text_is_never_requested_from_exa(captured_body):
    exa_search("acme", max_results=5)

    assert captured_body["body"]["contents"] == {
        "highlights": {"numSentences": 3, "highlightsPerUrl": 2}
    }
    assert "text" not in captured_body["body"]["contents"]


def test_autonomous_research_modes_are_rejected(monkeypatch, captured_body):
    monkeypatch.setenv("EXA_SEARCH_TYPE", "deep-reasoning")

    exa_search("acme", max_results=5)

    assert captured_body["body"]["type"] == "auto"


# --- client: failure modes --------------------------------------------------


def test_missing_api_key_is_a_disabled_diagnostic():
    rows = exa_search("acme")

    assert rows == []
    assert rows.diagnostics["outcome"] == "disabled"
    assert rows.diagnostics["reason"] == "missing_api_key"


@pytest.mark.parametrize("payload", [{"error": "bad request"}, {"results": "nope"}, []])
def test_malformed_responses_are_errors_not_silent_empty(monkeypatch, payload):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setattr("research.exa_client.urlopen", lambda *a, **k: _Response(payload))

    rows = exa_search("acme")

    assert rows == []
    assert rows.diagnostics["outcome"] == "error"
    assert rows.diagnostics["reason"] == "malformed_response"


def test_zero_results_reports_empty_not_success(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setattr("research.exa_client.urlopen", lambda *a, **k: _Response(_payload([])))

    rows = exa_search("acme")

    assert rows == []
    assert rows.diagnostics["outcome"] == "empty"
    assert rows.diagnostics["reason"] == "no_usable_results"


def test_rate_limit_retries_then_reports_rate_limited(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("EXA_MAX_RETRIES", "1")
    attempts = 0

    def limited(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPError("https://api.exa.ai/search", 429, "limited", {}, BytesIO())

    monkeypatch.setattr("research.exa_client.urlopen", limited)
    monkeypatch.setattr("research.exa_client.time.sleep", lambda _: None)

    rows = exa_search("acme")

    assert attempts == 2
    assert rows.diagnostics["reason"] == "rate_limited"
    assert rows.diagnostics["http_status"] == 429


def test_timeout_retries_then_reports_timeout(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setenv("EXA_MAX_RETRIES", "1")
    attempts = 0

    def slow(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise TimeoutError("read timed out")

    monkeypatch.setattr("research.exa_client.urlopen", slow)
    monkeypatch.setattr("research.exa_client.time.sleep", lambda _: None)

    rows = exa_search("acme")

    assert attempts == 2
    assert rows.diagnostics["reason"] == "timeout"


# --- query construction -----------------------------------------------------


def test_boolean_scaffolding_is_stripped_for_a_semantic_index():
    query = '"climate tech" OR "energy" startup funding round raised'

    for rewritten in (semantic_query(query, "company"), semantic_query(query, "company", discovery=True)):
        assert '"' not in rewritten
        assert " OR " not in rewritten


def test_only_discovery_queries_get_an_intent_prefix():
    query = "Acme Inc official site"

    assert semantic_query(query, "company") == query
    assert semantic_query(query, "company", discovery=True).startswith("Companies working on")


@pytest.mark.parametrize("query,category,expected", [
    ("who founded acme", "general", "founder"),
    ("acme series a funding raised", "general", "funding"),
    ("acme careers open roles", "general", "hiring"),
    ("acme customers case study", "general", "customers"),
    ("acme alternatives competitor", "general", "competitors"),
    ("acme pricing platform features", "general", "product"),
    ("robotics market size report", "general", "market"),
    ("warehouse robotics startups", "general", "company"),
    ("anything at all", "news", "news"),
    ("anything at all", "people", "founder"),
])
def test_query_intent_classification(query, category, expected):
    assert query_intent(query, category) == expected


# --- provider composition: Exa -> Firecrawl ---------------------------------


def test_exa_urls_are_passed_to_firecrawl_and_content_wins(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    scraped = {}

    def fake_scrape(urls, timeout=None):
        scraped["urls"] = list(urls)
        return [{"url": "https://acme.com", "content": "full page markdown"}]

    monkeypatch.setattr(
        "research.search_providers.exa_search",
        lambda *a, **k: ProviderSearchResults(
            [{"title": "Acme", "url": "https://acme.com", "highlight": "short highlight"}],
            {"provider": "exa", "outcome": "success", "reason": None, "result_count": 1,
             "query_type": "company", "cost_usd": 0.01},
        ),
    )
    monkeypatch.setattr("research.search_providers.firecrawl_scrape", fake_scrape)

    rows = provider_search("acme", max_results=5)

    assert scraped["urls"] == ["https://acme.com"]
    assert rows[0]["snippet"] == "full page markdown"
    assert rows[0]["content_provider"] == "firecrawl"
    assert rows.diagnostics["firecrawl_success_rate"] == 1.0


def test_firecrawl_failure_falls_back_to_exa_highlight_with_provenance(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setattr(
        "research.search_providers.exa_search",
        lambda *a, **k: ProviderSearchResults(
            [{"title": "Acme", "url": "https://acme.com", "highlight": "short highlight"}],
            {"provider": "exa", "outcome": "success", "reason": None, "result_count": 1,
             "query_type": "company"},
        ),
    )

    def boom(urls, timeout=None):
        raise RuntimeError("firecrawl down")

    monkeypatch.setattr("research.search_providers.firecrawl_scrape", boom)

    rows = provider_search("acme", max_results=5)

    assert rows[0]["snippet"] == "short highlight"
    assert rows[0]["content_provider"] == "exa_highlight"
    assert rows.diagnostics["content_fallback"] == "firecrawl_error"
    assert rows.diagnostics["provider"] == "exa"


def test_diagnostics_carry_discovery_quality_and_tier_history(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-key")
    monkeypatch.setattr(
        "research.search_providers.exa_search",
        lambda *a, **k: ProviderSearchResults(
            [
                {"title": "Acme", "url": "https://acme.com", "highlight": "h"},
                {"title": "CB", "url": "https://www.crunchbase.com/organization/acme", "highlight": "h"},
            ],
            {"provider": "exa", "outcome": "success", "reason": None, "result_count": 2,
             "query_type": "company"},
        ),
    )
    monkeypatch.setattr("research.search_providers.firecrawl_scrape", lambda urls, timeout=None: [])

    rows = provider_search("acme", max_results=5)

    assert rows.diagnostics["unique_domains"] == 2
    assert rows.diagnostics["company_domain_rate"] == 0.5
    assert [tier["provider"] for tier in rows.diagnostics["tiers"]] == ["exa"]


# --- chain ordering and failure ---------------------------------------------


def test_exa_leads_the_chain_and_firecrawl_answers_when_it_is_empty(monkeypatch):
    monkeypatch.setattr(
        "research.search_providers.exa_search",
        lambda *a, **k: ProviderSearchResults(
            [], {"provider": "exa", "outcome": "empty", "reason": "no_usable_results", "result_count": 0}
        ),
    )
    firecrawl_rows = ProviderSearchResults(
        [{"title": "FC", "url": "https://fc.example", "snippet": "answer"}],
        {"provider": "firecrawl", "outcome": "success", "reason": None, "result_count": 1},
    )
    monkeypatch.setattr("research.search_providers.firecrawl_search", lambda *a, **k: firecrawl_rows)

    rows = provider_search("acme", max_results=5)

    assert rows.diagnostics["provider"] == "firecrawl"
    assert [tier["provider"] for tier in rows.diagnostics["tiers"]] == ["exa", "firecrawl"]


def test_primary_provider_override_moves_a_tier_to_the_head(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_PRIMARY_PROVIDER", "firecrawl")
    monkeypatch.setattr(
        "research.search_providers.firecrawl_search",
        lambda *a, **k: ProviderSearchResults(
            [], {"provider": "firecrawl", "outcome": "empty", "reason": "no_usable_results", "result_count": 0}
        ),
    )
    monkeypatch.setattr(
        "research.search_providers.exa_search",
        lambda *a, **k: ProviderSearchResults(
            [], {"provider": "exa", "outcome": "empty", "reason": "no_usable_results", "result_count": 0}
        ),
    )

    rows = provider_search("acme", max_results=5)

    assert [tier["provider"] for tier in rows.diagnostics["tiers"]] == ["firecrawl", "exa"]


def test_one_tier_raising_does_not_sink_the_tiers_behind_it(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("exa down")

    monkeypatch.setattr("research.search_providers.exa_search", boom)
    firecrawl_rows = ProviderSearchResults(
        [{"title": "FC", "url": "https://fc.example", "snippet": "answer"}],
        {"provider": "firecrawl", "outcome": "success", "reason": None, "result_count": 1},
    )
    monkeypatch.setattr("research.search_providers.firecrawl_search", lambda *a, **k: firecrawl_rows)

    rows = provider_search("acme", max_results=5)

    assert rows.diagnostics["provider"] == "firecrawl"
    assert [tier["provider"] for tier in rows.diagnostics["tiers"]] == ["exa", "firecrawl"]
    assert rows.diagnostics["tiers"][0]["reason"] == "provider_error"


def test_complete_chain_failure_returns_empty_with_every_tier_recorded(monkeypatch):
    for target, provider in (
        ("exa_search", "exa"), ("firecrawl_search", "firecrawl")
    ):
        monkeypatch.setattr(
            f"research.search_providers.{target}",
            lambda *a, _p=provider, **k: ProviderSearchResults(
                [], {"provider": _p, "outcome": "error", "reason": "request_error", "result_count": 0}
            ),
        )

    rows = provider_search("acme", max_results=5)

    assert rows == []
    assert [tier["provider"] for tier in rows.diagnostics["tiers"]] == ["exa", "firecrawl"]
    assert rows.diagnostics["outcome"] == "empty"


def test_chain_failure_degrades_to_duckduckgo_not_to_nothing(monkeypatch):
    """The keyless fallback still sits behind the whole chain."""
    from research.retrieval_grounding import retrieve_source_pack

    for target, provider in (
        ("exa_search", "exa"), ("firecrawl_search", "firecrawl")
    ):
        monkeypatch.setattr(
            f"research.search_providers.{target}",
            lambda *a, _p=provider, **k: ProviderSearchResults(
                [], {"provider": _p, "outcome": "error", "reason": "request_error", "result_count": 0}
            ),
        )
    monkeypatch.setattr(
        "research.retrieval_grounding._fallback_search",
        lambda query, max_results: ProviderSearchResults(
            [{"title": "DDG", "url": "https://ddg.example", "snippet": ""}],
            {"provider": "duckduckgo_html_fallback", "outcome": "success", "reason": None, "result_count": 1},
        ),
    )

    pack = retrieve_source_pack(query="acme", user_id="u1", max_results=3)

    assert pack["provider"] == "duckduckgo_html_fallback"
    assert len(pack["sources"]) == 1
