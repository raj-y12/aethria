import pytest

from authority.reconciliation import AuthorityReconciler


class _Conn:
    def __init__(self, row):
        self.row = row

    async def fetchval(self, query, user_id):
        return self.row


class _Acquire:
    def __init__(self, row):
        self.row = row

    async def __aenter__(self):
        return _Conn(self.row)

    async def __aexit__(self, *_):
        return None


class _Pool:
    def __init__(self, row):
        self.row = row

    def acquire(self):
        return _Acquire(self.row)


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
