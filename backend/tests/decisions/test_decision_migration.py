from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715250000_rulings_and_actions.sql"
TRANSITION_MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260726120000_ruling_context_and_investment_transition.sql"


def test_ruling_action_schema_is_append_only_and_approval_gated():
    sql = MIGRATION.read_text().lower()
    for table in ("human_rulings", "override_signals", "workflow_actions"):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "prevent_ruling_mutation" in sql
    assert "requires_approval" in sql
    assert "approved_by" in sql
    assert "current_ruling_id" in sql


def test_investment_transition_migration_preserves_history_and_adds_context():
    sql = TRANSITION_MIGRATION.read_text().lower()
    assert "add column if not exists ruling_context" in sql
    assert "investment_transition" in sql
    assert "historical invest rows remain compatible" in sql
    assert "create index if not exists human_rulings_investment_transition_idx" in sql


def test_ruling_interpretation_migration_is_append_only_and_tenant_scoped():
    path = Path(__file__).parents[3] / "supabase/migrations/20260809000001_ruling_interpretations.sql"
    sql = path.read_text().lower()
    assert "create table if not exists public.ruling_interpretations" in sql
    assert "supersedes_interpretation_id" in sql
    assert "prevent_ruling_interpretation_mutation" in sql
    assert "alter table public.ruling_interpretations enable row level security" in sql
    assert "user_id, ruling_id, version" in sql
