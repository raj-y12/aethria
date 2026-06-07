"""P7.1 — SupabaseStartupsStorage.record_scoring_trail appends a scoring trail row.

Uses a recording fake client: asserts the insert targets the `scoring_trails` table,
denormalizes the right columns, embeds the full trace, and never raises into the caller.
"""
from types import SimpleNamespace

from supabase_storage import SupabaseStartupsStorage


class _InsertBuilder:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        self.store.setdefault(self.table, []).append(dict(self._payload))
        return SimpleNamespace(data=[self._payload])


class _RecordingClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _InsertBuilder(self.store, name)


class _RaisingClient:
    def table(self, name):
        raise RuntimeError("relation \"scoring_trails\" does not exist")


def _trace():
    return {
        "market": {"score": 7.0, "components": {}},
        "overall_score": 6.8,
        "overall_confidence": 0.55,
        "policy_version_id": "pol-1",
        "policy_hash": "abc123",
        "stage_cohort": "seed",
        "stage_cohort_label": "Seed",
        "sector_tam_benchmark": "Fintech (capital-heavy; large markets expected)",
    }


def test_record_scoring_trail_inserts_denormalized_row_and_full_trace():
    store: dict = {}
    storage = SupabaseStartupsStorage(_RecordingClient(store), "user-1")

    assert storage.record_scoring_trail("s1", _trace()) is True
    rows = store["scoring_trails"]
    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == "user-1"
    assert row["startup_id"] == "s1"
    assert row["overall_score"] == 6.8
    assert row["stage_cohort"] == "seed"
    assert row["sector_tam_benchmark"].startswith("Fintech")
    assert row["policy_hash"] == "abc123"
    # the full trace is embedded for replay/calibration
    assert row["trail"]["market"]["score"] == 7.0


def test_record_scoring_trail_swallows_errors_and_returns_false():
    storage = SupabaseStartupsStorage(_RaisingClient(), "user-1")
    # a missing table / DB error must never raise into the review pipeline
    assert storage.record_scoring_trail("s1", _trace()) is False


def test_record_scoring_trail_ignores_invalid_input():
    storage = SupabaseStartupsStorage(_RecordingClient({}), "user-1")
    assert storage.record_scoring_trail("", _trace()) is False
    assert storage.record_scoring_trail("s1", None) is False  # type: ignore[arg-type]
