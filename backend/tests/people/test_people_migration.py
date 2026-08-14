from pathlib import Path


def test_people_migration_is_tenant_scoped_and_temporal():
    sql = Path("supabase/migrations/20260812000003_canonical_people.sql").read_text()
    lowered = sql.lower()
    for table in ("people", "person_identifiers", "company_people", "person_history"):
        assert f"create table if not exists public.{table}" in lowered
        assert "user_id" in sql
        assert table in sql
    assert "valid_from" in sql and "valid_to" in sql
    assert "row level security" in sql.lower()


def test_provider_neutral_people_migration_is_kept_separate_from_supabase_security():
    sql = Path("db/migrations/20260813000001_canonical_people.sql").read_text()
    lowered = sql.lower()
    assert "create table if not exists public.people" in lowered
    assert "row level security" not in lowered
    assert "service_role" not in lowered
    assert "auth.uid" not in lowered
