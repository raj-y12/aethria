import os
from uuid import uuid4

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


@pytest.mark.asyncio
async def test_old_observation_replay_keeps_its_opportunity_after_a_newer_source():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    transaction = connection.transaction()
    await transaction.start()
    user_id = f"identity-contract-{uuid4()}"
    company_id = uuid4()
    old_observation = uuid4()
    newer_observation = uuid4()
    opportunity_id = uuid4()
    try:
        await connection.execute(
            """
            insert into public.companies (
              company_id,user_id,canonical_name,canonical_domain,identity_confidence
            ) values ($1,$2,'Replay Co',$3,1)
            """,
            company_id,
            user_id,
            f"{company_id}.example",
        )
        for observation_id, event_key in (
            (old_observation, "old"),
            (newer_observation, "new"),
        ):
            await connection.execute(
                """
                insert into public.source_observations (
                  observation_id,user_id,channel,external_event_key,observed_name,
                  company_id,identity_status,identity_confidence
                ) values ($1,$2,'autonomous_discovery',$3,'Replay Co',$4,'resolved',1)
                """,
                observation_id,
                user_id,
                event_key,
                company_id,
            )
        await connection.execute(
            """
            insert into public.opportunities (
              opportunity_id,user_id,company_id,context_key,
              first_observation_id,latest_observation_id
            ) values ($1,$2,$3,'primary',$4,$5)
            """,
            opportunity_id,
            user_id,
            company_id,
            old_observation,
            newer_observation,
        )
        await connection.execute(
            """
            update public.source_observations set opportunity_id=$3
            where user_id=$1 and observation_id=$2
            """,
            user_id,
            old_observation,
            opportunity_id,
        )
        replayed = await connection.fetchval(
            """
            select p.opportunity_id from public.source_observations o
            join public.opportunities p
              on p.user_id=o.user_id and p.opportunity_id=o.opportunity_id
            where o.user_id=$1 and o.observation_id=$2
            """,
            user_id,
            old_observation,
        )
        assert replayed == opportunity_id
    finally:
        await transaction.rollback()
        await connection.close()
