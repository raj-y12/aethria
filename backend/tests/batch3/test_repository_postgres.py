import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for Batch 3 PostgreSQL contracts",
)


@pytest.mark.asyncio
async def test_batch3_collections_are_tenant_scoped_ordered_and_json_round_trip():
    import asyncpg

    from batch3.repository import Batch3Repository, TABLES

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = Batch3Repository(pool)
    user_a = f"batch3-a-{uuid4()}"
    user_b = f"batch3-b-{uuid4()}"
    try:
        state = await repository.load_state(user_a)
        state.upsert("portfolio_decisions", {"id": "d-1", "startup_id": "s-1", "decision": "YES", "nested": {"ok": True}})
        state.upsert("portfolio_signals", {"id": "sig-1", "startup_id": "s-1", "signal_type": "positive"})
        state.upsert("portfolio_watchlist", {"id": "w-1", "startup_id": "s-1", "version": 4})
        await repository.persist_state(state)

        other = await repository.load_state(user_b)
        assert all(other.get_all(table) == [] for table in TABLES)
        loaded = await repository.load_state(user_a)
        assert loaded.get_all("portfolio_decisions")[0]["nested"] == {"ok": True}
        assert loaded.get_all("portfolio_signals")[0]["id"] == "sig-1"
        assert loaded.get_all("portfolio_watchlist")[0]["version"] == 4
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.portfolio_decisions where user_id=$1", user_a
            ) == 1
            assert await connection.fetchval(
                "select created_at is not null from public.portfolio_decisions where user_id=$1", user_a
            ) is True
    finally:
        async with pool.acquire() as connection:
            for table in TABLES:
                await connection.execute(f"delete from public.{table} where user_id=$1", user_a)
        await pool.close()


@pytest.mark.asyncio
async def test_batch3_duplicate_id_updates_same_tenant_and_not_another():
    import asyncpg

    from batch3.repository import Batch3Repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = Batch3Repository(pool)
    user_a = f"batch3-upsert-a-{uuid4()}"
    user_b = f"batch3-upsert-b-{uuid4()}"
    try:
        state = await repository.load_state(user_a)
        state.upsert("portfolio_rejections", {"id": "r-1", "reason": "LOW_SCORE", "version": 1})
        await repository.persist_state(state)
        state = await repository.load_state(user_a)
        state.upsert("portfolio_rejections", {"id": "r-1", "reason": "NEW_REASON"})
        await repository.persist_state(state)

        loaded = await repository.load_state(user_a)
        assert loaded.get_all("portfolio_rejections") == [{"id": "r-1", "reason": "NEW_REASON", "version": 2}]
        assert (await repository.load_state(user_b)).get_all("portfolio_rejections") == []
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.portfolio_rejections where user_id=$1", user_a)
        await pool.close()
