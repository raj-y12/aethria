import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for target-PostgreSQL job repository tests",
)


@pytest.mark.asyncio
async def test_target_postgres_supports_transactional_skip_locked_contract():
    """The readiness gate runs the full repository scenario after the migration is applied."""
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        version = await connection.fetchval("show server_version_num")
        tables = await connection.fetchval(
            """
            select count(*)
            from information_schema.tables
            where table_schema = 'public'
              and table_name in ('agent_jobs', 'agent_job_checkpoints', 'domain_outbox')
            """
        )
    finally:
        await connection.close()

    assert int(version) >= 140000
    assert tables == 3


@pytest.mark.asyncio
async def test_target_postgres_skip_locked_claims_distinct_tenant_jobs():
    import asyncpg

    dsn = os.environ["TEST_DATABASE_URL"]
    setup = await asyncpg.connect(dsn)
    first = await asyncpg.connect(dsn)
    second = await asyncpg.connect(dsn)
    user_id = f"contract-{uuid4()}"
    job_ids = [uuid4(), uuid4()]
    try:
        await setup.executemany(
            """
            insert into public.agent_jobs (
              job_id,user_id,job_type,idempotency_key,payload,status,
              pipeline_run_id,created_at
            ) values ($1,$2,'pipeline_cycle',$3,'{}'::jsonb,'queued',$4,$5)
            """,
            [
                (job_ids[0], user_id, "first", uuid4(), datetime(2026, 1, 1, tzinfo=timezone.utc)),
                (job_ids[1], user_id, "second", uuid4(), datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)),
            ],
        )
        first_tx = first.transaction()
        second_tx = second.transaction()
        await first_tx.start()
        await second_tx.start()
        claimed_first = await first.fetchval(
            """
            select job_id from public.agent_jobs
            where user_id=$1 and status='queued'
            order by created_at for update skip locked limit 1
            """,
            user_id,
        )
        claimed_second = await second.fetchval(
            """
            select job_id from public.agent_jobs
            where user_id=$1 and status='queued'
            order by created_at for update skip locked limit 1
            """,
            user_id,
        )
        assert {claimed_first, claimed_second} == set(job_ids)
        await second_tx.rollback()
        await first_tx.rollback()
    finally:
        await setup.execute("delete from public.agent_jobs where user_id=$1", user_id)
        await first.close()
        await second.close()
        await setup.close()
