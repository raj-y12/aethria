"""
Burst-reduction follow-up (see memory/project_render_oom_diagnosis.md):
- get_active_thesis caches the resolved triad per user (collapses in-cycle / poll bursts).
- get_active_thesis_metadata never pulls the embedding_vector (model column only).
- compute_thesis_alignment_stats projects 3 JSON sub-fields instead of full review_info blobs.
"""
from typing import Any, Dict, List

import pytest

import fund_thesis
from fund_thesis import (
    ActiveThesisMeta,
    compute_thesis_alignment_stats,
    get_active_thesis,
    get_active_thesis_metadata,
    invalidate_thesis_cache,
)


@pytest.fixture(autouse=True)
def _clear_thesis_cache():
    invalidate_thesis_cache()
    yield
    invalidate_thesis_cache()


# ---------------------------------------------------------------------------
# Recording fake Supabase client. Records every (table, select) issued so we can
# assert query volume and which columns were projected.
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, data: List[Dict[str, Any]], count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, client: "_FakeClient", table: str):
        self._client = client
        self._table = table
        self._select = ""

    def select(self, cols, **_kwargs):
        self._select = cols
        self._client.calls.append((self._table, cols))
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def range(self, *_a, **_k):
        return self

    @property
    def not_(self):
        return self

    def is_(self, *_a, **_k):
        return self

    def execute(self):
        return self._client._resolve(self._table, self._select)


class _FakeClient:
    def __init__(self, *, fund_thesis_row, version_row, embedding_row, startups=None):
        self.calls: List = []
        self._fund_thesis_row = fund_thesis_row
        self._version_row = version_row
        self._embedding_row = embedding_row
        self._startups = startups or []

    def table(self, name):
        return _FakeQuery(self, name)

    def _resolve(self, table: str, select: str) -> _FakeResp:
        if table == "fund_thesis":
            return _FakeResp([self._fund_thesis_row] if self._fund_thesis_row else [])
        if table == "fund_thesis_versions":
            return _FakeResp([self._version_row] if self._version_row else [])
        if table == "fund_thesis_embeddings":
            if not self._embedding_row:
                return _FakeResp([])
            # Honor projection: metadata path selects only "model".
            if select == "model":
                return _FakeResp([{"model": self._embedding_row.get("model")}])
            return _FakeResp([self._embedding_row])
        if table == "startups":
            return _FakeResp(self._startups)
        return _FakeResp([])


def _client(**kw):
    defaults = dict(
        fund_thesis_row={"id": "t1", "active_version_id": "v1"},
        version_row={
            "id": "v1",
            "thesis_id": "t1",
            "version_number": 1,
            "raw_text": "We invest in B2B SaaS.",
            "parsed_json": {"sectors": ["B2B SaaS"]},
            "is_active": True,
            "user_id": "u1",
        },
        embedding_row={"embedding_vector": [0.1, 0.2, 0.3], "model": "text-embedding-3-small"},
    )
    defaults.update(kw)
    return _FakeClient(**defaults)


