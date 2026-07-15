from collections import deque

import pytest

from identity.reconciliation import reconcile_identity


class _Connection:
    def __init__(self, rows):
        self.rows = deque(rows)
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows.popleft()


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_reconciliation_reports_counts_only_and_flags_authoritative_drift():
    connection = _Connection(
        [
            {
                "legacy_rows": 20,
                "observations": 20,
                "companies": 18,
                "opportunities": 18,
                "unlinked_projections": 2,
                "duplicate_verified_identifiers": 0,
                "open_cases": 2,
                "tenant_drift": 0,
                "authoritative_legacy_only_after_activation": 1,
            }
        ]
    )

    report = await reconcile_identity(
        _Pool(connection), user_id="fund-a", activated_at="2026-07-15T00:00:00Z"
    )

    assert report.counts["companies"] == 18
    assert report.has_violations is True
    assert "authoritative_legacy_only_after_activation" in report.violations
    assert "user_id = $1" in connection.calls[0][0].lower()
    assert "scout_info" not in report.model_dump(mode="json")


@pytest.mark.asyncio
async def test_reconciliation_passes_when_constraints_and_linkage_are_clean():
    zero = {
        "legacy_rows": 10,
        "observations": 10,
        "companies": 8,
        "opportunities": 8,
        "unlinked_projections": 0,
        "duplicate_verified_identifiers": 0,
        "open_cases": 0,
        "tenant_drift": 0,
        "authoritative_legacy_only_after_activation": 0,
    }
    report = await reconcile_identity(
        _Pool(_Connection([zero])), user_id="fund-a"
    )

    assert report.has_violations is False
