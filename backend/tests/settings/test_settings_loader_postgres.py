import os

import pytest
from uuid import uuid4

from utils import settings_loader
from settings_repository import SettingsRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for settings PostgreSQL contract tests",
)


class Repository:
    def __init__(self, value=None):
        self.value = value
        self.reads = 0
        self.writes = []

    async def get(self, _user_id, *, key=None):
        self.reads += 1
        return self.value

    async def upsert(self, _user_id, data, *, key=None):
        self.writes.append(data)
        self.value = data


@pytest.mark.asyncio
async def test_loader_defaults_merge_legacy_coercions_and_malformed_rows():
    repository = Repository(
        {
            "fund_config": {"mandate": {"fundName": "Fund €"}},
            "user_preferences": {"savedFilters": ["seed"]},
            "fund_memory": {"historical_decisions": [None]},
            "agent_config": {
                "confidence_threshold": 0.5,
                "scouts_enabled": True,
                "unexpected": "ignored",
            },
            "fund_identity": {"fund_name": "Aethria", "unexpected": "ignored"},
        }
    )
    settings_loader._SETTINGS_CACHE.clear()

    value = await settings_loader.load_settings(
        "user-a", repository=repository, use_cache=False
    )

    assert value["fund_config"]["mandate"]["fundName"] == "Fund €"
    assert value["fund_config"]["mandate"]["mandateName"] == "Core mandate"
    assert value["user_preferences"]["savedFilters"] == ["seed"]
    assert value["fund_memory"]["historical_decisions"] == [None]
    assert value["agent_config"]["confidence_threshold"] == 0.2
    assert "unexpected" not in value["agent_config"]
    assert "unexpected" not in value["fund_identity"]

    repository.value = ["malformed"]
    malformed = await settings_loader.load_settings(
        "user-b", repository=repository, use_cache=False
    )
    assert malformed == settings_loader.DEFAULT_SETTINGS
    assert malformed is not settings_loader.DEFAULT_SETTINGS


@pytest.mark.asyncio
async def test_loader_cache_and_save_invalidation_preserve_replacement_semantics():
    repository = Repository({"agent_config": {"scouts_enabled": False}})
    settings_loader._SETTINGS_CACHE.clear()

    first = await settings_loader.load_settings("user-a", repository=repository)
    repository.value = {"agent_config": {"scouts_enabled": True}}
    cached = await settings_loader.load_settings("user-a", repository=repository)
    assert first == cached
    assert repository.reads == 1

    replacement = {"fund_config": {"mandate": {"fundName": "Only persisted section"}}}
    await settings_loader.save_settings(
        replacement, "user-a", repository=repository
    )
    refreshed = await settings_loader.load_settings("user-a", repository=repository)
    assert refreshed["fund_config"]["mandate"]["fundName"] == "Only persisted section"
    assert refreshed["agent_config"]["scouts_enabled"] is False
    assert repository.writes == [replacement]


@pytest.mark.asyncio
async def test_loader_projects_canonical_active_thesis_over_stale_settings():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"settings-thesis-{uuid4()}"
    thesis_id = uuid4()
    version_id = uuid4()
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """insert into public.settings (user_id,key,data)
                   values ($1,$1,$2::jsonb)""",
                user_id,
                '{"fund_config":{"version":34,"mandate":{"preferredSectors":["Old"]}},"agent_config":{"scouts_enabled":true}}',
            )
            await connection.execute(
                "insert into public.fund_thesis (id,user_id) values ($1,$2)",
                thesis_id,
                user_id,
            )
            await connection.execute(
                """insert into public.fund_thesis_versions
                   (id,user_id,thesis_id,version_number,raw_text,parsed_json,is_active)
                   values ($1,$2,$3,37,'canonical thesis',$4::jsonb,true)""",
                version_id,
                user_id,
                thesis_id,
                '{"sectors":["AI"],"stage_focus":["Seed"],"geography":["Europe"],"exclusions":["Crypto"]}',
            )
            await connection.execute(
                "update public.fund_thesis set active_version_id=$2 where id=$1",
                thesis_id,
                version_id,
            )

        settings_loader._SETTINGS_CACHE.clear()
        loaded = await settings_loader.load_settings(
            user_id,
            repository=SettingsRepository(pool),
            use_cache=False,
        )
        assert loaded["fund_config"]["version"] == 37
        assert loaded["fund_config"]["mandate"]["preferredSectors"] == ["AI"]
        assert loaded["fund_config"]["mandate"]["excludedSectorList"] == ["Crypto"]
        assert loaded["agent_config"]["scouts_enabled"] is True
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.settings where user_id=$1", user_id)
            await connection.execute("delete from public.fund_thesis where user_id=$1", user_id)
        await pool.close()