def test_get_active_thesis_caches_triad(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    c = _client()

    first = get_active_thesis(c, "u1")
    assert first is not None and first.version_id == "v1"
    # 3 queries: fund_thesis, fund_thesis_versions, fund_thesis_embeddings
    assert len(c.calls) == 3

    second = get_active_thesis(c, "u1")
    assert second is second  # cached identity
    assert len(c.calls) == 3  # no new queries on cache hit


def test_invalidate_forces_refetch(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    c = _client()
    get_active_thesis(c, "u1")
    assert len(c.calls) == 3
    invalidate_thesis_cache("u1")
    get_active_thesis(c, "u1")
    assert len(c.calls) == 6  # full triad re-issued after invalidation


def test_cache_disabled_when_ttl_zero(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "0")
    c = _client()
    get_active_thesis(c, "u1")
    get_active_thesis(c, "u1")
    assert len(c.calls) == 6  # no caching, triad twice


def test_metadata_does_not_pull_embedding_vector(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    c = _client()
    meta = get_active_thesis_metadata(c, "u1")
    assert isinstance(meta, ActiveThesisMeta)
    assert meta.has_embeddings is True
    assert meta.embedding_model == "text-embedding-3-small"
    assert meta.embedding_dim == 1536  # derived from model, not from a fetched vector
    embedding_selects = [cols for (tbl, cols) in c.calls if tbl == "fund_thesis_embeddings"]
    assert embedding_selects == ["model"]  # never selected embedding_vector


def test_metadata_rule_based_when_model_none(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    c = _client(embedding_row={"embedding_vector": [], "model": "none"})
    meta = get_active_thesis_metadata(c, "u1")
    assert meta.has_embeddings is False
    assert meta.embedding_model == "none"
    assert meta.embedding_dim == 0


def test_metadata_derived_from_warm_full_cache(monkeypatch):
    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    c = _client()
    get_active_thesis(c, "u1")  # warms full cache (3 calls)
    assert len(c.calls) == 3
    meta = get_active_thesis_metadata(c, "u1")  # served from full cache, no new query
    assert meta.has_embeddings is True
    assert meta.embedding_dim == 3  # exact length from the cached full vector
    assert len(c.calls) == 3


def test_alignment_stats_uses_projected_query():
    # Rows shaped like the PostgREST projection aliases (scalar strings, not blobs).
    startups = [
        {"v": "vA", "s": "0.8", "s2": None, "m": "true"},
        {"v": "vA", "s": "0.4", "s2": None, "m": "false"},
        {"v": "vA", "s": None, "s2": "0.7", "m": None},  # high score, no explicit match
        {"v": "vOld", "s": "0.9", "s2": None, "m": "true"},  # previous version
    ]
    c = _client(startups=startups)
    stats = compute_thesis_alignment_stats(
        c, "u1", active_version_id="vA", previous_version_id="vOld", row_limit=500
    )
    # The startups query must project sub-fields, not the whole review_info blob.
    startup_selects = [cols for (tbl, cols) in c.calls if tbl == "startups"]
    assert startup_selects, "no startups query issued"
    assert "review_info->>fund_thesis_version_id" in startup_selects[0]
    assert startup_selects[0] != "review_info"

    assert stats["reviewed_with_thesis_count"] == 3  # three vA rows
    # matches: row1 true, row2 false, row3 (None + score 0.7>=0.6) -> 2 of 3
    assert stats["pct_matching_thesis"] == pytest.approx(66.7, abs=0.1)
    assert stats["avg_alignment_score"] == pytest.approx((0.8 + 0.4 + 0.7) / 3, abs=1e-3)
    assert stats["drift_vs_previous"] is not None  # prev had 0.9


# ---------------------------------------------------------------------------
# Endpoint-level: /api/fund-thesis/runtime folds its per-poll queries.
# ---------------------------------------------------------------------------
class _RuntimeQuery:
    def __init__(self, client, table):
        self._client = client
        self._table = table
        self._select = ""

    def select(self, cols, **_kwargs):
        self._select = cols
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    @property
    def not_(self):
        return self

    def is_(self, *_a, **_k):
        return self

    def execute(self):
        self._client.calls.append((self._table, self._select))
        if self._table == "fund_thesis":
            return _FakeResp([{"id": "t1", "active_version_id": "v2", "updated_at": "2026-06-14T00:00:00Z"}])
        if self._table == "fund_thesis_versions":
            if "raw_text" in self._select:  # active-version resolve
                return _FakeResp([{
                    "id": "v2", "thesis_id": "t1", "version_number": 2,
                    "raw_text": "x", "parsed_json": {}, "is_active": True, "user_id": "u1",
                }])
            # timeline (desc); includes the predecessor v1
            return _FakeResp([
                {"id": "v2", "version_number": 2, "is_active": True, "created_at": "c2"},
                {"id": "v1", "version_number": 1, "is_active": False, "created_at": "c1"},
            ])
        if self._table == "fund_thesis_embeddings":
            return _FakeResp([{"model": "none"}])
        if self._table == "startups":
            return _FakeResp([])
        return _FakeResp([])


class _RuntimeClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return _RuntimeQuery(self, name)


def test_runtime_endpoint_folds_queries(monkeypatch):
    import api

    monkeypatch.setenv("FUND_THESIS_CACHE_TTL_SECONDS", "30")
    invalidate_thesis_cache()
    client = _RuntimeClient()
    monkeypatch.setattr(api, "_require_supabase_for_thesis", lambda: None)
    monkeypatch.setattr(api, "get_service_client", lambda: client)

    from types import SimpleNamespace
    request = SimpleNamespace(state=SimpleNamespace(user_id="u1"))
    resp = api.get_fund_thesis_runtime(request)

    import json
    body = json.loads(resp.body)
    assert body["mode"] == "rule_based"
    assert body["fund_thesis_updated_at"] == "2026-06-14T00:00:00Z"

    fund_thesis_calls = [c for c in client.calls if c[0] == "fund_thesis"]
    version_selects = [sel for (tbl, sel) in client.calls if tbl == "fund_thesis_versions"]
    # The redundant second fund_thesis (updated_at) read is gone: exactly one, and it
    # carries updated_at so the payload field is served from that single resolve.
    assert len(fund_thesis_calls) == 1
    assert "updated_at" in fund_thesis_calls[0][1]
    # No separate point query for the predecessor version (select == "id"); prev_id is
    # derived from the timeline. Two version queries total: resolve + timeline.
    assert "id" not in version_selects  # the dropped prev point-query selected only "id"
    assert len(version_selects) == 2
