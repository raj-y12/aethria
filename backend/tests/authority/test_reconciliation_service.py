import pytest

from authority.reconciliation import AuthorityReconciler


class _Conn:
    def __init__(self, row):
        self.row = row
        self.queries = []

    async def fetchval(self, query, user_id):
        self.queries.append((query, user_id))
        return self.row


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class _Pool:
    def __init__(self, row):
        self.row = row
        self.connection = None

    def acquire(self):
        self.connection = _Conn(self.row)
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_reconciler_returns_green_when_all_linked_opportunities_have_legacy_rows():
    result = await AuthorityReconciler(_Pool(0)).check_tenant("tenant-1")
    assert result.status == "green"
    assert result.missing_legacy_projections == 0


@pytest.mark.asyncio
async def test_reconciler_returns_red_when_a_linked_opportunity_is_not_projected():
    result = await AuthorityReconciler(_Pool(2)).check_tenant("tenant-1")
    assert result.status == "red"
    assert result.missing_legacy_projections == 2


@pytest.mark.asyncio
async def test_reconciler_casts_canonical_legacy_link_to_text_for_startups_join():
    pool = _Pool(0)

    await AuthorityReconciler(pool).check_tenant("tenant-1")

    query = " ".join(pool.connection.queries[0][0].split()).lower()
    assert "s.startup_id=o.legacy_startup_id::text" in query
