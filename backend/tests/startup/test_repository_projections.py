import pytest
from types import SimpleNamespace

from api import _list_projection_to_frontend
from startup_repository import StartupRepository, _queue_reasons_for_startup


class _Connection:
    def __init__(self):
        self.sql = ""

    async def fetch(self, sql, *args):
        self.sql = sql
        return [
            {
                "startup_id": "startup-1",
                "human_resolution": '{"decision":"NO","resolved_at":"2026-08-12T10:00:00+00:00"}',
            }
        ]


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_list_projection_preserves_human_resolution_for_portfolio_history():
    connection = _Connection()

    rows = await StartupRepository(_Pool(connection)).list_projection("user-a")

    assert "human_resolution" in connection.sql
    assert rows[0]["human_resolution"] == {
        "decision": "NO",
        "resolved_at": "2026-08-12T10:00:00+00:00",
    }


def test_list_projection_maps_institutional_monitor_to_legacy_maybe():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-monitor",
            "human_resolution": {
                "decision": "MONITOR",
                "notes": "Keep watching.",
            },
        }
    )

    assert projected["human_resolution"] == {
        "decision": "MAYBE",
        "notes": "Keep watching.",
    }


def test_list_projection_never_exposes_legacy_reviewer_score_as_priority():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-legacy-score",
            "display_name": "Legacy Score Co",
            "list_verdict": "STRONG",
            "list_score": 9.0,
            "short_summary": "Historical reviewer output.",
        }
    )

    assert projected["review"].get("overall_score") is None
    assert projected["review"].get("aggregate_score") is None
    assert projected["priority_reason"].startswith("Priority pending")


def test_list_projection_rebuilds_stored_legacy_numeric_priority():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-stale-priority",
            "display_name": "Stale Priority Co",
            "list_verdict": "STRONG",
            "priority_reason": "Priority 90 · Reviewed · B2B SaaS",
            "list_sector": "B2B SaaS",
        }
    )

    assert projected["priority_reason"] == "Priority pending · Reviewer output ready for partner judgement · B2B SaaS"


def test_postgres_queue_reason_never_reconstructs_legacy_reviewer_score():
    startup = SimpleNamespace(
        scout_info=SimpleNamespace(sector="B2B SaaS"),
        review_info=SimpleNamespace(
            market_score=9.0,
            product_score=9.0,
            technical_score=9.0,
            execution_score=9.0,
        ),
        partner_info=None,
        human_resolution=None,
    )

    _, priority_reason = _queue_reasons_for_startup(startup)

    assert priority_reason == "Priority pending · Reviewed · B2B SaaS"
