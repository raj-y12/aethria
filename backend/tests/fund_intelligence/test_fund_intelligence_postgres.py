import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for governed-policy PostgreSQL tests",
)


@pytest.mark.asyncio
async def test_repository_preview_review_and_publication_are_hash_bound():
    import asyncpg
    from fund_intelligence.repository import FundIntelligenceRepository

    pool = await asyncpg.create_pool(
        os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3
    )
    repository = FundIntelligenceRepository(pool)
    user_id = f"policy-contract-{uuid4()}"
    proposal_id = uuid4()
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into public.policy_proposals (
                  policy_proposal_id,user_id,proposal_fingerprint,pattern_summary,
                  attribution,sample_size,confidence,proposed_policy_patch,status
                ) values ($1,$2,$3,'Contract proposal','policy_criterion_disagreement',
                          5,0.8,'{}'::jsonb,'ready_for_review')
                """,
                proposal_id,
                user_id,
                str(uuid4()),
            )

        preview = await repository.preview_impact(
            user_id=user_id,
            policy_proposal_id=str(proposal_id),
            actor_id=user_id,
            policy_hash="hash-bound",
            config_hash="config-bound",
        )
        assert preview["estimated_effect"]["config_hash"] == "config-bound"
        reviewed = await repository.review_proposal(
            user_id=user_id,
            policy_proposal_id=str(proposal_id),
            actor_id=user_id,
            action="edit_and_accept",
            rationale="Validated against the bounded preview.",
            resulting_fund_config={"scoringWeights": [{"key": "market", "weight": 30}]},
            policy_hash="hash-bound",
            config_hash="config-bound",
        )
        version_id = reviewed["policy_version"]["governed_policy_version_id"]
        published = await repository.mark_published(
            user_id=user_id,
            governed_policy_version_id=version_id,
            actor_id=user_id,
        )
        active = await repository.get_active_published_policy(user_id=user_id)
        assert published["status"] == "published"
        assert active["governed_policy_version_id"] == version_id
        assert active["policy_hash"] == "hash-bound"
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.domain_outbox where user_id=$1", user_id
            )
            await connection.execute(
                "update public.policy_proposals set resulting_policy_version_id=null where user_id=$1",
                user_id,
            )
            await connection.execute(
                "delete from public.governed_policy_versions where user_id=$1",
                user_id,
            )
            await connection.execute(
                "delete from public.policy_impact_previews where user_id=$1",
                user_id,
            )
            await connection.execute(
                "delete from public.policy_proposals where user_id=$1", user_id
            )
        await pool.close()
