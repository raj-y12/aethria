import pytest

from memory_repository import MemoryRepository


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
async def test_get_returns_decoded_json_document_for_exact_tenant_and_key():
    connection = _Connection({"data": '{"nested": {"items": [1, true, null]}, "unicode": "€"}'})
    repository = MemoryRepository(_Pool(connection))

    result = await repository.get("user-a", key="default")

    assert result == {
        "nested": {"items": [1, True, None]},
        "unicode": "€",
    }
    kind, sql, args = connection.calls[0]
    assert kind == "fetchrow"
    assert "where user_id = $1 and key = $2" in sql.lower()
    assert args == ("user-a", "default")


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_document():
    repository = MemoryRepository(_Pool(_Connection()))

    assert await repository.get("missing-user", key="default") is None


@pytest.mark.asyncio
async def test_upsert_serializes_json_once_and_uses_tenant_key_conflict():
    connection = _Connection()
    repository = MemoryRepository(_Pool(connection))
    document = {
        "nested": {"items": [1, True, None]},
        "unicode": "€",
    }

    await repository.upsert("user-a", document, key="default")

    kind, sql, args = connection.calls[0]
    assert kind == "execute"
    assert "on conflict (user_id, key) do update" in sql.lower()
    assert args[0:2] == ("user-a", "default")
    assert args[2] == '{"nested": {"items": [1, true, null]}, "unicode": "\\u20ac"}'
