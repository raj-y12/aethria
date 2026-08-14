import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from meta.agent import MetaAgent
from pipeline_execution import MetaCycleResult, StageExecutionState
from portfolio.engine import PortfolioEngine


@pytest.mark.asyncio
async def test_claim_due_jobs_persists_intervals_and_isolates_tenants():
    import asyncpg

    from schedule_repository import ScheduleRepository

    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    intervals = {"meta": 86400, "signals": 3600}
    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = ScheduleRepository(pool)
    user_a = f"schedule-{uuid4()}"
    user_b = f"schedule-{uuid4()}"
    try:
        assert await repository.claim_due_jobs(user_a, intervals, now=now) == {"meta", "signals"}
        assert await repository.claim_due_jobs(user_a, intervals, now=now) == set()
        assert await repository.claim_due_jobs(user_b, {"signals": 3600}, now=now) == {"signals"}
    finally:
        await pool.execute("delete from public.agent_job_schedules where user_id = any($1::text[])", [user_a, user_b])
        await pool.close()


@pytest.mark.asyncio
async def test_concurrent_schedule_claim_has_one_winner():
    import asyncpg

    from schedule_repository import ScheduleRepository

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=4)
    repository = ScheduleRepository(pool)
    user_id = f"schedule-race-{uuid4()}"
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    try:
        await repository.claim_due_jobs(user_id, {"meta": 0}, now=now)
        await pool.execute(
            "update public.agent_job_schedules set last_claimed_at=$2 where user_id=$1",
            user_id,
            datetime(2026, 7, 14, 10, 59, tzinfo=timezone.utc),
        )
        results = await asyncio.gather(
            repository.claim_due_jobs(user_id, {"meta": 3600}, now=now),
            repository.claim_due_jobs(user_id, {"meta": 3600}, now=now),
        )
        assert sorted(results, key=lambda value: len(value)) == [set(), {"meta"}]
    finally:
        await pool.execute("delete from public.agent_job_schedules where user_id=$1", user_id)
        await pool.close()


def test_portable_schedule_migration_has_no_supabase_security_dependencies():
    sql = (
        Path(__file__).parents[2]
        / "db/migrations/20260811000021_security_and_schedules.sql"
    ).read_text().lower()

    assert "create table if not exists public.agent_job_schedules" in sql
    assert "primary key (user_id, job_name)" in sql
    assert "auth." not in sql
    assert "service_role" not in sql
    assert "security definer" not in sql


def test_meta_agent_skips_automatic_cycle_until_due(monkeypatch):
    agent = MetaAgent(user_id="user-schedule")
    ran = []
    monkeypatch.setattr("meta.agent.claim_due_jobs", lambda *a, **k: set())
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: ran.append(True) or {"cycle_number": 1})

    result = asyncio.run(agent.run_cycle())

    assert isinstance(result, MetaCycleResult)
    assert result.outcome.state is StageExecutionState.SKIPPED
    assert result.outcome.code == "meta_not_due"
    assert result.report is None
    assert ran == []


def test_meta_agent_manual_cycle_bypasses_schedule(monkeypatch):
    agent = MetaAgent(user_id="user-schedule")
    claims = []
    monkeypatch.setattr(
        "meta.agent.claim_due_jobs",
        lambda user_id, intervals: claims.append((user_id, intervals)) or {"meta"},
    )
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: {"cycle_number": 7})

    result = asyncio.run(agent.run_cycle(force=True))

    assert result.outcome.state is StageExecutionState.COMPLETED
    assert result.report == {"cycle_number": 7}
    assert claims == [("user-schedule", {"meta": 0})]


def test_portfolio_engine_runs_only_persistently_due_stages(monkeypatch):
    engine = object.__new__(PortfolioEngine)
    engine.tenant_user_id = "user-schedule"
    engine.execution_interval = 10
    engine.signal_interval = 3600
    engine.feedback_interval = 86400
    engine.health_interval = 3600
    calls = []

    async def record(name):
        calls.append(name)

    engine._run_execution = lambda: record("execution")
    engine._run_signals = lambda: record("signals")
    engine._run_watchlist_review = lambda: record("watchlist")
    engine._run_feedback = lambda: record("feedback")
    engine._run_health = lambda: record("health")
    monkeypatch.setattr(
        "portfolio.engine.claim_due_jobs",
        lambda user_id, intervals: {"execution", "health"},
    )

    result = asyncio.run(engine.run_cycle())

    assert calls == ["execution", "health"]
    assert result.state is StageExecutionState.COMPLETED
    assert result.attempted == 2
    assert result.succeeded == 2


