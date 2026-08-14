import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for Batch 2 PostgreSQL contracts",
)


@pytest.mark.asyncio
async def test_batch2_cache_rejection_and_metrics_are_tenant_scoped():
    import asyncpg

    from batch2.repository import Batch2Repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = Batch2Repository(pool)
    user_a = f"batch2-a-{uuid4()}"
    user_b = f"batch2-b-{uuid4()}"
    try:
        state_a = await repository.load_state(user_a)
        state_a.set_feed_cache({"id": str(uuid4()), "cached_at": 123.5, "items": [{"title": "€"}]})
        state_a.set_rejection_patterns({"id": str(uuid4()), "stats": {"_rejection_count": 2}})
        state_a.append_metric({"id": "metric-1", "metric_name": "acceptance_rate", "sample_size": 3})
        await repository.persist_state(state_a)

        state_b = await repository.load_state(user_b)
        assert state_b.get_feed_cache() is None
        assert state_b.get_rejection_patterns() is None
        assert state_b.get_metrics() == []

        loaded = await repository.load_state(user_a)
        assert loaded.get_feed_cache()["items"] == [{"title": "€"}]
        assert loaded.get_rejection_patterns()["stats"] == {"_rejection_count": 2}
        assert loaded.get_metrics()[0]["metric_name"] == "acceptance_rate"
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.portfolio_agent_metrics where user_id=$1",
                user_a,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            for table in (
                "portfolio_feed_cache",
                "portfolio_rejection_patterns",
                "portfolio_agent_metrics",
            ):
                await connection.execute(f"delete from public.{table} where user_id=$1", user_a)
        await pool.close()


@pytest.mark.asyncio
async def test_batch2_current_rows_update_and_metrics_append():
    import asyncpg

    from batch2.repository import Batch2Repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = Batch2Repository(pool)
    user_id = f"batch2-update-{uuid4()}"
    try:
        state = await repository.load_state(user_id)
        state.set_feed_cache({"id": str(uuid4()), "cached_at": 1, "items": []})
        state.set_rejection_patterns({"id": str(uuid4()), "stats": {"n": 1}})
        state.append_metric({"id": "metric-a", "metric_name": "one"})
        await repository.persist_state(state)

        state = await repository.load_state(user_id)
        cache_id = state.get_feed_cache()["id"]
        rejection_id = state.get_rejection_patterns()["id"]
        state.set_feed_cache({"id": cache_id, "cached_at": 2, "items": [{"fresh": True}]})
        state.set_rejection_patterns({"id": rejection_id, "stats": {"n": 2}})
        state.append_metric({"id": "metric-b", "metric_name": "two"})
        await repository.persist_state(state)

        loaded = await repository.load_state(user_id)
        assert loaded.get_feed_cache()["cached_at"] == 2
        assert loaded.get_rejection_patterns()["stats"] == {"n": 2}
        assert [m["id"] for m in loaded.get_metrics()] == ["metric-a", "metric-b"]
    finally:
        async with pool.acquire() as connection:
            for table in (
                "portfolio_feed_cache",
                "portfolio_rejection_patterns",
                "portfolio_agent_metrics",
            ):
                await connection.execute(f"delete from public.{table} where user_id=$1", user_id)
        await pool.close()
