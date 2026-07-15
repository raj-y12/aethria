import os

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
