from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715260000_attention_enrichment.sql"
MATERIALITY_MIGRATION = (
    Path(__file__).parents[3]
    / "supabase/migrations/20260720120000_materiality_digests.sql"
)


def test_monitoring_schema_has_budget_materiality_and_refresh_job_contract():
    sql = MIGRATION.read_text().lower()
    assert "create table if not exists public.budget_reservations" in sql
    assert "create table if not exists public.material_change_checks" in sql
    assert "evidence_refresh" in sql
    assert "next_review_at" in sql
    assert "lifecycle_reason" in sql
    assert "providers jsonb" in sql
    assert "deadline_at" in sql
    assert "alter table public.budget_reservations enable row level security" in sql


def test_materiality_digest_schema_is_distinct_from_clocked_snapshot_hash():
    sql = MATERIALITY_MIGRATION.read_text().lower()

    assert "evidence_materiality_digest" in sql
    assert "previous_materiality_digest" in sql
    assert "current_materiality_digest" in sql
