from datetime import datetime, timezone

import pytest

from user_state.repository import UserStateRepository


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_exc):
        return False


class _Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.row

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_get_last_seen_at_returns_only_the_requested_tenant_value():
    seen = datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc)
    connection = _Connection({"last_seen_at": seen})
    repository = UserStateRepository(_Pool(connection))

    result = await repository.get_last_seen_at("user-a")

    assert result == seen
    kind, sql, args = connection.calls[0]
    assert kind == "fetchrow"
    assert "where user_id = $1" in sql.lower()
    assert args == ("user-a",)


@pytest.mark.asyncio
async def test_get_last_seen_at_returns_none_for_missing_user():
    repository = UserStateRepository(_Pool(_Connection()))

    assert await repository.get_last_seen_at("missing-user") is None


@pytest.mark.asyncio
async def test_upsert_last_seen_at_uses_user_id_conflict_key_and_timestamp_parameter():
    seen = datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc)
    connection = _Connection()
    repository = UserStateRepository(_Pool(connection))

    await repository.upsert_last_seen_at("user-a", seen)

    kind, sql, args = connection.calls[0]
    assert kind == "execute"
    assert "on conflict (user_id) do update" in sql.lower()
    assert args == ("user-a", seen)
