from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260715210000_canonical_identity.sql"
)


def _sql():
    return MIGRATION.read_text().lower()


def test_identity_migration_defines_all_authoritative_tables():
    sql = _sql()
    for table in (
        "companies",
        "source_observations",
        "company_identifiers",
        "company_aliases",
        "opportunities",
        "identity_resolution_cases",
    ):
        assert f"create table if not exists public.{table}" in sql


def test_identity_migration_scopes_identity_and_idempotency_to_tenant():
    sql = _sql()
    assert "unique (user_id, company_id)" in sql
    assert "unique (user_id, observation_id)" in sql
    assert "unique (user_id, opportunity_id)" in sql
    assert "on public.company_identifiers (user_id, identifier_type, normalized_value)" in sql
    assert "where verification_status = 'verified'" in sql
    assert "source_observations_external_event_idx" in sql


def test_identity_migration_has_case_and_projection_reconciliation_indexes():
    sql = _sql()
    assert "identity_resolution_cases_open_idx" in sql
    assert "opportunities_legacy_projection_idx" in sql
    assert "source_observations_company_idx" in sql


def test_identity_migration_enables_rls_and_denies_frontend_roles():
    sql = _sql()
    for table in (
        "companies",
        "source_observations",
        "company_identifiers",
        "company_aliases",
        "opportunities",
        "identity_resolution_cases",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from anon, authenticated" in sql


def test_identity_migration_keeps_later_phase_pointers_nullable_and_unbound():
    sql = _sql()
    assert "current_evaluation_id uuid" in sql
    assert "current_recommendation_id uuid" in sql
    assert "current_ruling_id uuid" in sql
    assert "references public.evaluation_runs" not in sql


def test_review_fix_migration_adds_stable_observation_opportunity_link():
    migration = (
        Path(__file__).resolve().parents[3]
        / "supabase"
        / "migrations"
        / "20260716090000_review_fixes.sql"
    )
    sql = migration.read_text().lower()

    assert "add column if not exists opportunity_id uuid" in sql
    assert "source_observations_opportunity_fk" in sql
    assert "foreign key (user_id, opportunity_id)" in sql
    assert "references public.opportunities (user_id, opportunity_id)" in sql
