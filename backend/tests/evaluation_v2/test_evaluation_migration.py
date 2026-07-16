from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715240000_immutable_evaluations.sql"


def test_evaluation_schema_is_versioned_immutable_and_tenant_scoped():
    sql = MIGRATION.read_text().lower()
    for table in ("evaluation_runs", "criterion_assessments", "recommendations"):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "claim_snapshot jsonb not null" in sql
    assert "evidence_snapshot_hash" in sql
    assert "policy_version_id" in sql
    assert "prevent_completed_evaluation_mutation" in sql
    assert "current_recommendation_id" in sql
