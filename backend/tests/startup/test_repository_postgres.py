import os
import asyncio
from pathlib import Path
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from startups import StartupRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for startup PostgreSQL contracts",
)


async def _insert(connection, user_id: str, startup_id: str, *, name: str = "Acme", reviewed: bool = False, decided: bool = False, escalated: bool = False):
    review = {"verdict": "PASS", "fund_thesis_version_id": "thesis-1", "overall_summary": "Summary"} if reviewed else None
    partner = {"recommendation": "YES", "human_review_required": escalated} if decided else None
    await connection.execute(
        """insert into public.startups
           (user_id,startup_id,scout_info,review_info,partner_info,financials,agent_trace)
           values ($1,$2,$3::jsonb,$4::jsonb,$5::jsonb,$6::jsonb,$7::jsonb)""",
        user_id,
        startup_id,
        json.dumps({"name": name, "one_line": "Tools", "sector": "SaaS", "scout_type": "market_driven", "confidence_score": 0.8, "problem": "Problem", "solution": "Solution", "target_users": "Users", "why_now": "Now"}),
        json.dumps(review) if review is not None else None,
        json.dumps(partner) if partner is not None else None,
        '{}',
        '{"scout":{"ok":true}}',
    )


@pytest.mark.asyncio
async def test_startup_repository_reads_text_ids_and_preserves_projections():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-contract-{uuid4()}"
    other_user = f"startup-other-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert(connection, user_id, "startup-human-readable-42")
            await _insert(connection, user_id, "startup-reviewed", name="Reviewed", reviewed=True)
            await _insert(connection, user_id, "startup-decided", name="Decided", reviewed=True, decided=True, escalated=True)
            await _insert(connection, other_user, "startup-hidden", name="Hidden")

        repository = StartupRepository(pool)
        detail = await repository.get_startup(user_id, "startup-human-readable-42")
        assert detail is not None
        assert detail["startup_id"] == "startup-human-readable-42"
        assert detail["scout_info"]["name"] == "Acme"

        assert await repository.get_startup(user_id, "startup-hidden") is None
        assert await repository.exists(user_id, "startup-reviewed") is True
        assert await repository.exists(user_id, "startup-hidden") is False

        projection = await repository.list_projection(user_id, limit=2, offset=0)
        assert len(projection) == 2
        assert all("display_name" in row for row in projection)
        assert all("scout_info" in row for row in projection)
        assert {row["display_name"] for row in projection} == {"Decided", "Reviewed"}

        assert len(await repository.list_unreviewed(user_id)) == 1
        assert len(await repository.list_undecided(user_id)) == 1
        assert len(await repository.list_reviewed(user_id)) == 2
        assert len(await repository.list_decided(user_id, decision="YES")) == 1
        assert len(await repository.list_pending_escalations(user_id)) == 1
        assert await repository.count_unreviewed(user_id) == 1
        assert await repository.count_undecided(user_id) == 1
        assert await repository.count_tenant(user_id) == 3
        assert await repository.find_by_display_name(user_id, " acme ") == "startup-human-readable-42"
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id in ($1,$2)", user_id, other_user)
        await pool.close()


