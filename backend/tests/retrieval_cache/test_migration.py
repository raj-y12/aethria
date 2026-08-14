from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "supabase/migrations/20260812000001_durable_retrieval_cache.sql"


def test_retrieval_cache_migration_is_tenant_scoped_and_versioned():
    sql = MIGRATION.read_text().lower()
    for table in (
        "retrieval_cache_entries",
        "retrieval_cache_content_versions",
        "retrieval_cache_observations",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"user_id text not null" in sql
    assert "unique (user_id, content_hash, access_class)" in sql
    assert "current_setting('app.user_id', true)" in sql
