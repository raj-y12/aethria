import asyncio
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
    from identity.models import SourceChannel, SourceObservationInput
    from identity.repository import IdentityRepository
    from identity.service import IdentityService

    pool = await asyncpg.create_pool(
        os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4
    )
    repository = IdentityRepository(pool)
    service = IdentityService(repository)
    user_id = f"identity-contract-{uuid4()}"
    domain = f"replay-{uuid4()}.example"

    def observation(label: str) -> SourceObservationInput:
        return SourceObservationInput(
            user_id=user_id,
            channel=SourceChannel.MANUAL_LOOKUP,
            observed_name="Replay Co",
            observed_domain=domain,
            external_event_key=f"{label}:{uuid4()}",
            source_metadata={"operator_confirmed_identity": True},
            resolution_payload={
                "website": domain,
                "confidence": 1,
                "resolution_status": "FOUND",
            },
        )

    try:
        first, second = await asyncio.gather(
            service.admit(observation("first")),
            service.admit(observation("second")),
        )
        assert first.company_id == second.company_id
        assert first.opportunity_id == second.opportunity_id

        replayed = await repository.get_admission_for_observation(
            user_id=user_id, observation_id=first.observation_id
        )
        assert replayed is not None
        assert replayed.opportunity_id == first.opportunity_id
        assert replayed.blocks_evaluation is False
        assert await repository.get_company(
            user_id=f"other-{uuid4()}", company_id=first.company_id
        ) is None
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.domain_outbox where user_id=$1", user_id
            )
            await connection.execute(
                "delete from public.identity_resolution_cases where user_id=$1",
                user_id,
            )
            await connection.execute(
                "delete from public.company_aliases where user_id=$1", user_id
            )
            await connection.execute(
                "delete from public.company_identifiers where user_id=$1", user_id
            )
            await connection.execute(
                "update public.source_observations set opportunity_id=null where user_id=$1",
                user_id,
            )
            await connection.execute(
                "delete from public.opportunities where user_id=$1", user_id
            )
            await connection.execute(
                "delete from public.source_observations where user_id=$1", user_id
            )
            await connection.execute(
                "delete from public.companies where user_id=$1", user_id
            )
        await pool.close()
