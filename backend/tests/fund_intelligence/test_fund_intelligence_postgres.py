import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for governed-policy PostgreSQL tests",
)


@pytest.mark.asyncio
async def test_governed_draft_requires_and_persists_the_previewed_policy_hash():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    transaction = connection.transaction()
    await transaction.start()
    user_id = f"policy-contract-{uuid4()}"
    proposal_id = uuid4()
    try:
        await connection.execute(
            """
            insert into public.policy_proposals (
              policy_proposal_id,user_id,proposal_fingerprint,pattern_summary,
              attribution,sample_size,confidence,proposed_policy_patch,status
            ) values ($1,$2,$3,'Contract proposal','policy_criterion_disagreement',
                      5,0.8,'{}'::jsonb,'accepted')
            """,
            proposal_id,
            user_id,
            str(uuid4()),
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                """
                insert into public.governed_policy_versions (
                  governed_policy_version_id,user_id,policy_proposal_id,
                  policy_patch,status,created_by
                ) values ($1,$2,$3,'{}'::jsonb,'draft',$2)
                """,
                uuid4(),
                user_id,
                proposal_id,
            )
        await transaction.rollback()
        transaction = connection.transaction()
        await transaction.start()
        # The failed transaction rolled back the proposal, so recreate it.
        await connection.execute(
            """
            insert into public.policy_proposals (
              policy_proposal_id,user_id,proposal_fingerprint,pattern_summary,
              attribution,sample_size,confidence,proposed_policy_patch,status
            ) values ($1,$2,$3,'Contract proposal','policy_criterion_disagreement',
                      5,0.8,'{}'::jsonb,'accepted')
            """,
            proposal_id,
            user_id,
            str(uuid4()),
        )
        stored = await connection.fetchval(
            """
            insert into public.governed_policy_versions (
              governed_policy_version_id,user_id,policy_proposal_id,policy_patch,
              policy_hash,status,created_by
            ) values ($1,$2,$3,'{}'::jsonb,'hash-bound','draft',$2)
            returning policy_hash
            """,
            uuid4(),
            user_id,
            proposal_id,
        )
        assert stored == "hash-bound"
    finally:
        await transaction.rollback()
        await connection.close()
