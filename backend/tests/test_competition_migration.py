from pathlib import Path


def test_competition_relationship_migration_is_minimal_and_tenant_scoped():
    sql = Path("supabase/migrations/20260812000005_canonical_competition.sql").read_text().lower()
    assert "create table if not exists public.company_competitors" in sql
    for value in ("user_id", "target_company_id", "competitor_company_id", "relationship_type", "source_claim_id", "valid_from", "valid_to"):
        assert value in sql
    assert "row level security" in sql
    assert "unique (user_id, target_company_id, competitor_company_id, relationship_type)" in sql
