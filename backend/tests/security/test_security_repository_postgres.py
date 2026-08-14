import asyncio
import os
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_rate_limit_is_atomic_and_window_state_is_preserved():
    import asyncpg

    from security.repository import SecurityRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = SecurityRepository(pool)
    key = f"rate:test:{uuid4()}"
    try:
        assert await repository.check_rate_limit(key, window_seconds=60)
        count, first_expiry = await repository.check_rate_limit(key, window_seconds=60)
        assert count == 2
        count, second_expiry = await repository.check_rate_limit(key, window_seconds=300)
        assert count == 3
        assert second_expiry == first_expiry
        results = await asyncio.gather(
            *(repository.check_rate_limit(key, window_seconds=300) for _ in range(8))
        )
        assert sorted(count for count, _expiry in results) == list(range(4, 12))
    finally:
        await pool.execute("delete from public.security_limits where key=$1", key)
        await pool.close()


@pytest.mark.asyncio
async def test_lock_owner_token_protects_release_and_allows_expiry_takeover():
    import asyncpg

    from security.repository import SecurityRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = SecurityRepository(pool)
    key = f"lock:test:{uuid4()}"
    owner_a = str(uuid4())
    owner_b = str(uuid4())
    try:
        assert await repository.acquire_lock(key, ttl_seconds=60, owner_token=owner_a)
        assert not await repository.acquire_lock(key, ttl_seconds=60, owner_token=owner_b)
        assert not await repository.release_lock(key, owner_token=owner_b)
        assert await repository.release_lock(key, owner_token=owner_a)
        assert not await repository.release_lock(key, owner_token=owner_a)
        assert await repository.acquire_lock(key, ttl_seconds=60, owner_token=owner_b)
        await pool.execute(
            "update public.security_limits set expires_at=clock_timestamp() - interval '1 second' where key=$1",
            key,
        )
        assert await repository.acquire_lock(key, ttl_seconds=60, owner_token=owner_a)
    finally:
        await pool.execute("delete from public.security_limits where key=$1", key)
        await pool.close()


def test_portable_security_migration_has_no_supabase_security_dependencies():
    from pathlib import Path

    sql = (Path(__file__).parents[3] / "db/migrations/20260811000021_security_and_schedules.sql").read_text().lower()
    assert "security_limits" in sql
    assert "lock_owner_token" in sql
    assert "auth." not in sql
    assert "service_role" not in sql
    assert "security definer" not in sql


def test_normal_runtime_security_paths_have_no_supabase_rpc_dependency():
    from pathlib import Path

    backend = Path(__file__).parents[2]
    deps = (backend / "routers/deps.py").read_text()
    schedule = (backend / "utils/job_schedule.py").read_text()
    api = (backend / "api.py").read_text()

    assert "SecurityRepository" in deps
    assert "build_security_store" not in deps
    assert ".rpc(" not in deps
    assert "get_service_client" not in schedule
    assert ".rpc(" not in schedule
    assert "security_check_rate_limit" not in api
    assert "security_acquire_lock" not in api
    assert "security_release_lock" not in api
    assert "claim_due_agent_jobs" not in api