def test_portfolio_schedule_failure_is_fail_closed_and_isolated(monkeypatch):
    engine = object.__new__(PortfolioEngine)
    engine.tenant_user_id = "user-schedule"
    engine.execution_interval = 10
    engine.signal_interval = 3600
    engine.feedback_interval = 86400
    engine.health_interval = 3600
    engine.logger = __import__("logging").getLogger("test.portfolio.schedule")
    calls = []
    engine._run_execution = lambda: calls.append("execution")
    engine._run_signals = lambda: calls.append("signals")
    engine._run_watchlist_review = lambda: calls.append("watchlist")
    engine._run_feedback = lambda: calls.append("feedback")
    engine._run_health = lambda: calls.append("health")
    monkeypatch.setattr(
        "portfolio.engine.claim_due_jobs",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("schedule unavailable")),
    )

    result = asyncio.run(engine.run_cycle())

    assert calls == []
    assert result.state is StageExecutionState.FAILED
    assert result.code == "portfolio_schedule_unavailable"
    assert result.failed == 1
    assert result.recovery_action


def test_portfolio_engine_reports_no_due_work_as_skipped(monkeypatch):
    engine = object.__new__(PortfolioEngine)
    engine.tenant_user_id = "user-schedule"
    engine.execution_interval = 10
    engine.signal_interval = 3600
    engine.feedback_interval = 86400
    engine.health_interval = 3600
    engine.logger = __import__("logging").getLogger("test.portfolio.schedule")
    monkeypatch.setattr("portfolio.engine.claim_due_jobs", lambda *_a, **_k: set())

    result = asyncio.run(engine.run_cycle())

    assert result.state is StageExecutionState.SKIPPED
    assert result.code == "portfolio_no_due_work"


def test_portfolio_engine_aggregates_due_subjob_failure(monkeypatch):
    engine = object.__new__(PortfolioEngine)
    engine.tenant_user_id = "user-schedule"
    engine.execution_interval = 10
    engine.signal_interval = 3600
    engine.feedback_interval = 86400
    engine.health_interval = 3600
    engine.logger = __import__("logging").getLogger("test.portfolio.schedule")
    engine.last_execution = datetime.now(timezone.utc)
    engine.last_health = datetime.now(timezone.utc)

    async def succeed():
        return None

    async def fail():
        raise RuntimeError("health store unavailable")

    engine._run_execution = succeed
    engine._run_health = fail
    monkeypatch.setattr(
        "portfolio.engine.claim_due_jobs",
        lambda *_a, **_k: {"execution", "health"},
    )

    result = asyncio.run(engine.run_cycle())

    assert result.state is StageExecutionState.FAILED
    assert result.attempted == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.recovery_action


def test_meta_agent_returns_typed_disabled_and_failure_outcomes(monkeypatch):
    disabled = MetaAgent(user_id="user-schedule")
    disabled.enabled = False
    disabled_result = asyncio.run(disabled.run_cycle())

    assert disabled_result.outcome.state is StageExecutionState.SKIPPED
    assert disabled_result.outcome.code == "meta_disabled"
    assert disabled_result.report is None

    failed = MetaAgent(user_id="user-schedule")
    monkeypatch.setattr(
        "meta.agent.claim_due_jobs", lambda *_a, **_k: {"meta"}
    )
    monkeypatch.setattr(
        failed,
        "_run_cycle_sync",
        lambda: (_ for _ in ()).throw(RuntimeError("analysis store unavailable")),
    )
    failed_result = asyncio.run(failed.run_cycle())

    assert failed_result.outcome.state is StageExecutionState.FAILED
    assert failed_result.outcome.code == "meta_cycle_failed"
    assert failed_result.report is None
