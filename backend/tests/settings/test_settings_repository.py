import json

import pytest

from settings_repository import SettingsRepository


class FakePool:
    def __init__(self):
        self.rows = {}
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        value = self.rows.get((args[0], args[1]))
        return None if value is None else {"data": value}

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        self.rows[(args[0], args[1])] = json.loads(args[2])

    async def fetch(self, sql):
        return [
            {"user_id": uid, "key": key, "data": data}
            for (uid, key), data in self.rows.items()
        ]


@pytest.mark.asyncio
async def test_settings_repository_missing_and_tenant_key_isolation():
    pool = FakePool()
    repository = SettingsRepository(pool)

    assert await repository.get("user-a", key="user-a") is None
    await repository.upsert(
        "user-a",
        {"nested": {"items": [1, True, None], "currency": "€"}},
        key="user-a",
    )

    assert await repository.get("user-a", key="user-a") == {
        "nested": {"items": [1, True, None], "currency": "€"}
    }
    assert await repository.get("user-b", key="user-a") is None
    assert await repository.get("user-a", key="other") is None
    assert any("$3::jsonb" in sql for sql, _args in pool.calls)


@pytest.mark.asyncio
async def test_settings_repository_upsert_replaces_document_and_lists_rows():
    pool = FakePool()
    repository = SettingsRepository(pool)

    await repository.upsert("user-a", {"old": True}, key="user-a")
    await repository.upsert("user-a", {"new": [1, 2, 3]}, key="user-a")

    assert await repository.get("user-a", key="user-a") == {"new": [1, 2, 3]}
    assert await repository.list_all() == [
        {"user_id": "user-a", "key": "user-a", "data": {"new": [1, 2, 3]}}
    ]


@pytest.mark.asyncio
async def test_settings_repository_propagates_persistence_failures():
    class FailingPool:
        async def fetchrow(self, *_args):
            raise RuntimeError("database unavailable")

        async def execute(self, *_args):
            raise RuntimeError("database unavailable")

    repository = SettingsRepository(FailingPool())
    with pytest.raises(RuntimeError, match="database unavailable"):
        await repository.get("user-a")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await repository.upsert("user-a", {})
