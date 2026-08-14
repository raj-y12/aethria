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


@pytest.mark.asyncio
async def test_list_decision_history_includes_canonical_and_unlinked_legacy_rulings():
    connection = _Connection([
        {
            "history_id": "canonical:ruling-1",
            "startup_id": "startup-1",
            "opportunity_id": "opportunity-1",
            "canonical_name": "Acme",
            "decision": "monitor",
            "rationale": "Track retention.",
            "decided_at": "2026-08-10T10:00:00Z",
            "recommended_state": "monitor",
            "source": "canonical",
        },
        {
            "history_id": "legacy:startup-2",
            "startup_id": "startup-2",
            "opportunity_id": None,
            "canonical_name": "CloudNC",
            "decision": "invest",
            "rationale": "Portfolio Company",
            "decided_at": "2026-06-25T10:58:52Z",
            "recommended_state": None,
            "source": "legacy",
        },
        {
            "history_id": "partner:decision-1",
            "startup_id": "startup-3",
            "opportunity_id": None,
            "canonical_name": "Older Company",
            "decision": "pass",
            "rationale": "Aethria's partner decision.",
            "decided_at": "2026-06-17T08:23:21Z",
            "recommended_state": "pass",
            "source": "partner",
            "decision_kind": "partner",
        },
    ])
    repository = PortfolioRepository(_Pool(connection))

    rows = await repository.list_decision_history(user_id="user-a", limit=50)

    assert [row["canonical_name"] for row in rows] == ["Acme", "CloudNC", "Older Company"]
    assert rows[1]["decision"] == "invest"
    assert rows[1]["source"] == "legacy"
    assert rows[2]["decision_kind"] == "partner"
    sql, args = connection.calls[0][1], connection.calls[0][2]
    assert "public.human_rulings" in sql
    assert "public.startups" in sql
    assert "public.portfolio_decisions" in sql
    assert "o.legacy_startup_id" in sql
    assert args[0] == "user-a"
