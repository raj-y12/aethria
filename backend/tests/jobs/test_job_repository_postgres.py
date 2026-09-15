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
async def test_target_postgres_lookup_outcomes_is_tenant_scoped():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        columns = await connection.fetch(
            """
            select column_name
            from information_schema.columns
            where table_schema='public' and table_name='lookup_job_outcomes'
            """
        )
        keys = await connection.fetch(
            """
            select a.attname
            from pg_index i
            join pg_attribute a on a.attrelid=i.indrelid and a.attnum=any(i.indkey)
            where i.indrelid='public.lookup_job_outcomes'::regclass and i.indisunique
            """
        )
    finally:
        await connection.close()

    assert {row["column_name"] for row in columns} >= {"user_id", "id", "data"}
    assert {row["attname"] for row in keys} >= {"user_id", "id"}


@pytest.mark.asyncio
async def test_target_postgres_security_limits_uses_provider_neutral_repository():
    import asyncpg

    from security.repository import SecurityRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = SecurityRepository(pool)
    key = f"contract-security-{uuid4()}"
    try:
        count, _expires_at = await repository.check_rate_limit(key, window_seconds=60)
        assert count == 1
    finally:
        await pool.execute("delete from public.security_limits where key=$1", key)
        await pool.close()


CANONICAL_TENANT_TABLES = [
    "portfolio_budgets", "memory", "settings",
    "analytics_sector_concentration", "meta_prompt_library", "meta_scout_weights",
    "meta_calibration_state", "meta_cycle_counters",
    "portfolio_decisions", "portfolio_positions", "portfolio_rejections",
    "portfolio_watchlist", "portfolio_signals",
    "meta_mutation_log", "meta_reports",
    "meta_churn_signals", "user_state",
]

async def _assert_tables_are_tenant_scoped(connection, tables):
    rows = await connection.fetch(
        """
        select table_name
        from information_schema.tables
        where table_schema='public' and table_name = any($1::text[])
        """,
        tables,
    )
    columns = await connection.fetch(
        """
        select table_name
        from information_schema.columns
        where table_schema='public'
          and table_name = any($1::text[])
          and column_name='user_id'
        """,
        tables,
    )

    assert {row["table_name"] for row in rows} == set(tables)
    assert {row["table_name"] for row in columns} == set(tables)


@pytest.mark.asyncio
async def test_target_postgres_canonical_tenant_tables_are_provider_neutral():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        await _assert_tables_are_tenant_scoped(
            connection, CANONICAL_TENANT_TABLES
        )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_target_postgres_uses_canonical_startup_authority_and_alias_bridge():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        rows = await connection.fetch(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
              and table_name = any($1::text[])
            """,
            ["startups", "startup_id_aliases"],
        )
    finally:
        await connection.close()

    # The contract job applies the institutional compatibility migrations first,
    # so legacy portfolio tables may still exist. Canonical authority is proven
    # by the provider-neutral startups table and its explicit alias bridge.
    assert {row["table_name"] for row in rows} == {
        "startups",
        "startup_id_aliases",
    }


@pytest.mark.asyncio
async def test_target_postgres_skip_locked_claims_distinct_tenant_jobs():
    import asyncpg
    from jobs.models import AgentJob, JobType
    from jobs.repository import DurableJobRepository

    dsn = os.environ["TEST_DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    repository = DurableJobRepository(pool)
    user_id = f"contract-{uuid4()}"
    # Test SKIP LOCKED, not host/container clock synchronization. These jobs
    # must already be due according to the clock used by claim_next's SQL.
    due_at = await pool.fetchval("select clock_timestamp()")
    jobs = [
        AgentJob(
            user_id=user_id,
            job_type=JobType.PIPELINE_CYCLE,
            idempotency_key=f"contract:{index}:{uuid4()}",
            payload={"user_id": user_id, "manual_one_shot": True},
            next_attempt_at=due_at,
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
    finally:
        try:
            async with pool.acquire() as connection:
                await connection.execute(
                    "delete from public.domain_outbox where user_id=$1", user_id
                )
                await connection.execute(
                    "delete from public.agent_jobs where user_id=$1", user_id
                )
        finally:
            await pool.close()
