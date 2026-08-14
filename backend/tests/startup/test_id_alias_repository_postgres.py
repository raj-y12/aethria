import json
import os
from uuid import uuid4

import pytest

from startup_id_alias_repository import StartupIdAliasConflict, StartupIdAliasRepository
from startup_id_alias_backfill import load_reconciliation_artifact, repository_rows
from startup_resolver import CanonicalStartupResolver


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for startup alias PostgreSQL contracts",
)


async def _insert_startup(connection, user_id: str, startup_id: str, name: str | None = None):
    await connection.execute(
        """insert into public.startups
           (user_id,startup_id,scout_info,financials)
           values ($1,$2,$3::jsonb,'{}'::jsonb)""",
        user_id,
        startup_id,
        json.dumps({"name": name or startup_id, "one_line": "A useful company"}),
    )


@pytest.mark.asyncio
async def test_approved_alias_resolves_and_is_tenant_scoped():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"alias-user-{uuid4()}"
    other_user = f"alias-other-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert_startup(connection, user_id, "canonical-1")
            await _insert_startup(connection, other_user, "canonical-1")
        repository = StartupIdAliasRepository(pool)
        await repository.insert_approved_alias(
            user_id,
            "legacy-1",
            "canonical-1",
            source="portfolio_startups",
            evidence={"approved_batch": "4B.5C"},
        )
        assert await repository.resolve_legacy_id(user_id, "legacy-1") == "canonical-1"
        assert await repository.resolve_legacy_id(other_user, "legacy-1") is None
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_id_aliases where user_id in ($1,$2)", user_id, other_user)
            await connection.execute("delete from public.startups where user_id in ($1,$2)", user_id, other_user)
        await pool.close()


@pytest.mark.asyncio
async def test_alias_states_unknown_and_conflicts_fail_closed():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"alias-state-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert_startup(connection, user_id, "canonical-1")
            await _insert_startup(connection, user_id, "canonical-2", name="Canonical Two")
            await connection.execute(
                """insert into public.startup_id_aliases
                   (user_id,legacy_startup_id,canonical_startup_id,source,verification_state)
                   values ($1,'candidate-1','canonical-1','test','candidate'),
                          ($1,'revoked-1','canonical-1','test','revoked')""",
                user_id,
            )
        repository = StartupIdAliasRepository(pool)
        assert await repository.resolve_legacy_id(user_id, "candidate-1") is None
        assert await repository.resolve_legacy_id(user_id, "revoked-1") is None
        assert await repository.resolve_legacy_id(user_id, "unknown") is None
        await repository.insert_approved_alias(
            user_id, "legacy-1", "canonical-1", source="test", evidence={}
        )
        await repository.insert_approved_alias(
            user_id, "legacy-1", "canonical-1", source="test", evidence={}
        )
        with pytest.raises(StartupIdAliasConflict):
            await repository.insert_approved_alias(
                user_id, "legacy-1", "canonical-2", source="test", evidence={}
            )
        with pytest.raises(asyncpg.PostgresError):
            await repository.insert_approved_alias(
                user_id, "legacy-missing-target", "missing-canonical", source="test", evidence={}
            )
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_id_aliases where user_id=$1", user_id)
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_resolver_uses_canonical_startup_repository_without_portfolio_table():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"alias-resolver-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert_startup(connection, user_id, "canonical-1")
        aliases = StartupIdAliasRepository(pool)
        await aliases.insert_approved_alias(
            user_id, "legacy-1", "canonical-1", source="test", evidence={}
        )
        resolver = CanonicalStartupResolver(pool)
        assert (await resolver.resolve_startup_id(user_id, "canonical-1")) == "canonical-1"
        assert (await resolver.resolve_startup_id(user_id, "legacy-1")) == "canonical-1"
        assert await resolver.resolve_startup_id(user_id, "missing") is None
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_id_aliases where user_id=$1", user_id)
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_approved_reconciliation_artifact_resolves_all_133_seeded_mappings():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_ids = {item["user_id"] for item in load_reconciliation_artifact()}
    rows = repository_rows(load_reconciliation_artifact())
    try:
        async with pool.acquire() as connection:
            for item in rows:
                await _insert_startup(
                    connection,
                    item["user_id"],
                    item["canonical_startup_id"],
                    name=f"Seed {item['canonical_startup_id']}",
                )
        aliases = StartupIdAliasRepository(pool)
        inserted = await aliases.insert_approved_aliases(rows)
        assert len(inserted) == 133
        for item in rows:
            assert await aliases.resolve_legacy_id(
                item["user_id"], item["legacy_startup_id"]
            ) == item["canonical_startup_id"]
        assert len(await aliases.list_aliases_for_validation(next(iter(user_ids)))) > 0
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_id_aliases where user_id = any($1::text[])", list(user_ids))
            await connection.execute("delete from public.startups where user_id = any($1::text[])", list(user_ids))
        await pool.close()
