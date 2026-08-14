import os
from uuid import uuid4

import pytest

from memory_repository import MemoryRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for memory PostgreSQL contract tests",
)


@pytest.mark.asyncio
async def test_memory_jsonb_round_trip_and_tenant_key_isolation():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    first_user = f"memory-{uuid4()}"
    second_user = f"memory-{uuid4()}"
    document = {
        "nested": {"items": [1, True, None]},
        "number": 3.5,
        "unicode": "€",
    }
    repository = MemoryRepository(pool)
    try:
        assert await repository.get(first_user) is None
        await repository.upsert(first_user, document)
        await repository.upsert(second_user, {"owner": "second"}, key="other")

        assert await repository.get(first_user) == document
        assert await repository.get(first_user, key="other") is None
        assert await repository.get(second_user, key="other") == {"owner": "second"}
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.memory where user_id = any($1::text[])",
                [first_user, second_user],
            )
        await pool.close()
