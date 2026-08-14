import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from user_state.repository import UserStateRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for user_state PostgreSQL contract tests",
)


@pytest.mark.asyncio
async def test_user_state_round_trip_update_and_tenant_isolation():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    first_user = f"user-state-{uuid4()}"
    second_user = f"user-state-{uuid4()}"
    first_seen = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    second_seen = datetime(2026, 8, 11, 13, 0, tzinfo=timezone.utc)
    repository = UserStateRepository(pool)
    try:
        assert await repository.get_last_seen_at(first_user) is None
        await repository.upsert_last_seen_at(first_user, first_seen)
        await repository.upsert_last_seen_at(first_user, second_seen)
        await repository.upsert_last_seen_at(second_user, first_seen)

        assert await repository.get_last_seen_at(first_user) == second_seen
        assert await repository.get_last_seen_at(second_user) == first_seen
        assert await repository.get_last_seen_at(f"missing-{uuid4()}") is None
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.user_state where user_id = any($1::text[])",
                [first_user, second_user],
            )
        await pool.close()
