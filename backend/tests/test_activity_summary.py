from types import SimpleNamespace

import pytest

from api import _backend_to_frontend, acknowledge_startup
from routers.analytics import _aggregate_activity_totals


def test_activity_totals_split_agent_and_human_decisions():
    totals = _aggregate_activity_totals(
        [
            {"startups_found": 2, "reviewed_count": 3, "decisions_made": 4, "escalations_count": 1},
            {"startups_found": 1, "reviewed_count": 0, "decisions_made": 2, "escalations_count": 0},
        ],
        human_reviewed=5,
        open_in_progress=7,
    )
    assert totals["decided"] == 6
    assert totals["agent_decided"] == 6
    assert totals["human_reviewed"] == 5
    assert totals["open_in_progress"] == 7


def test_backend_to_frontend_surfaces_unresolved_at():
    raw = {
        "startup_id": "s1",
        "scout_info": {
            "name": "TinyPay",
            "one_line": "Payments ops",
            "sector": "Fintech",
            "why_now": "Now",
            "confidence_score": 0.7,
            "scout_type": "market_driven",
        },
        "unresolved_at": "2026-05-12T10:00:00+00:00",
    }
    out = _backend_to_frontend(raw)
    assert out["unresolved_at"] == "2026-05-12T10:00:00+00:00"
    assert out["timestamps"]["unresolved_at"] == "2026-05-12T10:00:00+00:00"


def test_backend_to_frontend_surfaces_queue_awareness():
    raw = {
        "startup_id": "s1",
        "scout_info": {
            "name": "TinyPay",
            "one_line": "Payments ops",
            "sector": "Fintech",
            "why_now": "Now",
            "confidence_score": 0.7,
            "scout_type": "market_driven",
        },
        "first_seen_at": "2026-05-12T10:00:00+00:00",
        "last_seen_by_user_at": None,
        "acknowledged_at": None,
        "updated_at": "2026-05-13T10:00:00+00:00",
        "queue_reason": "New discovery awaiting review.",
        "priority_reason": "Priority 70 · New signal · Fintech",
    }

    out = _backend_to_frontend(raw, last_seen_at="2026-05-12T12:00:00+00:00")

    assert out["timestamps"]["first_seen_at"] == "2026-05-12T10:00:00+00:00"
    assert out["timestamps"]["last_seen_by_user_at"] is None
    assert out["timestamps"]["acknowledged_at"] is None
    assert out["is_new_to_user"] is True
    assert out["changed_since_last_visit"] is True
    assert out["queue_reason"] == "New discovery awaiting review."
    assert out["priority_reason"] == "Priority 70 · New signal · Fintech"


@pytest.mark.asyncio
async def test_acknowledge_startup_sets_seen_fields(monkeypatch):
    captured_patch = {}
    updated = {
        "startup_id": "s1",
        "scout_info": {
            "name": "TinyPay",
            "one_line": "Payments ops",
            "sector": "Fintech",
            "why_now": "Now",
            "confidence_score": 0.7,
            "scout_type": "market_driven",
        },
        "first_seen_at": "2026-05-12T10:00:00+00:00",
        "acknowledged_at": "2026-05-13T10:00:00+00:00",
        "last_seen_by_user_at": "2026-05-13T10:00:00+00:00",
    }

    class FakeStorage:
        def get_by_id(self, startup_id):
            return updated if startup_id == "s1" else None

        def update_startup_partial(self, startup_id, patch):
            captured_patch.update(patch)
            updated.update(patch)
            return startup_id == "s1"

    monkeypatch.setattr("api._get_storage", lambda request: FakeStorage())

    result = await acknowledge_startup(SimpleNamespace(state=SimpleNamespace(user_id="user_123")), "s1")

    assert captured_patch["acknowledged_at"]
    assert captured_patch["last_seen_by_user_at"] == captured_patch["acknowledged_at"]
    assert result["id"] == "s1"
    assert result["is_new_to_user"] is False
