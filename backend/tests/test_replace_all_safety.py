"""replace_all must be non-destructive: upsert-first, prune-after, never a
delete-everything-then-reinsert that can wipe a tenant on partial failure."""
from types import SimpleNamespace

import pytest

from supabase_storage import SupabaseStartupsStorage


class _Builder:
    def __init__(self, store):
        self.store = store
        self._op = None
        self._payload = None
        self._in_ids = None

    def select(self, *a, **k):
        self._op = "select"
        return self

    def upsert(self, payload, *a, **k):
        self.store["ops"].append("upsert")
        for row in payload:
            self.store["rows"][str(row["startup_id"])] = dict(row)
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, _col, ids):
        self._in_ids = list(ids)
        return self

    def execute(self):
        if self._op == "select":
            return SimpleNamespace(
                data=[{"startup_id": sid} for sid in self.store["rows"].keys()]
            )
        if self._op == "delete":
            self.store["ops"].append("delete")
            for sid in (self._in_ids or []):
                self.store["rows"].pop(str(sid), None)
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self, store):
        self.store = store

    def table(self, _name):
        return _Builder(self.store)


def _row(sid, name="Co"):
    # Minimal shape _dict_to_row accepts: a startup dict with scout_info.
    return {
        "startup_id": sid,
        "scout_info": {"startup_id": sid, "name": name, "one_line": "", "sector": "",
                       "problem": "", "solution": "", "target_users": "", "why_now": "",
                       "scout_type": "market_driven", "confidence_score": 0.5},
    }


def _store(initial_ids):
    return {"ops": [], "rows": {sid: {"startup_id": sid} for sid in initial_ids}}


def test_replace_all_upserts_before_any_delete():
    store = _store(["a", "b", "c"])  # existing
    storage = SupabaseStartupsStorage(_Client(store), "u1")
    storage.replace_all([_row("a"), _row("d")])  # keep a, add d, drop b & c

    # The very first mutating op must be an upsert, never a delete.
    assert store["ops"][0] == "upsert"
    # Final set is exactly the new set.
    assert set(store["rows"].keys()) == {"a", "d"}
    # b and c were pruned (after the upserts).
    assert "delete" in store["ops"]
    assert store["ops"].index("upsert") < store["ops"].index("delete")


def test_replace_all_partial_upsert_failure_leaves_data_intact():
    store = _store(["a", "b"])

    class _FailingClient(_Client):
        def table(self, _name):
            b = _Builder(self.store)
            orig = b.upsert

            def boom(*a, **k):
                raise RuntimeError("transient upsert failure")

            b.upsert = boom
            return b

    storage = SupabaseStartupsStorage(_FailingClient(store), "u1")
    with pytest.raises(RuntimeError):
        storage.replace_all([_row("x")])
    # No delete ran, existing rows untouched — no wipe on failure.
    assert "delete" not in store["ops"]
    assert set(store["rows"].keys()) == {"a", "b"}
