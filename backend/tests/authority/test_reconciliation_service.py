import pytest

from authority.reconciliation import check_tenant_reconciliation


class _Conn:
    def __init__(self, row):
        self.row = row
        self.queries = []

    async def fetchval(self, query, user_id):
        self.queries.append((query, user_id))
        return self.row


@pytest.mark.asyncio
async def test_reconciler_returns_green_when_all_linked_opportunities_have_legacy_rows():
    result = await check_tenant_reconciliation(_Conn(0), "tenant-1")
    assert result.status == "green"
    assert result.missing_legacy_projections == 0


@pytest.mark.asyncio
async def test_reconciler_returns_red_when_a_linked_opportunity_is_not_projected():
    result = await check_tenant_reconciliation(_Conn(2), "tenant-1")
    assert result.status == "red"
    assert result.missing_legacy_projections == 2


@pytest.mark.asyncio
async def test_reconciler_casts_canonical_legacy_link_to_text_for_startups_join():
    conn = _Conn(0)

    await check_tenant_reconciliation(conn, "tenant-1")

    query = " ".join(conn.queries[0][0].split()).lower()
    assert "s.startup_id=o.legacy_startup_id::text" in query
