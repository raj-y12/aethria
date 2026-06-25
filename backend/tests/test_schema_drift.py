from types import SimpleNamespace

import supabase_storage as ss
from supabase_storage import detect_schema_drift


class _FakeQuery:
    def __init__(self, column, missing, transient):
        self.column = column
        self.missing = missing
        self.transient = transient

    def limit(self, _n):
        return self

    def execute(self):
        if self.transient:
            raise Exception("connection reset by peer")
        if self.column in self.missing:
            raise Exception(f"column startups.{self.column} does not exist (42703)")
        return SimpleNamespace(data=[])


class _FakeTable:
    def __init__(self, missing, transient):
        self.missing = missing
        self.transient = transient

    def select(self, column):
        return _FakeQuery(column, self.missing, self.transient)


class _FakeClient:
    def __init__(self, missing=(), transient=False):
        self.missing = set(missing)
        self.transient = transient

    def table(self, _t):
        return _FakeTable(self.missing, self.transient)


def test_no_drift_when_all_columns_present():
    assert detect_schema_drift(_FakeClient()) == []


def test_reports_missing_columns():
    missing = detect_schema_drift(_FakeClient(missing={"agent_trace", "unresolved_at"}))
    assert "agent_trace" in missing
    assert "unresolved_at" in missing


def test_transient_errors_do_not_count_as_drift():
    # A network blip must not be misreported as a missing column.
    assert detect_schema_drift(_FakeClient(transient=True)) == []


def test_probes_every_expected_optional_column():
    # Each known late-migration column should be probed (all reported missing here).
    missing = detect_schema_drift(_FakeClient(missing=set(ss._EXPECTED_OPTIONAL_COLUMNS)))
    assert set(missing) == set(ss._EXPECTED_OPTIONAL_COLUMNS)
