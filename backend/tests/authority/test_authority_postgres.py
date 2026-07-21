import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for authority transaction tests",
)


@pytest.mark.asyncio
async def test_target_postgres_rollout_and_workflow_transactions_are_tenant_safe():
    import asyncpg

    from authority.models import RolloutMode, WorkflowState
    from authority.repository import AuthorityConflict, AuthorityRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = AuthorityRepository(pool)
    user_id = f"authority-contract-{uuid4()}"
    opportunity_id = uuid4()
    company_id = uuid4()
    observation_id = uuid4()
    try:
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                """
                select relrowsecurity
                from pg_class where oid='public.tenant_authority_rollouts'::regclass
                """
            ) is True
            await connection.execute(
                """
                insert into public.companies (
                  company_id,user_id,canonical_name,identity_confidence,status,metadata,
                  created_at,updated_at
                ) values ($1,$2,'Authority Contract Co',1,'active','{}'::jsonb,now(),now())
                """,
                company_id,
                user_id,
            )
            await connection.execute(
                """
                insert into public.source_observations (
                  observation_id,user_id,channel,observed_name,company_id,identity_status,
                  identity_confidence,observed_at,created_at,updated_at
                ) values ($1,$2,'manual_lookup','Authority Contract Co',$3,'resolved',1,now(),now(),now())
                """,
                observation_id,
                user_id,
                company_id,
            )
            await connection.execute(
                """
                insert into public.opportunities (
                  opportunity_id,user_id,company_id,context_key,decision_state,
                  service_level,first_observation_id,latest_observation_id,
                  workflow_state,workflow_version,created_at,updated_at
                ) values ($1,$2,$3,'authority-test','discovered',1,$4,$4,'admitted',0,now(),now())
                """,
                opportunity_id,
                user_id,
                company_id,
                observation_id,
            )
        initial = await repository.get_rollout(user_id=user_id)
        assert initial.mode is RolloutMode.LEGACY
        shadow = await repository.transition_rollout(
            user_id=user_id,
            expected_version=initial.version,
            target_mode=RolloutMode.SHADOW,
            actor_id="contract-test",
            snapshot_id=None,
        )
        with pytest.raises(AuthorityConflict):
            await repository.transition_rollout(
                user_id=user_id,
                expected_version=initial.version,
                target_mode=RolloutMode.BACKFILL,
                actor_id="contract-test",
                snapshot_id=None,
            )

        changed = await repository.transition_workflow(
            user_id=user_id,
            opportunity_id=opportunity_id,
            expected_version=0,
            target_state=WorkflowState.TRIAGE_PENDING,
            transition_id=uuid4(),
        )
        assert changed.version == 1
        with pytest.raises(AuthorityConflict):
            await repository.transition_workflow(
                user_id=user_id,
                opportunity_id=opportunity_id,
                expected_version=0,
                target_state=WorkflowState.EVIDENCE_ACTIVE,
                transition_id=uuid4(),
            )
        assert shadow.user_id == user_id
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.domain_outbox where user_id=$1", user_id)
            await connection.execute("delete from public.opportunities where user_id=$1", user_id)
            await connection.execute("delete from public.source_observations where user_id=$1", user_id)
            await connection.execute("delete from public.companies where user_id=$1", user_id)
            await connection.execute(
                "delete from public.tenant_authority_rollouts where user_id=$1", user_id
            )
        await pool.close()


@pytest.mark.asyncio
async def test_target_postgres_rolls_back_workflow_on_outbox_error_and_receipts_are_unique():
    import asyncpg

    from authority.models import WorkflowState
    from authority.repository import AuthorityRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = AuthorityRepository(pool)
    user_id = f"authority-atomic-{uuid4()}"
    company_id = uuid4()
    observation_id = uuid4()
    opportunity_id = uuid4()
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into public.companies (
                  company_id,user_id,canonical_name,identity_confidence,status,metadata,
                  created_at,updated_at
                ) values ($1,$2,'Authority Atomic Co',1,'active','{}'::jsonb,now(),now())
                """,
                company_id,
                user_id,
            )
            await connection.execute(
                """
                insert into public.source_observations (
                  observation_id,user_id,channel,observed_name,company_id,identity_status,
                  identity_confidence,observed_at,created_at,updated_at
                ) values ($1,$2,'manual_lookup','Authority Atomic Co',$3,'resolved',1,now(),now(),now())
                """,
                observation_id,
                user_id,
                company_id,
            )
            await connection.execute(
                """
                insert into public.opportunities (
                  opportunity_id,user_id,company_id,context_key,decision_state,
                  service_level,first_observation_id,latest_observation_id,
                  workflow_state,workflow_version,created_at,updated_at
                ) values ($1,$2,$3,'authority-atomic','discovered',1,$4,$4,'admitted',0,now(),now())
                """,
                opportunity_id,
                user_id,
                company_id,
                observation_id,
            )

        async def fail_outbox(*args, **kwargs):
            raise RuntimeError("forced outbox failure")

        repository._outbox = fail_outbox
        with pytest.raises(RuntimeError, match="forced outbox failure"):
            await repository.transition_workflow(
                user_id=user_id,
                opportunity_id=opportunity_id,
                expected_version=0,
                target_state=WorkflowState.TRIAGE_PENDING,
                transition_id=uuid4(),
            )
        async with pool.acquire() as connection:
            state = await connection.fetchrow(
                """
                select workflow_state,workflow_version from public.opportunities
                where user_id=$1 and opportunity_id=$2
                """,
                user_id,
                opportunity_id,
            )
            assert dict(state) == {"workflow_state": "admitted", "workflow_version": 0}
            event_id = uuid4()
            aggregate_id = uuid4()
            await connection.execute(
                """
                insert into public.authority_projection_receipts (
                  receipt_id,user_id,event_id,consumer,aggregate_type,aggregate_id
                ) values ($1,$2,$3,'authority-contract','opportunity',$4)
                """,
                uuid4(),
                user_id,
                event_id,
                aggregate_id,
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await connection.execute(
                    """
                    insert into public.authority_projection_receipts (
                      receipt_id,user_id,event_id,consumer,aggregate_type,aggregate_id
                    ) values ($1,$2,$3,'authority-contract','opportunity',$4)
                    """,
                    uuid4(),
                    user_id,
                    event_id,
                    aggregate_id,
                )
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.authority_projection_receipts where user_id=$1", user_id)
            await connection.execute("delete from public.domain_outbox where user_id=$1", user_id)
            await connection.execute("delete from public.opportunities where user_id=$1", user_id)
            await connection.execute("delete from public.source_observations where user_id=$1", user_id)
            await connection.execute("delete from public.companies where user_id=$1", user_id)
            await connection.execute(
                "delete from public.tenant_authority_rollouts where user_id=$1", user_id
            )
        await pool.close()
