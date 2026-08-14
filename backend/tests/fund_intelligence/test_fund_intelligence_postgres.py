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
        settings_published = await repository.publish_settings_policy(
            user_id=user_id,
            actor_id=user_id,
            fund_config={"scoringWeights": [{"key": "market", "weight": 40}]},
            policy_hash="hash-settings",
        )
        active = await repository.get_active_published_policy(user_id=user_id)
        assert settings_published["publication_source"] == "settings"
        assert active["governed_policy_version_id"] == settings_published[
            "governed_policy_version_id"
        ]
        assert active["policy_hash"] == "hash-settings"
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


@pytest.mark.asyncio
async def test_settings_policy_publication_is_idempotent_and_preserves_unrelated_settings():
    import asyncpg
    from fund_intelligence.repository import FundIntelligenceRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = FundIntelligenceRepository(pool)
    user_id = f"policy-settings-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                "insert into public.settings (user_id,key,data) values ($1,$1,$2::jsonb)",
                user_id,
                '{"agent_config":{"reviewers_enabled":true},"fund_config":{"draftOnly":true}}',
            )
        first = await repository.publish_settings_policy(
            user_id=user_id,
            actor_id=user_id,
            fund_config={"scoringWeights": [{"key": "market", "weight": 40}]},
            policy_hash="hash-settings-1",
            expected_policy_id="",
            expected_policy_hash="",
        )
        retry = await repository.publish_settings_policy(
            user_id=user_id,
            actor_id=user_id,
            fund_config={"scoringWeights": [{"key": "market", "weight": 40}]},
            policy_hash="hash-settings-1",
        )
        assert retry["governed_policy_version_id"] == first["governed_policy_version_id"]
        with pytest.raises(RuntimeError, match="stale"):
            await repository.publish_settings_policy(
                user_id=user_id,
                actor_id=user_id,
                fund_config={"scoringWeights": [{"key": "market", "weight": 50}]},
                policy_hash="hash-settings-2",
                expected_policy_id="old-policy",
                expected_policy_hash="old-hash",
            )
        async with pool.acquire() as connection:
            settings = await connection.fetchval(
                "select data from public.settings where user_id=$1 and key=$1", user_id
            )
            settings = settings if isinstance(settings, dict) else __import__("json").loads(settings)
            assert settings["agent_config"] == {"reviewers_enabled": True}
            assert settings["fund_config"]["draftOnly"] is True
            assert settings["fund_config"]["activePolicyVersionId"] == first["governed_policy_version_id"]
            assert await connection.fetchval(
                "select count(*) from public.governed_policy_versions where user_id=$1 and status='published'",
                user_id,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.domain_outbox where user_id=$1", user_id)
            await connection.execute("delete from public.settings where user_id=$1", user_id)
            await connection.execute("delete from public.governed_policy_versions where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_concurrent_settings_policy_publications_allow_one_stale_writer_only():
    import asyncio
    import asyncpg
    from fund_intelligence.repository import FundIntelligenceRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=6)
    repository = FundIntelligenceRepository(pool)
    user_id = f"policy-concurrent-{uuid4()}"
    try:
        async def publish(index):
            return await repository.publish_settings_policy(
                user_id=user_id,
                actor_id=f"actor-{index}",
                fund_config={"scoringWeights": [{"key": "market", "weight": 30 + index}]},
                policy_hash=f"hash-concurrent-{index}",
                expected_policy_id="",
                expected_policy_hash="",
            )

        results = await asyncio.gather(publish(1), publish(2), return_exceptions=True)
        assert sum(not isinstance(result, Exception) for result in results) == 1
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.governed_policy_versions where user_id=$1 and status='published'",
                user_id,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.domain_outbox where user_id=$1", user_id)
            await connection.execute("delete from public.settings where user_id=$1", user_id)
            await connection.execute("delete from public.governed_policy_versions where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_canonical_policy_upgrade_uses_governed_repository_and_is_retry_safe():
    import asyncpg
    from fund_intelligence.repository import FundIntelligenceRepository
    from services.scoring.policy_upgrade import upgrade_published_policy_with_repository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = FundIntelligenceRepository(pool)
    user_id = f"policy-upgrade-{uuid4()}"
    config = {"scoringWeights": [{"key": "market", "weight": 40}]}
    try:
        first = await upgrade_published_policy_with_repository(
            repository, user_id, fund_config=config, apply=True
        )
        retry = await upgrade_published_policy_with_repository(
            repository, user_id, fund_config=config, apply=True
        )
        assert first.status.value == "applied"
        assert retry.status.value == "already_current"
        active = await repository.get_active_published_policy(user_id=user_id)
        assert active["governed_policy_version_id"] == first.new_policy_id
        assert active["publication_source"] == "settings"
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.domain_outbox where user_id=$1", user_id)
            await connection.execute("delete from public.settings where user_id=$1", user_id)
            await connection.execute("delete from public.governed_policy_versions where user_id=$1", user_id)
        await pool.close()
