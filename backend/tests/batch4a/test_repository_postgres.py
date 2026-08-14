import os
from uuid import uuid4

import pytest

from batch4a.repository import Batch4ARepository, Batch4AState


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for Batch 4A PostgreSQL contracts",
)


@pytest.mark.asyncio
async def test_batch4a_operational_history_contracts():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"batch4a-{uuid4()}"
    other_user_id = f"batch4a-other-{uuid4()}"
    startup_id = f"startup-{uuid4()}"
    run_id = uuid4()
    try:
        repository = Batch4ARepository(pool)
        state = await repository.load_state(user_id)
        assert state.pipeline_states == {}

        await pool.execute(
            """insert into public.startups
               (user_id,startup_id,scout_info,financials)
               values ($1,$2,'{}'::jsonb,'{}'::jsonb)""",
            user_id,
            startup_id,
        )

        state.upsert_pipeline_state({
            "user_id": user_id,
            "startup_id": startup_id,
            "pipeline_run_id": str(run_id),
            "status": "scouting",
            "updated_at": "2026-08-11T12:00:00Z",
            "error": None,
        })
        state.append_scoring_trail({
            "user_id": user_id,
            "startup_id": startup_id,
            "rubric_version": "r1",
            "policy_version_id": "p1",
            "policy_hash": "hash",
            "overall_score": 7.5,
            "overall_confidence": 0.8,
            "stage_cohort": "seed",
            "sector_tam_benchmark": "large",
            "trail": {"market": {"score": 7.5}},
        })
        state.append_activity({
            "user_id": user_id,
            "startups_found": 2,
            "reviewed_count": 3,
            "decisions_made": 1,
            "escalations_count": 1,
        })
        await repository.persist_state(state)

        loaded = await repository.load_state(user_id)
        assert loaded.pipeline_states[startup_id]["status"] == "scouting"
        assert loaded.scoring_trails[0]["trail"] == {"market": {"score": 7.5}}
        assert loaded.pipeline_activity[0]["decisions_made"] == 1

        loaded.upsert_pipeline_state({
            "user_id": user_id,
            "startup_id": startup_id,
            "pipeline_run_id": str(run_id),
            "status": "ready",
            "updated_at": "2026-08-11T12:01:00Z",
            "error": None,
        })
        await repository.persist_state(loaded)
        assert (await repository.get_pipeline_state(user_id, startup_id))["status"] == "ready"

        assert await repository.get_pipeline_state(other_user_id, startup_id) is None
        assert len(await repository.list_pipeline_activity_since(user_id)) == 1
        assert len(await repository.list_all_pipeline_activity()) >= 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_pipeline_state where user_id=$1", user_id)
            await connection.execute("delete from public.scoring_trails where user_id=$1", user_id)
            await connection.execute("delete from public.pipeline_activity where user_id=$1", user_id)
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


def test_batch4a_state_is_tenant_explicit_and_append_only():
    state = Batch4AState("user-1")
    state.append_scoring_trail({"startup_id": "s1", "trail": {"x": 1}})
    state.append_scoring_trail({"startup_id": "s1", "trail": {"x": 2}})
    assert len(state.appended_scoring_trails) == 2
    assert state.user_id == "user-1"
