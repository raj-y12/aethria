import pytest

from portfolio.repository import PortfolioRepository


class _Connection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
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
async def test_list_positions_exposes_legacy_bridge_and_is_tenant_scoped():
    connection = _Connection([
        {
            "position_id": "position-1",
            "user_id": "user-a",
            "opportunity_id": "opportunity-1",
            "company_id": "company-1",
            "ruling_id": "ruling-1",
            "status": "active",
            "entry_rationale": "Retention held through the pricing change.",
            "investor_confidence": 0.72,
            "entered_at": "2026-07-20T12:00:00Z",
            "canonical_name": "Acme",
            "canonical_domain": "acme.ai",
            "legacy_startup_id": "startup-1",
        }
    ])
    repository = PortfolioRepository(_Pool(connection))

    rows = await repository.list_positions(user_id="user-a", limit=10)

    assert rows[0]["legacy_startup_id"] == "startup-1"
    sql, args = connection.calls[0][1], connection.calls[0][2]
    assert "left join public.opportunities" in sql.lower()
    assert "o.legacy_startup_id" in sql
    assert "p.status='active'" in sql.lower()
    assert args[0] == "user-a"


@pytest.mark.asyncio
async def test_list_positions_rejects_missing_tenant():
    repository = PortfolioRepository(_Pool(_Connection([])))
    with pytest.raises(RuntimeError):
        await repository.list_positions(user_id="", limit=10)
