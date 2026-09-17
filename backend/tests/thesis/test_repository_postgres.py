import json
import os
from uuid import uuid4

import pytest

from fund_thesis import FundThesisRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for thesis PostgreSQL contracts",
)


async def _insert_fixture(connection, user_id: str, other_user: str):
    thesis_id = uuid4()
    version_one = uuid4()
    version_two = uuid4()
    await connection.execute(
        """
        insert into public.fund_thesis (id,user_id)
        values ($1,$2)
        """,
        thesis_id,
        user_id,
    )
    await connection.execute(
        """
        insert into public.fund_thesis_versions
          (id,user_id,thesis_id,version_number,raw_text,parsed_json,is_active)
        values ($1,$2,$3,1,'first',$4::jsonb,false),
               ($5,$2,$3,2,'second',$6::jsonb,true)
        """,
        version_one,
        user_id,
        thesis_id,
        json.dumps({"sectors": ["SaaS"]}),
        version_two,
        json.dumps({"sectors": ["Infrastructure"]}),
    )
    await connection.execute(
        "update public.fund_thesis set active_version_id=$2 where id=$1",
        thesis_id,
        version_two,
    )
    await connection.execute(
        """
        insert into public.fund_thesis_embeddings
          (user_id,version_id,embedding_vector,model)
        values ($1,$2,$3::jsonb,'test-model')
        """,
        user_id,
        version_two,
        json.dumps([0.1, 0.2]),
    )
    link_id = uuid4()
    await connection.execute(
        """
        insert into public.fund_thesis_pipeline_link
          (id,user_id,thesis_version_id,pipeline_run_id,affected_startups_count)
        values ($1,$2,$3,$4,7)
        """,
        link_id,
        user_id,
        version_two,
        uuid4(),
    )
    return thesis_id, version_one, version_two, link_id


