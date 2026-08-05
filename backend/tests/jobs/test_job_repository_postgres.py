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
async def test_target_postgres_security_limits_is_rls_protected_and_rpc_service_role_only():
    import asyncpg

    function_names = [
        "security_check_rate_limit",
        "security_acquire_lock",
        "security_release_lock",
    ]
    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        rls_enabled = await connection.fetchval(
            """
            select c.relrowsecurity
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relname = 'security_limits'
            """
        )
        policies = await connection.fetch(
            """
            select policyname, roles, cmd, qual, with_check
            from pg_policies
            where schemaname = 'public' and tablename = 'security_limits'
            order by policyname
            """
        )
        table_grants = await connection.fetch(
            """
            select grantee, privilege_type
            from information_schema.table_privileges
            where table_schema = 'public'
              and table_name = 'security_limits'
              and grantee in ('PUBLIC', 'anon', 'authenticated', 'service_role')
            order by grantee, privilege_type
            """
        )
        functions = await connection.fetch(
            """
            select
                p.proname,
                p.prosecdef,
                coalesce(p.proconfig, array[]::text[]) as proconfig,
                has_function_privilege('anon', p.oid, 'execute') as anon_execute,
                has_function_privilege(
                    'authenticated', p.oid, 'execute'
                ) as authenticated_execute,
                has_function_privilege(
                    'service_role', p.oid, 'execute'
                ) as service_role_execute
            from pg_proc p
            join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname = any($1::text[])
            order by p.proname
            """,
            function_names,
        )
        function_acl = await connection.fetch(
            """
            select
                p.proname,
                coalesce(r.rolname, 'PUBLIC') as grantee,
                a.privilege_type
            from pg_proc p
            join pg_namespace n on n.oid = p.pronamespace
            cross join lateral pg_catalog.aclexplode(
                coalesce(p.proacl, pg_catalog.acldefault('f', p.proowner))
            ) as a
            left join pg_roles r on r.oid = a.grantee
            where n.nspname = 'public'
              and p.proname = any($1::text[])
              and a.privilege_type = 'EXECUTE'
              and a.grantee <> p.proowner
            order by p.proname, grantee
            """,
            function_names,
        )
    finally:
        await connection.close()

    assert rls_enabled is True
    assert [dict(row) for row in policies] == [
        {
            "policyname": "security_limits_service_role_all",
            "roles": ["service_role"],
            "cmd": "ALL",
            "qual": "true",
            "with_check": "true",
        }
    ]
    assert {
        (row["grantee"], row["privilege_type"])
        for row in table_grants
    } == {
        ("service_role", privilege)
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
    }
    assert [row["proname"] for row in functions] == sorted(function_names)
    assert all(row["prosecdef"] for row in functions)
    assert all(
        any(
            setting.partition("=")[0] == "search_path"
            and setting.partition("=")[2].strip().strip("'\"") == ""
            for setting in row["proconfig"]
        )
        for row in functions
    )
    assert all(
        not row["anon_execute"]
        and not row["authenticated_execute"]
        and row["service_role_execute"]
        for row in functions
    )
    assert {
        (row["proname"], row["grantee"], row["privilege_type"])
        for row in function_acl
    } == {
        (function_name, "service_role", "EXECUTE")
        for function_name in function_names
    }


LEGACY_TENANT_TABLES = [
    "portfolio_budgets", "memory", "settings", "serp_usage",
    "analytics_sector_concentration", "meta_prompt_library", "meta_scout_weights",
    "meta_calibration_state", "meta_cycle_counters",
    "portfolio_decisions", "portfolio_positions", "portfolio_rejections",
    "portfolio_watchlist", "portfolio_signals", "portfolio_agent_metrics",
    "meta_mutation_log", "meta_reports",
    "meta_churn_signals", "pipeline_activity", "user_state",
]

PORTFOLIO_TABLES_PREVIOUSLY_MISSING = [
    "portfolio_startups", "portfolio_feed_cache", "portfolio_rejection_patterns",
]


async def _assert_tables_are_rls_protected_service_role_only(connection, tables):
    rows = await connection.fetch(
        """
        select c.relname as table_name, c.relrowsecurity
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relname = any($1::text[])
        """,
        tables,
    )
    policies = await connection.fetch(
        """
        select tablename, policyname, roles, cmd, qual, with_check
        from pg_policies
        where schemaname = 'public' and tablename = any($1::text[])
        order by tablename
        """,
        tables,
    )
    grants = await connection.fetch(
        """
        select table_name, grantee, privilege_type
        from information_schema.table_privileges
        where table_schema = 'public'
          and table_name = any($1::text[])
          and grantee in ('anon', 'authenticated', 'service_role')
        """,
        tables,
    )

    rls_by_table = {row["table_name"]: row["relrowsecurity"] for row in rows}
    assert set(rls_by_table) == set(tables), set(tables) - set(rls_by_table)
    assert all(rls_by_table.values()), rls_by_table

    policy_by_table = {row["tablename"]: dict(row) for row in policies}
    assert set(policy_by_table) == set(tables)
    for table, policy in policy_by_table.items():
        assert policy["roles"] == ["service_role"], (table, policy)
        assert policy["cmd"] == "ALL"
        assert policy["qual"] == "true"
        assert policy["with_check"] == "true"

    grants_by_table = {}
    for row in grants:
        grants_by_table.setdefault(row["table_name"], set()).add(
            (row["grantee"], row["privilege_type"])
        )
    for table in tables:
        assert grants_by_table.get(table) == {
            ("service_role", privilege)
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
        }, (table, grants_by_table.get(table))


@pytest.mark.asyncio
async def test_target_postgres_legacy_tenant_tables_are_rls_protected_service_role_only():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        await _assert_tables_are_rls_protected_service_role_only(
            connection, LEGACY_TENANT_TABLES
        )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_target_postgres_previously_missing_portfolio_tables_exist_and_are_rls_protected():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        await _assert_tables_are_rls_protected_service_role_only(
            connection, PORTFOLIO_TABLES_PREVIOUSLY_MISSING
        )
    finally:
        await connection.close()


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