@pytest.mark.asyncio
async def test_generated_columns_are_database_owned_and_not_writable():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-generated-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert(connection, user_id, "text-id")
            generated = await connection.fetch(
                """select attname,attgenerated from pg_attribute a
                   join pg_class c on c.oid=a.attrelid
                   join pg_namespace n on n.oid=c.relnamespace
                   where n.nspname='public' and c.relname='startups' and a.attgenerated <> ''"""
            )
            assert {row["attname"] for row in generated} >= {"display_name", "partner_decision", "list_score"}
            with pytest.raises(asyncpg.PostgresError):
                await connection.execute(
                    "update public.startups set display_name='forbidden' where user_id=$1",
                    user_id,
                )
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_list_score_averages_only_scored_dimensions():
    """Regression (2026-08-19): list_score used to COALESCE unscored dimensions
    to 0.0 but always divide by a fixed 4, so a startup scored on only 2 of 4
    dimensions got two phantom zeros averaged in -- the docket row (list_score)
    disagreed sharply with every other scoring path, which excludes unscored
    dimensions instead of failing them. technical=4.31 + execution=5.562833,
    market/product unscored should average to (4.31+5.562833)/2, not /4."""
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-list-score-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """insert into public.startups
                   (user_id,startup_id,scout_info,review_info,partner_info,financials,agent_trace)
                   values ($1,$2,$3::jsonb,$4::jsonb,null,'{}','{}')""",
                user_id,
                "partial-scored",
                json.dumps({"name": "Partial Co", "one_line": "x", "sector": "SaaS", "scout_type": "market_driven", "confidence_score": 0.5, "problem": "p", "solution": "s", "target_users": "u", "why_now": "n"}),
                json.dumps({"technical_score": 4.31, "execution_score": 5.562833}),
            )
            row = await connection.fetchrow(
                "select list_score from public.startups where user_id=$1 and startup_id=$2",
                user_id, "partial-scored",
            )
            assert row["list_score"] == pytest.approx((4.31 + 5.562833) / 2, abs=1e-6)

            await connection.execute(
                "update public.startups set review_info=$3::jsonb where user_id=$1 and startup_id=$2",
                user_id, "partial-scored", json.dumps({}),
            )
            row = await connection.fetchrow(
                "select list_score from public.startups where user_id=$1 and startup_id=$2",
                user_id, "partial-scored",
            )
            assert row["list_score"] is None
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_targeted_writes_preserve_mature_state_and_text_ids():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-writes-{uuid4()}"
    try:
        repository = StartupRepository(pool)
        scout = SimpleNamespace(
            startup_id="human-readable-id",
            name="New Company",
            sector="SaaS / AI",
            model_dump=lambda mode="json": {
                "startup_id": "human-readable-id",
                "name": "New Company",
                "sector": "SaaS / AI",
            },
        )
        financials = SimpleNamespace(model_dump=lambda mode="json": {"revenue": 42})
        assert await repository.create_startup(user_id, scout, financials=financials) == "human-readable-id"
        assert await repository.update_financials(user_id, "human-readable-id", financials) is True
        seen_at = datetime.now(timezone.utc)
        assert await repository.acknowledge_startup(user_id, "human-readable-id", seen_at) is True

        async with pool.acquire() as connection:
            await connection.execute(
                "update public.startups set review_info=$3::jsonb, partner_info=$4::jsonb, "
                "agent_trace=$5::jsonb, investment_memo_markdown='mature' where user_id=$1 and startup_id=$2",
                user_id, "human-readable-id", '{"reviewed":true}', '{"recommendation":"YES"}',
                '{"scout":{"ok":true}}',
            )
        duplicate = SimpleNamespace(
            startup_id="replacement-id", name="New Company", sector="Other",
            model_dump=lambda mode="json": {"startup_id": "replacement-id", "name": "New Company", "sector": "Other"},
        )
        assert await repository.create_startup(user_id, duplicate, financials=financials) == "human-readable-id"
        await asyncio.gather(
            repository.update_financials(user_id, "human-readable-id", SimpleNamespace(model_dump=lambda mode="json": {"revenue": 99})),
            repository.acknowledge_startup(user_id, "human-readable-id", datetime.now(timezone.utc)),
        )
        row = await repository.get_row(user_id, "human-readable-id")
        assert row["review_info"]["reviewed"] is True
        assert row["partner_info"]["recommendation"] == "YES"
        assert row["agent_trace"]["scout"]["ok"] is True
        assert row["financials"]["revenue"] == 99
        assert row["acknowledged_at"] is not None
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_create_startup_refreshes_confidence_only_while_unreviewed():
    """Regression (product decision, 2026-08-19): create_startup dedupes a
    rediscovered company by name and returns the existing row untouched --
    but Scout's triage-funnel gate compares confidence_score against a
    threshold, so a company stuck on its first-ever (possibly stale, e.g.
    pre-deterministic-scorer) confidence would never re-enter review even
    after a fresh discovery scores it differently. confidence_score must
    refresh on redup while unreviewed, and must NOT refresh once reviewed."""
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-confidence-refresh-{uuid4()}"
    try:
        repository = StartupRepository(pool)

        def _scout(startup_id: str, name: str, confidence: float):
            return SimpleNamespace(
                startup_id=startup_id,
                name=name,
                sector="SaaS",
                confidence_score=confidence,
                model_dump=lambda mode="json": {
                    "startup_id": startup_id,
                    "name": name,
                    "sector": "SaaS",
                    "confidence_score": confidence,
                },
            )

        first_id = await repository.create_startup(user_id, _scout("id-1", "Rediscovered Co", 0.33))
        assert first_id == "id-1"

        rediscovery = _scout("id-2", "Rediscovered Co", 0.67)
        assert await repository.create_startup(user_id, rediscovery) == first_id
        row = await repository.get_row(user_id, first_id)
        assert row["scout_info"]["confidence_score"] == 0.67

        async with pool.acquire() as connection:
            await connection.execute(
                "update public.startups set review_info=$3::jsonb where user_id=$1 and startup_id=$2",
                user_id, first_id, '{"verdict": "PASS"}',
            )

        post_review_rediscovery = _scout("id-3", "Rediscovered Co", 0.1)
        assert await repository.create_startup(user_id, post_review_rediscovery) == first_id
        row = await repository.get_row(user_id, first_id)
        assert row["scout_info"]["confidence_score"] == 0.67
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_scalar_write_whitelist_rejects_generated_and_shared_fields():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-scalars-{uuid4()}"
    try:
        repository = StartupRepository(pool)
        async with pool.acquire() as connection:
            await _insert(connection, user_id, "scalar-id")
        with pytest.raises(ValueError):
            await repository.update_scalar_fields(user_id, "scalar-id", display_name="nope")
        with pytest.raises(ValueError):
            await repository.update_scalar_fields(user_id, "scalar-id", review_info={})
        assert await repository.update_scalar_fields(user_id, "scalar-id", queue_reason="Seen") is True
        row = await repository.get_row(user_id, "scalar-id")
        assert row["queue_reason"] == "Seen"
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_stage_writes_merge_owned_fields_without_replacing_siblings():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-stages-{uuid4()}"
    try:
        repository = StartupRepository(pool)
        async with pool.acquire() as connection:
            await _insert(connection, user_id, "stage-id")
        review = SimpleNamespace(model_dump=lambda mode="json": {"verdict": "STRONG", "overall_score": 7, "overall_summary": "Good", "key_risks": []})
        partner = SimpleNamespace(
            partnered_at=datetime.now(timezone.utc),
            human_review_required=False,
            recommendation="YES",
            model_dump=lambda mode="json": {"recommendation": "YES"},
        )
        review_result, partner_result = await asyncio.gather(
            repository.update_review(user_id, "stage-id", review, settings={}),
            repository.update_partner(user_id, "stage-id", partner, settings={}),
        )
        assert review_result is True
        assert partner_result is True
        assert await repository.merge_agent_trace_stage(
            user_id, "stage-id", "evaluation_manifest", {"manifest": True}
        ) is True
        await asyncio.gather(
            repository.acknowledge_startup(user_id, "stage-id", datetime.now(timezone.utc)),
            repository.apply_human_resolution(
                user_id, "stage-id",
                {"human_resolution": {"decision": "YES", "resolved_at": "2026-08-11T00:00:00Z"}, "unresolved_at": None},
            ),
        )
        row = await repository.get_row(user_id, "stage-id")
        assert row["review_info"]["verdict"] == "STRONG"
        assert row["partner_info"]["recommendation"] == "YES"
        assert row["agent_trace"]["reviewer"]
        assert row["agent_trace"]["partner"]
        assert row["agent_trace"]["evaluation_manifest"]
        assert row["acknowledged_at"] is not None
        assert row["human_resolution"]["decision"] == "YES"
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_agent_trace_stage_merge_contract_preserves_sibling_stages():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-trace-{uuid4()}"
    try:
        async with pool.acquire() as connection:
            await _insert(connection, user_id, "trace-id")
            await connection.execute(
                """update public.startups
                   set agent_trace=coalesce(agent_trace,'{}'::jsonb) || $2::jsonb
                   where user_id=$1 and startup_id='trace-id'""",
                user_id, json.dumps({"reviewer": {"score": 7}}),
            )
            await connection.execute(
                """update public.startups
                   set agent_trace=coalesce(agent_trace,'{}'::jsonb) || $2::jsonb
                   where user_id=$1 and startup_id='trace-id'""",
                user_id, json.dumps({"partner": {"decision": "YES"}}),
            )
            trace = await connection.fetchval(
                "select agent_trace from public.startups where user_id=$1 and startup_id='trace-id'",
                user_id,
            )
            if isinstance(trace, str):
                trace = json.loads(trace)
            assert trace["scout"]["ok"] is True
            assert trace["reviewer"]["score"] == 7
            assert trace["partner"]["decision"] == "YES"
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_pruning_startups_also_removes_pipeline_state_for_deleted_rows():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-prune-state-{uuid4()}"
    startup_id = "stale-startup"
    run_id = uuid4()
    try:
        async with pool.acquire() as connection:
            await _insert(connection, user_id, startup_id)
            await connection.execute(
                """insert into public.startup_pipeline_state
                   (user_id,startup_id,pipeline_run_id,status)
                   values ($1,$2,$3,'ingesting')""",
                user_id,
                startup_id,
                run_id,
            )

        assert await StartupRepository(pool).remove_startups_without_references(user_id) == 1

        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.startup_pipeline_state where user_id=$1 and startup_id=$2",
                user_id,
                startup_id,
            ) == 0
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_pipeline_state where user_id=$1", user_id)
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


