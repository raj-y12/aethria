from types import SimpleNamespace

import pytest

from api import _backend_to_frontend, acknowledge_startup
from routers.analytics import (
    _aggregate_activity_totals,
    get_activity_summary,
    mark_activity_seen,
)


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

    class FakeRepository:
        async def acknowledge_startup(self, user_id, startup_id, seen_at):
            patch = {
                "acknowledged_at": seen_at.isoformat(),
                "last_seen_by_user_at": seen_at.isoformat(),
            }
            captured_patch.update(patch)
            updated.update(patch)
            return startup_id == "s1"

        async def get_startup(self, user_id, startup_id):
            return updated if startup_id == "s1" else None

    monkeypatch.setattr("api._get_startup_repository", lambda request: FakeRepository())

    result = await acknowledge_startup(SimpleNamespace(state=SimpleNamespace(user_id="user_123")), "s1")

    assert captured_patch["acknowledged_at"]
    assert captured_patch["last_seen_by_user_at"] == captured_patch["acknowledged_at"]
    assert result["id"] == "s1"
    assert result["is_new_to_user"] is False


@pytest.mark.asyncio
async def test_mark_activity_seen_reports_persistence_failure(monkeypatch):
    class BrokenConnection:
        def __init__(self):
            self.pool = self

        def acquire(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def execute(self, *_args):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr("routers.analytics.require_authenticated_user", lambda request: "user_123")
    def no_rate_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("routers.analytics._enforce_rate_limits", no_rate_limit)
    pool = BrokenConnection()

    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user_123"),
        app=SimpleNamespace(state=SimpleNamespace(durable_job_pool=pool)),
    )
    response = await mark_activity_seen(request)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_activity_summary_fails_closed_without_postgres_pool():
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user_123"),
        app=SimpleNamespace(state=SimpleNamespace(durable_job_pool=None)),
    )

    response = await get_activity_summary(request)

    assert response.status_code == 503
    assert response.body == (
        b'{"status":"unavailable","reason":"durable_job_store_unavailable"}'
    )
