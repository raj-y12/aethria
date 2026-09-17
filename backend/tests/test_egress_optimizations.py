"""Egress guards: pipeline reads/writes must not ship heavy JSONB they don't use.

Context: the portfolio execution scan re-downloaded every decided row (avg 24KB,
~20KB of which is review_info it never reads) every cycle, and all mutations
echoed the full row back (PostgREST returns the representation by default).
These tests pin the cheap query shapes so the egress fix doesn't regress.
"""

from types import SimpleNamespace

import pytest

from legacy_supabase.storage import SupabaseStartupsStorage


class _FakeTable:
    def __init__(self, response_rows=None):
        self.calls = []
        self.response_rows = response_rows or []

    def _record(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return method

    def __getattr__(self, name):
        # select/eq/is_/not_/order/limit/in_/update/upsert/insert/delete all chain.
        if name == "not_":
            self.calls.append(("not_", (), {}))
            return self
        return self._record(name)

    def execute(self):
        return SimpleNamespace(data=list(self.response_rows), count=len(self.response_rows))

    def select_columns(self):
        return [args[0] for name, args, _ in self.calls if name == "select" and args]

    def mutation_kwargs(self, name):
        return [kwargs for call_name, _, kwargs in self.calls if call_name == name]


class _FakeClient:
    def __init__(self, table):
        self._table = table

    def table(self, name):
        return self._table


def _storage(table):
    return SupabaseStartupsStorage(_FakeClient(table), "user-1")


def test_decision_scan_excludes_heavy_unused_columns():
    """Portfolio execution scan must not download review_info/trace/memo blobs."""
    table = _FakeTable()
    _storage(table).get_startups_with_decision(limit=200)

    selects = table.select_columns()
    assert selects, "expected a select call"
    cols = selects[0]
    assert cols != "*"
    assert "review_info" not in cols
    assert "agent_trace" not in cols
    assert "investment_memo_markdown" not in cols
    # Columns the execution agent actually consumes must stay.
    for needed in ("startup_id", "scout_info", "partner_info", "human_resolution"):
        assert needed in cols


def test_upsert_startup_dict_does_not_echo_row_back():
    table = _FakeTable()
    _storage(table).upsert_startup_dict({"startup_id": "s1", "scout_info": {}})

    kwargs = table.mutation_kwargs("upsert")
    assert kwargs and all(k.get("returning") == "minimal" for k in kwargs)


def test_targeted_column_update_does_not_echo_row_back():
    table = _FakeTable()
    _storage(table)._update_startup_columns("s1", {"review_info": {"big": "blob"}})

    kwargs = table.mutation_kwargs("update")
    assert kwargs and all(k.get("returning") == "minimal" for k in kwargs)


def test_scoring_trail_insert_does_not_echo_row_back():
    table = _FakeTable()
    assert _storage(table).record_scoring_trail("s1", {"rubric_version": "v1"}) is True

    kwargs = table.mutation_kwargs("insert")
    assert kwargs and all(k.get("returning") == "minimal" for k in kwargs)


@pytest.mark.asyncio
async def test_execution_fetches_full_row_only_for_new_decisions():
    """Already-executed decisions must not trigger full-row refetches; new ones
    get exactly one targeted get_startup to recover review_info for key_risks."""
    from portfolio.engine import PortfolioEngine

    light_entries = [
        {
            "startup_id": "old",
            "scout_info": {"id": "old", "name": "OldCo"},
            "partner_info": {"decision": "YES"},
        },
        {
            "startup_id": "new",
            "scout_info": {"id": "new", "name": "NewCo"},
            "partner_info": {"decision": "YES"},
        },
    ]

    class FakeDiscoveryStorage:
        def __init__(self):
            self.full_fetches = []

        def get_startups_with_decision(self, limit=None):
            return list(light_entries)

        def get_startup(self, startup_id):
            self.full_fetches.append(startup_id)
            return SimpleNamespace(
                to_dict=lambda: {
                    "startup_id": startup_id,
                    "scout_info": {"id": startup_id},
                    "partner_info": {"decision": "YES"},
                    "review_info": {"key_risks": ["r1"]},
                }
            )

        def get_all(self):
            raise AssertionError("execution cycle should not load every startup")

    class FakePortfolioStore:
        _tenant_user_id = "user-1"
        data_dir = "."

        def get_all_decisions(self):
            return [{"startup_id": "old"}]

        def get_startup(self, startup_id):
            return {"id": "old"} if startup_id == "old" else None

        def add_startup(self, *args, **kwargs):
            return "p1"

        def add_decision(self, *args, **kwargs):
            return "d1"

    discovery = FakeDiscoveryStorage()
    engine = PortfolioEngine(
        discovery_storage=discovery,
        portfolio_store=FakePortfolioStore(),
    )

    executed = []
    engine.execution_agent = SimpleNamespace(
        execute_decision=lambda **kwargs: executed.append(kwargs)
    )

    await engine._run_execution()

    assert discovery.full_fetches == ["new"]
    assert len(executed) == 1
    assert executed[0]["key_risks"] == ["r1"]
