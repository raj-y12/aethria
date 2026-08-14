import pytest

from api import _list_projection_to_frontend
from startup_repository import StartupRepository


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
