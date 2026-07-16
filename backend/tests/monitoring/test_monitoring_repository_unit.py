from collections import deque

import pytest

from monitoring.repository import MonitoringRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self):
        self.fetchrows = deque(
            [
                {"current_evaluation_id": "evaluation-1"},
                {
                    "material_change_check_id": "check-1",
                    "detail": {"claim_count": 0},
                    "material_change": False,
                },
            ]
        )
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.popleft()

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return "snapshot-1"

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return []


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
async def test_material_change_reads_the_immutable_evaluation_schema_columns():
    connection = _Connection()
    repository = MonitoringRepository(_Pool(connection))

    await repository.check_material_change(
        user_id="user-a",
        opportunity_id="opportunity-1",
        job_id="job-1",
        reason="human_request",
    )

    evaluation_sql = next(
        sql.lower()
        for operation, sql, _ in connection.calls
        if operation == "fetchval" and "evaluation_runs" in sql
    )
    assert "evidence_snapshot_hash" in evaluation_sql
    assert "evaluation_id=$2" in evaluation_sql
    assert "claim_snapshot_hash" not in evaluation_sql
    assert "evaluation_run_id" not in evaluation_sql