@pytest.mark.asyncio
async def test_repository_reads_active_history_embedding_and_links_tenant_safely():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"thesis-{uuid4()}"
    other_user = f"other-{uuid4()}"
    thesis_id, version_one, version_two, link_id = None, None, None, None
    try:
        async with pool.acquire() as connection:
            thesis_id, version_one, version_two, link_id = await _insert_fixture(
                connection, user_id, other_user
            )
        repository = FundThesisRepository(pool)

        active = await repository.get_active(user_id)
        assert active["thesis_id"] == str(thesis_id)
        assert active["version_id"] == str(version_two)
        assert active["version_number"] == 2
        assert active["parsed_json"] == {"sectors": ["Infrastructure"]}
        assert active["embedding"] == [0.1, 0.2]

        history = await repository.list_versions(user_id, thesis_id=str(thesis_id))
        assert [row["version_number"] for row in history] == [2, 1]
        assert (await repository.get_version(user_id, str(version_one)))["version_id"] == str(version_one)
        assert (await repository.get_embedding(user_id, str(version_two)))["model"] == "test-model"
        links = await repository.get_pipeline_links(user_id, version_id=str(version_two))
        assert links[0]["link_id"] == str(link_id)

        assert await repository.get_active(other_user) is None
        assert await repository.get_version(other_user, str(version_one)) is None
        assert await repository.get_embedding(other_user, str(version_two)) is None
        assert await repository.get_pipeline_links(other_user) == []
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis_pipeline_link where id=$1", link_id)
            await connection.execute("delete from public.fund_thesis_embeddings where version_id=any($1::uuid[])", [version_one, version_two])
            await connection.execute("delete from public.fund_thesis where id=$1", thesis_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_allows_missing_thesis_active_version_and_embedding():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"missing-{uuid4()}"
    thesis_id = uuid4()
    try:
        repository = FundThesisRepository(pool)
        assert await repository.get_active(user_id) is None
        async with pool.acquire() as connection:
            await connection.execute("insert into public.fund_thesis (id,user_id) values ($1,$2)", thesis_id, user_id)
        assert await repository.get_active(user_id) is None
        assert await repository.list_versions_missing_embeddings(user_id) == []
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where id=$1", thesis_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_lists_versions_missing_embeddings_and_respects_limit():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"backfill-{uuid4()}"
    thesis_id = uuid4()
    version_ids = [uuid4(), uuid4()]
    try:
        async with pool.acquire() as connection:
            await connection.execute("insert into public.fund_thesis (id,user_id) values ($1,$2)", thesis_id, user_id)
            await connection.executemany(
                "insert into public.fund_thesis_versions (id,user_id,thesis_id,version_number,raw_text) values ($1,$2,$3,$4,$5)",
                [(version_ids[0], user_id, thesis_id, 1, "one"), (version_ids[1], user_id, thesis_id, 2, "two")],
            )
            await connection.execute("update public.fund_thesis set active_version_id=$2 where id=$1", thesis_id, version_ids[1])
        repository = FundThesisRepository(pool)
        rows = await repository.list_versions_missing_embeddings(user_id, limit=1)
        assert len(rows) == 1
        assert rows[0]["version_id"] == str(version_ids[1])
        active_only = await repository.list_versions_missing_embeddings(user_id, only_active=True)
        assert [row["version_id"] for row in active_only] == [str(version_ids[1])]
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where id=$1", thesis_id)
        await pool.close()


@pytest.mark.asyncio
async def test_portable_integrity_rejects_cross_tenant_links_and_duplicate_active_versions():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"integrity-{uuid4()}"
    thesis_id = uuid4()
    version_id = uuid4()
    try:
        async with pool.acquire() as connection:
            await connection.execute("insert into public.fund_thesis (id,user_id) values ($1,$2)", thesis_id, user_id)
            await connection.execute("insert into public.fund_thesis_versions (id,user_id,thesis_id,version_number,is_active) values ($1,$2,$3,1,true)", version_id, user_id, thesis_id)
            await connection.execute("update public.fund_thesis set active_version_id=$2 where id=$1", thesis_id, version_id)
            with pytest.raises(asyncpg.UniqueViolationError):
                await connection.execute("insert into public.fund_thesis_versions (user_id,thesis_id,version_number,is_active) values ($1,$2,2,true)", user_id, thesis_id)
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await connection.execute("insert into public.fund_thesis_embeddings (user_id,version_id,embedding_vector) values ($1,$2,'[]'::jsonb)", f"wrong-{uuid4()}", version_id)
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where id=$1", thesis_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_publishes_atomically_with_sequential_versions_and_link():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = FundThesisRepository(pool)
    user_id = f"publish-{uuid4()}"
    try:
        first = await repository.publish_version(
            user_id,
            raw_text="first thesis",
            parsed_json={"sectors": ["SaaS"]},
            embedding=[0.1, 0.2],
            embedding_model="test-model",
            pipeline_run_id=str(uuid4()),
            affected_startups_count=3,
        )
        second = await repository.publish_version(
            user_id,
            raw_text="second thesis",
            parsed_json={"sectors": ["Infra"]},
            embedding=[],
            embedding_model="none",
        )
        assert first["version_number"] == 1
        assert second["version_number"] == 2
        active = await repository.get_active(user_id)
        assert active["version_id"] == second["version_id"]
        assert active["embedding"] == []
        assert len(await repository.get_pipeline_links(user_id)) == 2
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.fund_thesis_versions where user_id=$1 and is_active",
                user_id,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_publication_reconciles_existing_settings_projection():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = FundThesisRepository(pool)
    user_id = f"publish-settings-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """insert into public.settings (user_id,key,data)
                   values ($1,$1,$2::jsonb)""",
                user_id,
                json.dumps({
                    "fund_config": {
                        "version": 1,
                        "mandate": {"preferredSectors": ["Old"]},
                    },
                    "agent_config": {"scouts_enabled": True},
                }),
            )

        result = await repository.publish_version(
            user_id,
            raw_text="canonical thesis",
            parsed_json={
                "sectors": ["AI"],
                "stage_focus": ["Seed"],
                "geography": ["Europe"],
                "exclusions": ["Crypto"],
                "risk_profile": "balanced",
            },
            embedding=[],
        )

        async with pool.acquire() as connection:
            settings = await connection.fetchval(
                "select data from public.settings where user_id=$1 and key=$1",
                user_id,
            )
        if isinstance(settings, str):
            settings = json.loads(settings)
        fund_config = settings["fund_config"]
        assert fund_config["version"] == result["version_number"]
        assert fund_config["activePolicyVersionId"] == result["version_id"]
        assert fund_config["mandate"]["preferredSectors"] == ["AI"]
        assert fund_config["mandate"]["excludedSectorList"] == ["Crypto"]
        assert settings["agent_config"]["scouts_enabled"] is True
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.settings where user_id=$1", user_id)
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_publication_rolls_back_when_pipeline_link_fails():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = FundThesisRepository(pool)
    user_id = f"rollback-{uuid4()}"
    try:
        with pytest.raises((asyncpg.DataError, ValueError)):
            await repository.publish_version(
                user_id,
                raw_text="must roll back",
                parsed_json={},
                embedding=[0.3],
                embedding_model="test-model",
                pipeline_run_id="not-a-uuid",
            )
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.fund_thesis where user_id=$1", user_id
            ) == 0
            assert await connection.fetchval(
                "select count(*) from public.fund_thesis_versions where user_id=$1", user_id
            ) == 0
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_repository_activation_is_tenant_safe_and_transactional():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=3)
    repository = FundThesisRepository(pool)
    user_id = f"activate-{uuid4()}"
    other_user = f"other-{uuid4()}"
    try:
        first = await repository.publish_version(
            user_id, raw_text="one", parsed_json={}, embedding=[], embedding_model="none"
        )
        second = await repository.publish_version(
            user_id, raw_text="two", parsed_json={}, embedding=[], embedding_model="none"
        )
        with pytest.raises(ValueError, match="version not found"):
            await repository.activate_version(other_user, second["version_id"])
        await repository.activate_version(user_id, first["version_id"], pipeline_run_id=str(uuid4()))
        active = await repository.get_active(user_id)
        assert active["version_id"] == first["version_id"]
        assert active["is_active"] is True
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_concurrent_publications_serialize_versions():
    import asyncio
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=6)
    repository = FundThesisRepository(pool)
    user_id = f"concurrent-{uuid4()}"
    try:
        results = await asyncio.gather(*[
            repository.publish_version(
                user_id,
                raw_text=f"thesis-{index}",
                parsed_json={"index": index},
                embedding=[],
                embedding_model="none",
            )
            for index in range(4)
        ])
        assert sorted(row["version_number"] for row in results) == [1, 2, 3, 4]
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.fund_thesis_versions where user_id=$1 and is_active",
                user_id,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_repository_bootstrap_is_idempotent_under_concurrency_and_embedding_upsert_is_retryable():
    import asyncio
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=6)
    repository = FundThesisRepository(pool)
    user_id = f"bootstrap-{uuid4()}"
    try:
        results = await asyncio.gather(*[
            repository.ensure_default(
                user_id,
                raw_text="default thesis",
                parsed_json={"sectors": []},
            )
            for _ in range(4)
        ])
        assert {row["version_id"] for row in results}.__len__() == 1
        version_id = results[0]["version_id"]
        await repository.upsert_embedding(user_id, version_id, [0.4, 0.5], "test-model")
        await repository.upsert_embedding(user_id, version_id, [0.6, 0.7], "test-model")
        active = await repository.get_active(user_id)
        assert active["embedding"] == [0.6, 0.7]
        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.fund_thesis_embeddings where version_id=$1",
                version_id,
            ) == 1
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()
