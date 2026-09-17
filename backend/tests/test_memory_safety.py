from types import SimpleNamespace

import pytest

from models import ScoutInfo
from legacy_supabase.storage import SupabaseStartupsStorage


class _FakeTable:
    def __init__(self, response_rows=None):
        self.calls = []
        self.response_rows = response_rows or []

    def select(self, columns, *args, **kwargs):
        self.calls.append(("select", columns, args, kwargs))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.calls.append(("ilike", column, value))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def upsert(self, payload, *args, **kwargs):
        self.calls.append(("upsert", payload, args, kwargs))
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.response_rows), count=len(self.response_rows))


class _FakeClient:
    def __init__(self, table):
        self._table = table

    def table(self, name):
        assert name == "startups"
        return self._table


def _scout_info(startup_id="s1", name="TraceCo"):
    return ScoutInfo(
        startup_id=startup_id,
        name=name,
        one_line="Traceable decisions",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="n",
        scout_type="market_driven",
        confidence_score=0.7,
    )


def test_supabase_add_startup_duplicate_checks_are_targeted():
    table = _FakeTable()
    storage = SupabaseStartupsStorage(_FakeClient(table), "user-1")

    storage.add_startup(_scout_info())

    select_calls = [call for call in table.calls if call[0] == "select"]
    assert select_calls[:2] == [
        ("select", "startup_id", (), {}),
        ("select", "startup_id,display_name", (), {}),
    ]
    assert ("ilike", "display_name", "TraceCo") in table.calls
    assert ("limit", 1) in table.calls
    assert ("limit", 20) in table.calls


@pytest.mark.asyncio
async def test_startups_endpoint_uses_bounded_projection(monkeypatch):
    import api

    captured = {}

    class FakeRepository:
        async def list_projection(self, user_id, *, limit=100, offset=0):
            captured["limit"] = limit
            captured["offset"] = offset
            return []

    monkeypatch.setattr(api, "_get_startup_repository", lambda request: FakeRepository())
    async def no_last_seen(user_id):
        return None
    monkeypatch.setattr(api, "_get_user_last_seen_at", no_last_seen)

    result = await api.get_startups(SimpleNamespace(state=SimpleNamespace(user_id="user-1")))

    assert result == []
    assert captured == {"limit": api.DEFAULT_STARTUPS_LIST_LIMIT, "offset": 0}


@pytest.mark.asyncio
async def test_startups_endpoint_does_not_full_row_fallback_on_projection_failure(monkeypatch):
    """A failed projection (e.g. transient EAGAIN) must NOT trigger a full-row
    select(*) fetch -- that amplifier drove RSS/egress until OOM. Expect a 503."""
    import api
    from fastapi import HTTPException

    class FakeRepository:
        async def list_projection(self, user_id, *, limit=100, offset=0):
            raise HTTPException(status_code=503, detail="projection unavailable")

    monkeypatch.setattr(api, "_get_startup_repository", lambda request: FakeRepository())
    async def no_last_seen(user_id):
        return None
    monkeypatch.setattr(api, "_get_user_last_seen_at", no_last_seen)

    with pytest.raises(HTTPException) as exc:
        await api.get_startups(SimpleNamespace(state=SimpleNamespace(user_id="user-1")))

    assert exc.value.status_code == 503


def test_malloc_tuning_helpers_are_defensive():
    """Allocator tuning must be a safe no-op off glibc (e.g. macOS dev)."""
    from utils.malloc_tuning import cap_malloc_arenas, trim_malloc

    cap_malloc_arenas()
    cap_malloc_arenas(2)
    trim_malloc()


def test_resource_cleanup_helpers_are_defensive():
    from concurrent.futures import ThreadPoolExecutor

    from utils.resource_cleanup import close_openai_client, shutdown_executor

    # None and missing-method inputs must not raise.
    close_openai_client(None)
    shutdown_executor(None)
    close_openai_client(object())

    ex = ThreadPoolExecutor(max_workers=1)
    ex.submit(lambda: None).result()
    shutdown_executor(ex)
    assert ex._shutdown is True

    closed = {"value": False}

    class FakeClient:
        def close(self):
            closed["value"] = True

    close_openai_client(FakeClient())
    assert closed["value"] is True


def test_scout_engine_close_releases_clients_and_threads():
    """Engines are rebuilt every cycle; close() must release httpx pools + threads."""
    from scout.engine import ScoutEngine

    engine = ScoutEngine(api_key="sk-test", tenant_user_id="user-1")
    executors = [s.executor for s in engine.scouts]
    assert executors and all(not e._shutdown for e in executors)

    engine.close()

    assert all(e._shutdown for e in executors)


@pytest.mark.asyncio
async def test_portfolio_execution_uses_bounded_decision_query():
    from portfolio.engine import PortfolioEngine

    class FakeDiscoveryStorage:
        def __init__(self):
            self.limit = None

        def get_startups_with_decision(self, limit=None):
            self.limit = limit
            return []

        def get_all(self):
            raise AssertionError("execution cycle should not load every startup")

    class FakePortfolioStore:
        _tenant_user_id = "user-1"
        data_dir = "."

        def get_all_decisions(self):
            return []

    engine = PortfolioEngine(
        discovery_storage=FakeDiscoveryStorage(),
        portfolio_store=FakePortfolioStore(),
    )

    await engine._run_execution()

    assert engine.discovery_storage.limit == engine.execution_scan_limit
