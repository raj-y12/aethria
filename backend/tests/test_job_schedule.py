import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from meta.agent import MetaAgent
from portfolio.engine import PortfolioEngine
from utils import job_schedule


def test_claim_due_jobs_persists_intervals_and_isolates_tenants(monkeypatch):
    calls = []

    class Request:
        def __init__(self, rows):
            self.rows = rows

        def execute(self):
            return SimpleNamespace(data=self.rows)

    class Client:
        def rpc(self, name, params):
            calls.append((name, params))
            return Request([{"job_name": "signals"}])

    monkeypatch.setattr(job_schedule, "get_service_client", Client)
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    intervals = {"meta": 86400, "signals": 3600}

    assert job_schedule.claim_due_jobs("user-a", intervals, now=now) == {"signals"}
    assert calls == [
        (
            "claim_due_agent_jobs",
            {
                "p_user_id": "user-a",
                "p_intervals": {"meta": 86400, "signals": 3600},
                "p_now": "2026-07-14T12:00:00Z",
            },
        )
    ]


def test_claim_due_jobs_fails_closed_on_rpc_error(monkeypatch):
    class Client:
        def rpc(self, name, params):
            raise RuntimeError("schedule store unavailable")

    monkeypatch.setattr(job_schedule, "get_service_client", Client)

    with pytest.raises(RuntimeError, match="schedule store unavailable"):
        job_schedule.claim_due_jobs("user-a", {"meta": 86400})


def test_schedule_migration_claim_is_transactional_and_service_role_only():
    sql = (
        Path(__file__).parents[2]
        / "supabase/migrations/20260714192632_agent_job_schedules.sql"
    ).read_text().lower()

    assert "create or replace function public.claim_due_agent_jobs" in sql
    assert "on conflict on constraint agent_job_schedules_pkey do update" in sql
    assert "on conflict (user_id, job_name)" not in sql
    assert "where agent_job_schedules.last_claimed_at" in sql
    assert "returning agent_job_schedules.job_name" in sql
    assert "(select auth.jwt()) ->> 'sub' = user_id" in sql
    assert "revoke all on function public.claim_due_agent_jobs" in sql
    assert "grant execute on function public.claim_due_agent_jobs" in sql


def test_meta_agent_skips_automatic_cycle_until_due(monkeypatch):
    agent = MetaAgent(user_id="user-schedule")
    ran = []
    monkeypatch.setattr("meta.agent.claim_due_jobs", lambda *a, **k: set())
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: ran.append(True) or {"cycle_number": 1})

    report = asyncio.run(agent.run_cycle())

    assert report is None
    assert ran == []


def test_meta_agent_manual_cycle_bypasses_schedule(monkeypatch):
    agent = MetaAgent(user_id="user-schedule")
    claims = []
    monkeypatch.setattr(
        "meta.agent.claim_due_jobs",
        lambda user_id, intervals: claims.append((user_id, intervals)) or {"meta"},
    )
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: {"cycle_number": 7})

    assert asyncio.run(agent.run_cycle(force=True)) == {"cycle_number": 7}
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

    asyncio.run(engine.run_cycle())

    assert calls == ["execution", "health"]


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

    asyncio.run(engine.run_cycle())

    assert calls == []