@pytest.mark.asyncio
async def test_removing_one_startup_also_removes_pipeline_state():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    user_id = f"startup-remove-state-{uuid4()}"
    startup_id = "removed-startup"
    try:
        async with pool.acquire() as connection:
            await _insert(connection, user_id, startup_id)
            await connection.execute(
                """insert into public.startup_pipeline_state
                   (user_id,startup_id,pipeline_run_id,status)
                   values ($1,$2,$3,'ready')""",
                user_id,
                startup_id,
                uuid4(),
            )

        assert await StartupRepository(pool).remove_startup(user_id, startup_id) is True

        async with pool.acquire() as connection:
            assert await connection.fetchval(
                "select count(*) from public.startup_pipeline_state where user_id=$1 and startup_id=$2",
                user_id,
                startup_id,
            ) == 0
    finally:
        async with pool.acquire() as connection:
            await connection.execute("delete from public.startup_pipeline_state where user_id=$1", user_id)
            await connection.execute("delete from public.startups where user_id=$1", user_id)
        await pool.close()


def test_startup_repository_has_only_explicit_targeted_write_sql():
    source = (Path(__file__).parents[2] / "startups" / "repository.py").read_text(encoding="utf-8")
    assert "upsert_startup" not in source.lower()
    assert "display_name=" not in source.lower()
    assert "upsert_startup" not in source.lower()
