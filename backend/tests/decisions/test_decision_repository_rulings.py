import json

import pytest

from decisions.models import HumanRulingInput
from decisions.repository import DecisionRepository


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows


class _CreateConnection:
    def __init__(self):
        self.fetchrows = [
            {
                "current_ruling_id": None,
                "current_recommendation_id": None,
                "recommended_state": "advance",
                "legacy_startup_id": "6df278f2-679f-4a7f-8dd9-27109904d093",
            },
            {"ruling_id": "ruling-a"},
        ]
        self.calls = []

    def transaction(self):
        return _Acquire(self)

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.pop(0)

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "INSERT 0 1"


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
async def test_list_rulings_is_tenant_scoped_and_newest_first():
    connection = _Connection([
        {
            "ruling_id": "ruling-2",
            "user_id": "user-a",
            "opportunity_id": "opportunity-1",
            "recommendation_id": "recommendation-1",
            "decision": "monitor",
            "rationale": "Wait for retention evidence.",
            "risk_acknowledgement": None,
            "mandate_exception": None,
            "investor_confidence": 0.7,
            "actor_id": "user-a",
            "prior_ruling_id": "ruling-1",
            "override_type": "timing",
            "override_note": None,
            "created_at": "2026-07-16T12:00:00Z",
        }
    ])
    repository = DecisionRepository(_Pool(connection))

    records = await repository.list_rulings(
        user_id="user-a",
        opportunity_id="opportunity-1",
        limit=20,
    )

    sql, args = connection.calls[0]
    assert "left join public.override_signals" in " ".join(sql.split()).lower()
    assert "where hr.user_id=$1 and hr.opportunity_id=$2" in " ".join(sql.split()).lower()
    assert "order by hr.created_at desc" in " ".join(sql.split()).lower()
    assert args == ("user-a", "opportunity-1", 20)
    assert records[0].ruling_id == "ruling-2"


@pytest.mark.asyncio
async def test_created_ruling_outbox_carries_legacy_startup_and_rationale():
    connection = _CreateConnection()
    repository = DecisionRepository(_Pool(connection))

    await repository.create_ruling(
        HumanRulingInput(
            user_id="user-a",
            opportunity_id="opportunity-a",
            decision="pass",
            rationale="Outside this fund's mandate.",
        ),
        actor_id="operator-a",
    )

    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == "6df278f2-679f-4a7f-8dd9-27109904d093"
    assert payload["rationale"] == "Outside this fund's mandate."
    assert payload["compatibility_reason"] == "Outside this fund's mandate."
