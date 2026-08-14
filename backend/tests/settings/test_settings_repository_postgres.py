import os

import pytest

from settings_repository import SettingsRepository


@pytest.mark.asyncio
async def test_settings_repository_postgres_round_trip_and_isolation():
    dsn = os.getenv("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")

    asyncpg = pytest.importorskip("asyncpg")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    repository = SettingsRepository(pool)
    await pool.execute(
        """
        create table if not exists public.settings (
            user_id text not null,
            key text not null,
            data jsonb not null default '{}'::jsonb,
            primary key (user_id, key)
        )
        """
    )
    try:
        await repository.upsert(
            "settings-test-a",
            {"nested": {"items": [1, True, None], "currency": "€"}},
            key="settings-test-a",
        )
        assert await repository.get("settings-test-a", key="settings-test-a") == {
            "nested": {"items": [1, True, None], "currency": "€"}
        }
        assert await repository.get("settings-test-b", key="settings-test-a") is None
    finally:
        await pool.execute(
            "delete from public.settings where user_id in ('settings-test-a', 'settings-test-b')"
        )
        await pool.close()
