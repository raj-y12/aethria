import asyncio
import os
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
async def test_target_postgres_lookup_outcomes_is_service_role_only():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        rls_enabled = await connection.fetchval(
            """
            select c.relrowsecurity
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relname = 'lookup_job_outcomes'
            """
        )
        policies = await connection.fetch(
            """
            select policyname, roles, cmd, qual, with_check
            from pg_policies
            where schemaname = 'public' and tablename = 'lookup_job_outcomes'
            """
        )
        grants = await connection.fetch(
            """
            select grantee, privilege_type
            from information_schema.table_privileges
            where table_schema = 'public'
              and table_name = 'lookup_job_outcomes'
              and grantee in ('anon', 'authenticated', 'service_role')
            """
        )
    finally:
        await connection.close()

    check = __import__(
        "scripts.check_phase8_readiness", fromlist=["check"]
    )._lookup_outcomes_security_check(
        table_rows=[
            {
                "table_name": "lookup_job_outcomes",
                "relrowsecurity": bool(rls_enabled),
            }
        ],
        policy_rows=[dict(row) for row in policies],
        grant_rows=[dict(row) for row in grants],
    )
    assert check["status"] == "passed", check


@pytest.mark.asyncio
async def test_target_postgres_skip_locked_claims_distinct_tenant_jobs():
    import asyncpg
    from jobs.models import AgentJob, JobType
    from jobs.repository import DurableJobRepository

    dsn = os.environ["TEST_DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    repository = DurableJobRepository(pool)
    user_id = f"contract-{uuid4()}"
    jobs = [
        AgentJob(
            user_id=user_id,
            job_type=JobType.PIPELINE_CYCLE,
            idempotency_key=f"contract:{index}:{uuid4()}",
            payload={"user_id": user_id, "manual_one_shot": True},
        )
        for index in range(2)
    ]
    try:
        accepted = await asyncio.gather(
            *(repository.enqueue(job) for job in jobs)
        )
        claimed = await asyncio.gather(
            repository.claim_next(worker_id="worker-1", lease_seconds=60),
            repository.claim_next(worker_id="worker-2", lease_seconds=60),
        )
        assert {job.job_id for job in accepted} == {job.job_id for job in jobs}
        assert {job.job_id for job in claimed if job is not None} == {
            job.job_id for job in jobs
        }
        tenant_depths = await repository.tenant_queue_depths(user_id=user_id)
        assert tenant_depths["pipeline_cycle:running"] == 2
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.domain_outbox where user_id=$1", user_id
            )
            await connection.execute(
                "delete from public.agent_jobs where user_id=$1", user_id
            )
    finally:
        await pool.close()
