from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715250000_rulings_and_actions.sql"


def test_ruling_action_schema_is_append_only_and_approval_gated():
    sql = MIGRATION.read_text().lower()
    for table in ("human_rulings", "override_signals", "workflow_actions"):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "prevent_ruling_mutation" in sql
    assert "requires_approval" in sql
    assert "approved_by" in sql
    assert "current_ruling_id" in sql
