from pathlib import Path


MIGRATION = Path(__file__).parents[3] / "db/migrations/20260811000020_fund_thesis_reads.sql"


def test_thesis_migration_is_provider_neutral_and_read_contract_only():
    sql = MIGRATION.read_text()
    lowered = sql.lower()

    for forbidden in (
        "auth.uid",
        "auth.jwt",
        "auth.role",
        "service_role",
        "supabase_migrations",
        "fund_policy_versions",
        "upgrade_fund_policy",
    ):
        assert forbidden not in lowered

    assert "create table" in lowered
    assert "references public.fund_thesis_versions (user_id, id)" in lowered
    assert "create unique index" in lowered
    assert "where is_active" in lowered
