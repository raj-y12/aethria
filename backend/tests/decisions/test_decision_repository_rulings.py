import pytest

from decisions.repository import DecisionRepository


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows


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
