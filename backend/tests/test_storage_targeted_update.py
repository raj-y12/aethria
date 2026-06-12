"""Targeted-column write path for SupabaseStartupsStorage.

Pipeline stage handoffs must update only the columns that changed, so an
unchanged ~20 KB review_info blob is never rewritten on a partner decision.
These tests use a recording fake client and assert on the UPDATE payload shape.
"""
from types import SimpleNamespace

from models import (
    Financials,
    PartnerInfo,
    PartnerSnapshot,
    ReviewInfo,
    ScoutInfo,
    Startup,
)
from supabase_storage import SupabaseStartupsStorage, _dict_to_row


class _Builder:
    def __init__(self, store):
        self.store = store
        self.kind = None
        self.payload = None

    def select(self, *a, **k):
        self.kind = "select"
        return self

    def update(self, payload, **kwargs):
        self.kind = "update"
        self.payload = payload
        return self

    def upsert(self, payload, *a, **k):
        self.kind = "upsert"
        self.payload = payload
        self.store["upserts"].append(dict(payload))
        return self

    def eq(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def execute(self):
        if self.kind == "update":
            self.store["updates"].append(dict(self.payload))
            return SimpleNamespace(data=[])
        if self.kind == "select":
            return SimpleNamespace(data=[dict(r) for r in self.store["rows"]], count=len(self.store["rows"]))
        return SimpleNamespace(data=[], count=0)


class _Client:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _Builder(self.store)


def _scout(name="Acme"):
    return ScoutInfo(
        startup_id="s1",
        name=name,
        one_line="one",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="now",
        scout_type="market_driven",
        confidence_score=0.7,
    )


def _review():
    return ReviewInfo(
        market_score=7,
        product_score=6,
        technical_score=6,
        execution_score=7,
        overall_summary="x" * 5000,  # simulate the heavy review blob
        key_risks=["r1"],
        verdict="MEDIUM",
    )


def _partner():
    return PartnerInfo(
        thesis="t",
        why_this_matters="w",
        snapshot=PartnerSnapshot(one_liner="ol"),
        market_insight="mi",
        product_edge="pe",
        risks=["r"],
        recommendation="MONITOR",
        decision_rationale="dr",
        confidence=0.6,
        next_action="na",
    )


def _store_with(st: Startup):
    return {"rows": [_dict_to_row(st.to_dict(), "user-1")], "updates": [], "upserts": []}


def test_partner_decision_does_not_rewrite_review_info():
    st = Startup(startup_id="s1", scout_info=_scout(), review_info=_review(), financials=Financials())
    store = _store_with(st)
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    assert storage.add_partner_decision("s1", _partner(), pipeline_run_id=None) is True

    assert len(store["updates"]) == 1
    assert store["upserts"] == []  # no full-row upsert
    cols = set(store["updates"][0].keys())
    assert "partner_info" in cols
    assert "review_info" not in cols  # the big unchanged blob is not rewritten
    assert "scout_info" not in cols
    assert cols <= {
        "partner_info", "agent_trace", "unresolved_at",
        "queue_reason", "priority_reason", "updated_at",
    }


def test_review_write_touches_review_columns_only():
    st = Startup(startup_id="s1", scout_info=_scout(), financials=Financials())
    store = _store_with(st)
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    assert storage.add_review("s1", _review(), pipeline_run_id=None) is True

    assert len(store["updates"]) == 1
    cols = set(store["updates"][0].keys())
    assert "review_info" in cols
    assert "partner_info" not in cols
    assert "financials" not in cols
    assert cols <= {
        "scout_info", "review_info", "agent_trace",
        "queue_reason", "priority_reason", "updated_at",
    }


def test_update_startup_partial_writes_only_patched_columns():
    st = Startup(startup_id="s1", scout_info=_scout(), review_info=_review(), financials=Financials())
    store = _store_with(st)
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    assert storage.update_startup_partial("s1", {"acknowledged_at": "2026-06-04T00:00:00+00:00"}) is True

    assert len(store["updates"]) == 1
    cols = set(store["updates"][0].keys())
    assert "acknowledged_at" in cols
    # queue reasons are recomputed, updated_at always bumped
    assert {"queue_reason", "priority_reason", "updated_at"} <= cols
    # unrelated heavy blobs are untouched
    assert "review_info" not in cols
    assert "scout_info" not in cols
    assert "partner_info" not in cols


def test_update_columns_strips_identity_keys():
    storage = SupabaseStartupsStorage(_Client({"rows": [], "updates": [], "upserts": []}), "user-1")
    store = storage._client.store
    storage._update_startup_columns(
        "s1",
        {"user_id": "user-1", "startup_id": "s1", "created_at": "x", "review_info": {"k": 1}},
    )
    assert len(store["updates"]) == 1
    cols = set(store["updates"][0].keys())
    assert cols == {"review_info"}
