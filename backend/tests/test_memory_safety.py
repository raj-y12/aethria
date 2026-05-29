from types import SimpleNamespace

import pytest

from models import ScoutInfo
from supabase_storage import SupabaseStartupsStorage


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
        ("select", "startup_id", (), {}),
    ]
    assert table.calls.count(("limit", 1)) >= 2


def test_startups_endpoint_uses_bounded_projection(monkeypatch):
    import api

    captured = {}

    class FakeStorage(SupabaseStartupsStorage):
        def __init__(self):
            pass

        def get_list_projection_rows(self, *, limit=None, offset=0):
            captured["limit"] = limit
            captured["offset"] = offset
            return []

    monkeypatch.setattr(api, "_get_storage", lambda request: FakeStorage())
    monkeypatch.setattr(api, "_get_user_last_seen_at", lambda user_id: None)

    result = api.get_startups(SimpleNamespace(state=SimpleNamespace(user_id="user-1")))

    assert result == []
    assert captured == {"limit": api.DEFAULT_STARTUPS_LIST_LIMIT, "offset": 0}


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
