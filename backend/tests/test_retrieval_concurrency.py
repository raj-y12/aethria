"""Merged retrieval runs queries concurrently without changing the merged result.

A single lookup issues a dozen or more blocking searches; they used to run one
after another. Parallelism must not change ordering, deduplication, the recency
reservation, or the source cap — only wall-clock time.
"""
import threading
import time

import pytest

from utils.retrieval_grounding import retrieve_source_pack_merged
from utils.tavily_client import ProviderSearchResults


class _Recorder:
    """Fake provider that records calls and can simulate latency."""

    def __init__(self, delay=0.0):
        self.delay = delay
        self.queries = []
        self.max_in_flight = 0
        self._in_flight = 0
        self._lock = threading.Lock()

    def __call__(self, query, max_results, time_range=None, topic=None, days=None):
        with self._lock:
            self.queries.append(query)
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            if self.delay:
                time.sleep(self.delay)
            if "acquisition" in query:
                rows = [{"title": "deal", "url": "https://news.example/deal", "snippet": "x"}]
            else:
                tag = query.split("#")[-1]
                rows = [{"title": f"t{tag}", "url": f"https://ex{tag}.com", "snippet": "s"}]
            return ProviderSearchResults(
                rows,
                {
                    "provider": "tavily",
                    "outcome": "success",
                    "reason": None,
                    "result_count": len(rows),
                },
            )
        finally:
            with self._lock:
                self._in_flight -= 1


@pytest.fixture
def provider(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr("utils.search_providers.tavily_search", recorder)
    return recorder


def _queries(n):
    return [f"q#{i}" for i in range(n)]


# --------------------------------------------------------------------------- #
# Determinism: parallel and sequential must agree
# --------------------------------------------------------------------------- #


def test_merged_result_is_identical_sequential_vs_parallel(monkeypatch, provider):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "1")
    sequential = retrieve_source_pack_merged(
        queries=_queries(6), user_id="u1", max_total_sources=20
    )
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    parallel = retrieve_source_pack_merged(
        queries=_queries(6), user_id="u1", max_total_sources=20
    )
    assert [s["url"] for s in sequential["sources"]] == [
        s["url"] for s in parallel["sources"]
    ]
    assert [s["source_id"] for s in parallel["sources"]] == [
        f"S{i + 1}" for i in range(6)
    ]


def test_merge_order_follows_query_order(monkeypatch, provider):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    pack = retrieve_source_pack_merged(
        queries=_queries(5), user_id="u1", max_total_sources=20
    )
    assert [s["url"] for s in pack["sources"]] == [
        f"https://ex{i}.com" for i in range(5)
    ]


def test_duplicate_urls_are_still_deduped(monkeypatch):
    def same_url(query, max_results, time_range=None, topic=None, days=None):
        return ProviderSearchResults(
            [{"title": "dup", "url": "https://same.example/a", "snippet": "s"}],
            {"provider": "tavily", "outcome": "success", "reason": None, "result_count": 1},
        )

    monkeypatch.setattr("utils.search_providers.tavily_search", same_url)
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    pack = retrieve_source_pack_merged(queries=_queries(5), user_id="u1")
    assert len(pack["sources"]) == 1


# --------------------------------------------------------------------------- #
# Concurrency actually happens
# --------------------------------------------------------------------------- #


def test_queries_overlap_when_concurrency_is_enabled(monkeypatch):
    recorder = _Recorder(delay=0.05)
    monkeypatch.setattr("utils.search_providers.tavily_search", recorder)
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    retrieve_source_pack_merged(queries=_queries(4), user_id="u1", max_total_sources=20)
    assert recorder.max_in_flight > 1


def test_concurrency_one_stays_sequential(monkeypatch):
    recorder = _Recorder(delay=0.02)
    monkeypatch.setattr("utils.search_providers.tavily_search", recorder)
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "1")
    retrieve_source_pack_merged(queries=_queries(4), user_id="u1", max_total_sources=20)
    assert recorder.max_in_flight == 1


@pytest.mark.parametrize("value", ["0", "-3", "999", "not-a-number"])
def test_invalid_concurrency_values_are_clamped(monkeypatch, provider, value):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", value)
    pack = retrieve_source_pack_merged(
        queries=_queries(3), user_id="u1", max_total_sources=20
    )
    assert len(pack["sources"]) == 3


# --------------------------------------------------------------------------- #
# Recency reservation and cap survive parallelism
# --------------------------------------------------------------------------- #


def test_recency_result_is_still_ingested_first(monkeypatch, provider):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    pack = retrieve_source_pack_merged(
        queries=_queries(4),
        recency_query="acme latest news acquisition",
        user_id="u1",
        max_total_sources=20,
    )
    assert pack["sources"][0]["url"] == "https://news.example/deal"


def test_recency_survives_a_cap_the_general_queries_would_fill(monkeypatch):
    def flood(query, max_results, time_range=None, topic=None, days=None):
        if "acquisition" in query:
            rows = [{"title": "deal", "url": "https://news.example/deal", "snippet": "x"}]
        else:
            rows = [
                {"title": f"g{i}", "url": f"https://g{i}.example", "snippet": "x"}
                for i in range(8)
            ]
        return ProviderSearchResults(
            rows,
            {"provider": "tavily", "outcome": "success", "reason": None, "result_count": len(rows)},
        )

    monkeypatch.setattr("utils.search_providers.tavily_search", flood)
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    pack = retrieve_source_pack_merged(
        queries=_queries(3),
        recency_query="acme latest news acquisition",
        user_id="u1",
        max_per_query=8,
        max_total_sources=5,
    )
    assert "https://news.example/deal" in [s["url"] for s in pack["sources"]]


def test_the_source_cap_still_stops_later_waves(monkeypatch, provider):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "2")
    pack = retrieve_source_pack_merged(
        queries=_queries(8), user_id="u1", max_total_sources=5
    )
    assert len(pack["sources"]) == 5
    # Waves stop once the cap is reached, so not every query is issued.
    assert len(provider.queries) < 8


def test_provider_diagnostics_are_collected_from_every_query(monkeypatch, provider):
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    pack = retrieve_source_pack_merged(
        queries=_queries(3), user_id="u1", max_total_sources=20
    )
    assert len(pack["provider_diagnostics"]) == 3
    assert pack["provider"] == "tavily"


def test_a_failing_query_does_not_sink_the_wave(monkeypatch):
    def flaky(query, max_results, time_range=None, topic=None, days=None):
        if query.endswith("#1"):
            raise RuntimeError("provider blew up")
        tag = query.split("#")[-1]
        return ProviderSearchResults(
            [{"title": f"t{tag}", "url": f"https://ex{tag}.com", "snippet": "s"}],
            {"provider": "tavily", "outcome": "success", "reason": None, "result_count": 1},
        )

    monkeypatch.setattr("utils.search_providers.tavily_search", flaky)
    monkeypatch.setenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    monkeypatch.setenv("RETRIEVAL_FALLBACK_ENABLED", "0")
    pack = retrieve_source_pack_merged(
        queries=_queries(3), user_id="u1", max_total_sources=20
    )
    urls = [s["url"] for s in pack["sources"]]
    assert "https://ex0.com" in urls and "https://ex2.com" in urls
