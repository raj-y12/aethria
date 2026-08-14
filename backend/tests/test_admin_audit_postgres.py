import pytest

from admin_audit import record_admin_audit_event


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_exc):
        return False


class _Pool:
    def __init__(self):
        self.calls = []

    def acquire(self):
        return _Acquire(self)

    async def execute(self, sql, *args):
        self.calls.append((sql, args))


@pytest.mark.asyncio
async def test_admin_audit_writes_jsonb_event_through_shared_async_pool():
    pool = _Pool()

    await record_admin_audit_event(
        pool=pool,
        event="admin_login",
        success=False,
        client_host="127.0.0.1",
        detail={"reason": "invalid_secret"},
    )

    assert len(pool.calls) == 1
    sql, args = pool.calls[0]
    assert "insert into public.admin_audit_log" in sql.lower()
    assert args == (
        "admin_login",
        False,
        "127.0.0.1",
        '{"reason": "invalid_secret"}',
    )


@pytest.mark.asyncio
async def test_admin_audit_does_not_raise_when_database_write_fails(caplog):
    class FailingPool(_Pool):
        async def execute(self, sql, *args):
            raise RuntimeError("database unavailable")

    await record_admin_audit_event(
        pool=FailingPool(),
        event="admin_overview",
        success=True,
    )

    assert "Unable to write admin audit event admin_overview" in caplog.text
