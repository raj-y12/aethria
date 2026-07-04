"""Post-hoc re-review (POST /api/startups/{id}/rerun) persistence path.

rescout_startup must overwrite the scout stage IN PLACE on the existing row —
clearing review/partner/memo/human ruling so the pipeline re-runs cleanly —
while preserving queue-awareness timestamps. It intentionally uses a full-row
upsert so the derived list_* projection columns are refreshed too.
"""
from types import SimpleNamespace

from models import Financials, ReviewInfo, ScoutInfo, Startup
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

    def limit(self, *a, **k):
        return self

    def execute(self):
        if self.kind == "update":
            self.store["updates"].append(dict(self.payload))
            return SimpleNamespace(data=[])
        if self.kind == "select":
            return SimpleNamespace(
                data=[dict(r) for r in self.store["rows"]], count=len(self.store["rows"])
            )
        return SimpleNamespace(data=[], count=0)


class _Client:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _Builder(self.store)


def _scout():
    return ScoutInfo(
        startup_id="s1",
        name="Acme",
        one_line="one",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="now",
        scout_type="market_driven",
        confidence_score=0.7,
        lookup_id="old-lookup",
    )


def _review():
    return ReviewInfo(
        market_score=7,
        product_score=6,
        technical_score=6,
        execution_score=7,
        overall_summary="reviewed",
        key_risks=["r1"],
        verdict="MEDIUM",
    )


def _existing_startup():
    st = Startup(startup_id="s1", scout_info=_scout(), review_info=_review(), financials=Financials())
    st.human_resolution = {"resolved_at": "2026-06-01T00:00:00+00:00", "decision": "PASS"}
    st.first_seen_at = st.created_at
    return st


def _rescout_payload():
    return {
        "id": "s1",
        "name": "Acme",
        "one_line": "one, now with private context",
        "sector": "B2B SaaS",
        "problem": "p",
        "solution": "s",
        "target_users": "u",
        "why_now": "now",
        "scout_type": "market_driven",
        "confidence_score": 0.8,
        "origin_type": "on_demand_lookup",
        "lookup_id": "new-lookup",
    }


def test_rescout_overwrites_in_place_and_clears_downstream_stages():
    st = _existing_startup()
    store = {"rows": [_dict_to_row(st.to_dict(), "user-1")], "updates": [], "upserts": []}
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    sid = storage.rescout_startup(_rescout_payload(), pipeline_run_id=None)

    assert sid == "s1"
    # Full-row upsert (refreshes derived list_* projections), not a partial patch.
    assert len(store["upserts"]) == 1
    row = store["upserts"][0]
    assert row["startup_id"] == "s1"
    # Downstream stages cleared so reviewer/partner re-run cleanly.
    assert not row.get("review_info")
    assert not row.get("partner_info")
    assert not row.get("human_resolution")
    # New lookup correlation id lands so the UI's pending-match keys on the re-run.
    assert (row.get("scout_info") or {}).get("lookup_id") == "new-lookup"
    # Queue-awareness timestamps survive the overwrite (row serializer may use Z suffix).
    def _iso(v):
        from datetime import datetime

        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

    assert _iso(row.get("created_at")) == st.created_at
    assert _iso(row.get("first_seen_at")) == st.first_seen_at


def test_rescout_refuses_when_row_is_missing():
    store = {"rows": [], "updates": [], "upserts": []}
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    assert storage.rescout_startup(_rescout_payload(), pipeline_run_id=None) is None
    assert store["upserts"] == []
