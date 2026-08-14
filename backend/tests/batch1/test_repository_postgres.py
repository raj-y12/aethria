import asyncio
import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for Batch 1 PostgreSQL contracts",
)


@pytest.mark.asyncio
async def test_batch1_documents_and_lists_are_tenant_scoped_and_ordered():
    import asyncpg

    from batch1.repository import Batch1Repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = Batch1Repository(pool)
    user_a = f"batch1-a-{uuid4()}"
    user_b = f"batch1-b-{uuid4()}"
    try:
        state_a = await repository.load_state(user_a)
        state_a.set_document("meta_prompt_library", {"unicode": "€", "enabled": True}, "prompt_active")
        state_a.append_list("meta_reports", {"cycle_number": 2, "nested": {"ok": None}})
        await repository.persist_state(state_a)

        state_b = await repository.load_state(user_b)
        assert state_b.get_document("meta_prompt_library", "prompt_active") is None
        assert state_b.get_list("meta_reports") == []

        loaded = await repository.load_state(user_a)
        assert loaded.get_document("meta_prompt_library", "prompt_active") == {
            "unicode": "€", "enabled": True
        }
        reports = loaded.get_list("meta_reports")
        assert len(reports) == 1
        assert reports[0]["nested"] == {"ok": None}
        assert reports[0]["id"]
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select created_at is not null from public.meta_reports where user_id=$1",
                user_a,
            ) is True
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.meta_reports where user_id=$1", user_a)
            await connection.execute("delete from public.meta_prompt_library where user_id=$1", user_a)
        await pool.close()


@pytest.mark.asyncio
async def test_batch1_cycle_counter_is_atomic():
    import asyncpg

    from batch1.repository import Batch1Repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=5)
    repository = Batch1Repository(pool)
    user_id = f"batch1-counter-{uuid4()}"
    try:
        values = await asyncio.gather(*(
            repository.increment_cycle_counter(user_id) for _ in range(8)
        ))
        assert sorted(values) == list(range(1, 9))
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.meta_cycle_counters where user_id=$1", user_id
            )
        await pool.close()
