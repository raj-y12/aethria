from pathlib import Path


MIGRATION = (
    Path(__file__).parents[3]
    / "supabase/migrations/20260715193000_durable_agent_jobs.sql"
)


def test_durable_job_migration_defines_all_transactional_tables():
    sql = MIGRATION.read_text().lower()

    assert "create table if not exists public.agent_jobs" in sql
    assert "create table if not exists public.agent_job_checkpoints" in sql
    assert "create table if not exists public.domain_outbox" in sql
    assert sql.count("user_id text not null") >= 3
    assert "payload jsonb not null" in sql
    assert "lease_expires_at timestamptz" in sql
    assert "heartbeat_at timestamptz" in sql
    assert "next_attempt_at timestamptz not null" in sql
    assert "attempts integer not null" in sql
    assert "max_attempts integer not null" in sql


def test_durable_job_migration_has_idempotency_and_claim_indexes():
    sql = MIGRATION.read_text().lower()

    assert "unique (user_id, idempotency_key)" in sql
    assert "unique (user_id, job_id, stage, attempt, status)" in sql
    assert "event_id uuid primary key" in sql
    assert "agent_jobs_claim_idx" in sql
    assert "status, next_attempt_at, priority desc, created_at" in sql
    assert "agent_jobs_lease_recovery_idx" in sql
    assert "status, lease_expires_at" in sql
    assert "domain_outbox_unpublished_idx" in sql
    assert "where published_at is null" in sql


def test_durable_job_migration_constrains_state_and_enables_rls():
    sql = MIGRATION.read_text().lower()

    for status in (
        "queued",
        "running",
        "retry_wait",
        "blocked",
        "succeeded",
        "failed",
        "dead_letter",
        "cancelled",
    ):
        assert f"'{status}'" in sql
    assert "'pipeline_cycle'" in sql
    assert "'company_lookup'" in sql
    assert "alter table public.agent_jobs enable row level security" in sql
    assert "alter table public.agent_job_checkpoints enable row level security" in sql
    assert "alter table public.domain_outbox enable row level security" in sql
    assert sql.count("to service_role") >= 3
    assert "revoke all on table public.agent_jobs from anon, authenticated" in sql
    assert "grant select, insert, update, delete on table public.agent_jobs to service_role" in sql


def test_durable_job_migration_updates_timestamps_without_editing_old_migrations():
    sql = MIGRATION.read_text().lower()

    assert "create or replace function public.touch_durable_job_updated_at" in sql
    assert "before update on public.agent_jobs" in sql
    assert "before update on public.agent_job_checkpoints" in sql
