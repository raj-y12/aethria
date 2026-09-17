"""Post-hoc re-review (POST /api/startups/{id}/rerun) persistence path.

prepare_rerun_startup must keep the existing scout profile EXACTLY as-is (no
re-discovery), stamp the operator context where the reviewer prompt reads it,
and preserve existing review/partner/memo/human ruling until replacement stages
finish so canceling a re-review does not hide the startup. It intentionally uses
a full-row upsert so the derived list_* projection columns are refreshed too.
"""
from types import SimpleNamespace

from models import Financials, PartnerInfo, PartnerSnapshot, ReviewInfo, ScoutInfo, Startup
from pipeline_runner import _OPERATOR_URL_RE
from legacy_supabase.storage import SupabaseStartupsStorage, _dict_to_row


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
        references=["https://acme.example"],
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


def _partner():
    return PartnerInfo(
        thesis="t",
        why_this_matters="w",
        snapshot=PartnerSnapshot(one_liner="ol"),
        market_insight="mi",
        product_edge="pe",
        risks=["r"],
        recommendation="MONITOR",
        decision_rationale="old decision",
        confidence=0.7,
        next_action="track",
    )


def _existing_startup():
    st = Startup(
        startup_id="s1",
        scout_info=_scout(),
        review_info=_review(),
        partner_info=_partner(),
        financials=Financials(),
    )
    st.human_resolution = {"resolved_at": "2026-06-01T00:00:00+00:00", "decision": "PASS"}
    st.investment_memo_markdown = "# Old memo"
    st.first_seen_at = st.created_at
    return st


def test_prepare_rerun_keeps_scout_and_preserves_downstream_until_replacement():
    st = _existing_startup()
    store = {"rows": [_dict_to_row(st.to_dict(), "user-1")], "updates": [], "upserts": []}
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    sid = storage.prepare_rerun_startup(
        "s1",
        operator_context="Raised $2.1M pre-seed (unannounced).",
        lookup_id="new-lookup",
    )

    assert sid == "s1"
    # Full-row upsert (refreshes derived list_* projections), not a partial patch.
    assert len(store["upserts"]) == 1
    row = store["upserts"][0]
    assert row["startup_id"] == "s1"
    scout = row.get("scout_info") or {}
    # Scout profile survives untouched — NO re-discovery.
    assert scout.get("one_line") == "one"
    assert scout.get("references") == ["https://acme.example"]
    # Operator context lands where the reviewer prompt reads it.
    assert scout.get("operator_context") == "Raised $2.1M pre-seed (unannounced)."
    # New lookup correlation id so the UI's pending-match keys on the re-run.
    assert scout.get("lookup_id") == "new-lookup"
    # Downstream stages are preserved until replacements are written. Reviewer
    # and partner use force_rerun=True, so this does not block re-processing.
    assert row.get("review_info", {}).get("overall_summary") == "reviewed"
    assert row.get("partner_info", {}).get("decision_rationale") == "old decision"
    assert row.get("human_resolution", {}).get("decision") == "PASS"
    assert row.get("investment_memo_markdown") == "# Old memo"
    # Queue-awareness timestamps survive the overwrite (row serializer may use Z suffix).
    def _iso(v):
        from datetime import datetime

        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

    assert _iso(row.get("created_at")) == st.created_at
    assert _iso(row.get("first_seen_at")) == st.first_seen_at


def test_prepare_rerun_refuses_when_row_is_missing():
    store = {"rows": [], "updates": [], "upserts": []}
    storage = SupabaseStartupsStorage(_Client(store), "user-1")

    sid = storage.prepare_rerun_startup("s1", operator_context="ctx", lookup_id=None)
    assert sid is None
    assert store["upserts"] == []


def test_operator_url_regex_finds_links_in_context():
    text = (
        "Pilot live with two design partners, see https://acme.example/case-study "
        "and (https://news.example/acme-raise). No other links."
    )
    assert _OPERATOR_URL_RE.findall(text)[:3] == [
        "https://acme.example/case-study",
        "https://news.example/acme-raise",
    ]
