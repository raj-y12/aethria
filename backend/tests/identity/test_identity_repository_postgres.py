import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for canonical identity transaction tests",
)


@pytest.mark.asyncio
async def test_target_postgres_has_phase2_identity_schema():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        tables = await connection.fetchval(
            """
            select count(*) from information_schema.tables
            where table_schema = 'public'
              and table_name = any($1::text[])
            """,
            [
                "companies",
                "source_observations",
                "company_identifiers",
                "company_aliases",
                "opportunities",
                "identity_resolution_cases",
            ],
        )
    finally:
        await connection.close()

    assert tables == 6
