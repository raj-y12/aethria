"""Firecrawl v2 provider contract tests (all network calls are stubbed)."""
from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from utils.firecrawl_client import firecrawl_search
from utils.search_providers import provider_search, reset_providers
from utils.tavily_client import ProviderSearchResults


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def _provider_environment(monkeypatch):
    for name in ("FIRECRAWL_API_KEY", "TAVILY_API_KEY", "RETRIEVAL_PRIMARY_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    reset_providers()
    yield
    reset_providers()


def test_success_normalizes_markdown_and_deduplicates_urls(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    payload = {
        "success": True,
        "creditsUsed": 3,
        "data": {"web": [
            {"title": "Acme", "url": "https://example.com/a", "description": "description", "markdown": "markdown wins"},
            {"title": "Duplicate", "url": "https://example.com/a#fragment", "description": "ignored"},
            {"title": "No URL", "description": "ignored"},
        ]},
    }
    monkeypatch.setattr("utils.firecrawl_client.urlopen", lambda *args, **kwargs: _Response(payload))

    result = firecrawl_search("acme", max_results=5)

    assert result == [{"title": "Acme", "url": "https://example.com/a", "snippet": "markdown wins"}]
    assert result.diagnostics["outcome"] == "success"


def test_firecrawl_error_falls_back_to_tavily_and_keeps_tier_diagnostics(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tv-key")
    monkeypatch.setattr(
        "utils.search_providers.firecrawl_search",
        lambda *args, **kwargs: ProviderSearchResults([], {"provider": "firecrawl", "outcome": "error", "reason": "http_error", "result_count": 0}),
    )
    tavily_rows = ProviderSearchResults(
        [{"title": "Tavily", "url": "https://tavily.example", "snippet": "answer"}],
        {"provider": "tavily", "outcome": "success", "reason": None, "result_count": 1},
    )
    monkeypatch.setattr("utils.search_providers.tavily_search", lambda *args, **kwargs: tavily_rows)

    result = provider_search("acme", max_results=5)

    assert list(result) == list(tavily_rows)
    assert result.diagnostics["provider"] == "tavily"
    assert [tier["provider"] for tier in result.diagnostics["tiers"]] == ["exa", "firecrawl", "tavily"]


@pytest.mark.parametrize("payload", [
    {"success": False, "error": "bad request"},
    {"success": True},
    {"success": True, "data": []},
    {"success": True, "data": {"web": {}}},
])
def test_malformed_responses_are_errors_not_silent_empty(monkeypatch, payload):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    monkeypatch.setattr("utils.firecrawl_client.urlopen", lambda *args, **kwargs: _Response(payload))

    result = firecrawl_search("acme")

    assert result == []
    assert result.diagnostics["outcome"] == "error"
    assert result.diagnostics["reason"] == "malformed_response"


def test_rate_limit_retries_then_reports_rate_limited(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    monkeypatch.setenv("FIRECRAWL_MAX_RETRIES", "1")
    attempts = 0

    def limited(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPError("https://api.firecrawl.dev/v2/search", 429, "limited", {"Retry-After": "0"}, BytesIO())

    monkeypatch.setattr("utils.firecrawl_client.urlopen", limited)
    monkeypatch.setattr("utils.firecrawl_client.time.sleep", lambda _: None)

    result = firecrawl_search("acme")

    assert attempts == 2
    assert result.diagnostics["reason"] == "rate_limited"
    assert result.diagnostics["http_status"] == 429


def test_zero_results_has_populated_empty_diagnostic(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
    monkeypatch.setattr("utils.firecrawl_client.urlopen", lambda *args, **kwargs: _Response({"success": True, "data": {"web": []}}))

    result = firecrawl_search("acme")

    assert result == []
    assert result.diagnostics == {"provider": "firecrawl", "outcome": "empty", "reason": "no_usable_results", "result_count": 0}


def test_missing_api_key_is_a_disabled_diagnostic():
    result = firecrawl_search("acme")

    assert result == []
    assert result.diagnostics == {"provider": "firecrawl", "outcome": "disabled", "reason": "missing_api_key", "result_count": 0}
