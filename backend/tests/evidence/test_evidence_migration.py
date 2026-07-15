from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260715230000_evidence_claim_ledger.sql"


def test_evidence_migration_has_provenance_claims_links_and_rls():
    sql = MIGRATION.read_text().lower()
    for table in (
        "evidence_artifacts",
        "evidence_items",
        "claims",
        "claim_evidence_links",
        "evidence_plans",
        "claim_corrections",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
    assert "content_hash" in sql
    assert "assertion_class" in sql
    assert "supersedes_claim_id" in sql
    assert "relationship" in sql
    assert "prompt_injection_detected" in sql
