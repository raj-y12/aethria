from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260722090000_authority_control.sql"
)


def _sql() -> str:
    return MIGRATION.read_text().lower()


def test_authority_migration_declares_closed_rollout_modes_and_order_metadata():
    sql = _sql()
    for mode in (
        "legacy",
        "shadow",
        "backfill",
        "canonical_write",
        "canonical_read",
    ):
        assert f"'{mode}'" in sql
    assert "legal rollout order: legacy -> shadow -> backfill -> canonical_write -> canonical_read" in sql


def test_authority_migration_adds_optimistically_locked_workflow_columns():
    sql = _sql()
    assert "add column if not exists workflow_state text not null default 'admitted'" in sql
    assert "alter column workflow_state drop default" in sql
    assert "add column if not exists workflow_version integer not null default 0" in sql
    assert "add column if not exists block_code text" in sql
    assert "add column if not exists block_detail text" in sql
    assert "add column if not exists block_recovery text" in sql
    assert "add column if not exists last_transition_id uuid" in sql
    assert "workflow_state in (" in sql
    for state in (
        "admitted",
        "identity_review",
        "triage_pending",
        "triaged_light",
        "deep_review_pending",
        "evidence_active",
        "evaluation_pending",
        "ruling_pending",
        "monitoring",
        "completed",
        "blocked",
        "archived",
    ):
        assert f"'{state}'" in sql
    assert "workflow_state <> 'blocked'" in sql
    assert "block_code is not null" in sql
    assert "block_detail is not null" in sql
    assert "block_recovery is not null" in sql


def test_authority_migration_creates_tenant_rollouts_and_idempotent_receipts():
    sql = _sql()
    assert "create table if not exists public.tenant_authority_rollouts" in sql
    for column in (
        "user_id text primary key",
        "mode text not null",
        "version integer not null",
        "activated_at timestamptz",
        "activated_by text",
        "snapshot_id text",
        "last_reconciliation_status text",
        "kill_switch boolean not null",
        "created_at timestamptz not null",
        "updated_at timestamptz not null",
    ):
        assert column in sql
    assert "create table if not exists public.authority_projection_receipts" in sql
    assert "unique (user_id, event_id, consumer)" in sql
    assert "tenant_authority_rollouts_tenant_mode_idx" in sql
    assert "opportunities_tenant_workflow_state_idx" in sql


def test_authority_migration_is_rls_protected_and_service_role_only():
    sql = _sql()
    for table in (
        "tenant_authority_rollouts",
        "authority_projection_receipts",
        "opportunities",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from anon, authenticated" in sql
        assert f"grant select, insert, update, delete on table public.{table} to service_role" in sql
        assert f"{table}_service_role_all" in sql
