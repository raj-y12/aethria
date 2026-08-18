import asyncio
import gc

import pytest

import pipeline_concurrency


@pytest.mark.asyncio
async def test_user_lock_serializes_two_concurrent_slots_for_the_same_user():
    order = []

    async def worker(n):
        async with pipeline_concurrency.pipeline_execution_slot("user-1"):
            order.append(f"start-{n}")
            await asyncio.sleep(0)
            order.append(f"end-{n}")

    await asyncio.gather(worker(1), worker(2))

    assert order == ["start-1", "end-1", "start-2", "end-2"]


@pytest.mark.asyncio
async def test_user_lock_is_evicted_once_no_one_holds_or_awaits_it():
    """Regression (audit LOW): _user_locks was a plain dict that grew one
    entry per distinct user_id ever seen, for the life of the process."""
    async with pipeline_concurrency.pipeline_execution_slot("user-evict-me"):
        pass

    gc.collect()
    assert "user-evict-me" not in pipeline_concurrency._user_locks
