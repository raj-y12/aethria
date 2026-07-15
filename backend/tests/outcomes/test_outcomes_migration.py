from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715280000_channels_outcomes.sql"


def test_channel_and_outcome_schema_reuses_identity_and_evidence():
    sql = MIGRATION.read_text().lower()
    assert "create table if not exists public.import_batches" in sql
    assert "create table if not exists public.import_rows" in sql
    assert "create table if not exists public.outcome_observations" in sql
    assert "create table if not exists public.outcome_evidence_links" in sql
    assert "references public.source_observations" in sql
    assert "references public.evidence_artifacts" in sql
    assert "crm_import" in sql
    assert "alter table public.outcome_observations enable row level security" in sql


def test_outcomes_are_append_only_and_causal_interpretation_is_not_persisted():
    sql = MIGRATION.read_text().lower()
    assert "outcome_observations_append_only" in sql
    assert "causal_inference" not in sql
