"""Security contract for the authoritative durable lookup outcome table."""

from pathlib import Path

from scripts import check_phase8_readiness as readiness


MIGRATION = (
    Path(__file__).parents[3]
    / "supabase/migrations/20260721150000_lookup_job_outcomes_rls.sql"
)


def test_lookup_outcomes_security_migration_is_service_role_only() -> None:
    sql = MIGRATION.read_text().lower()

    assert "alter table public.lookup_job_outcomes enable row level security" in sql
    assert "create policy lookup_job_outcomes_service_role_all" in sql
    assert "for all" in sql
    assert "to service_role" in sql
    assert "using (true)" in sql
    assert "with check (true)" in sql
    assert (
        "revoke all on table public.lookup_job_outcomes from public, anon, authenticated"
        in sql
    )
    assert (
        "grant select, insert, update, delete on table public.lookup_job_outcomes to service_role"
        in sql
    )
    assert "revoke all on table public.lookup_job_outcomes from service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql


def test_lookup_outcomes_security_migration_is_required_by_readiness() -> None:
    assert readiness.LOOKUP_OUTCOMES_SECURITY_MIGRATION == MIGRATION.name
    assert readiness._lookup_outcomes_security_migration_file_check()["status"] == (
        "passed"
    )
    check = readiness._lookup_outcomes_security_version_check(set())
    assert check["status"] == "failed"
    assert check["missing"] == ["20260721150000"]


def test_lookup_outcomes_live_security_requires_exact_policy_and_grants() -> None:
    passed = readiness._lookup_outcomes_security_check(
        table_rows=[{"table_name": "lookup_job_outcomes", "relrowsecurity": True}],
        policy_rows=[
            {
                "policyname": "lookup_job_outcomes_service_role_all",
                "roles": ["service_role"],
                "cmd": "ALL",
            }
        ],
        grant_rows=[
            {"grantee": "service_role", "privilege_type": privilege}
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
        ],
    )

    assert passed["status"] == "passed"
    assert passed["client_grants"] == []

    client_leak = readiness._lookup_outcomes_security_check(
        table_rows=[{"table_name": "lookup_job_outcomes", "relrowsecurity": True}],
        policy_rows=[
            {
                "policyname": "lookup_job_outcomes_service_role_all",
                "roles": ["service_role"],
                "cmd": "ALL",
            }
        ],
        grant_rows=[
            {"grantee": "service_role", "privilege_type": privilege}
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
        ]
        + [{"grantee": "authenticated", "privilege_type": "SELECT"}],
    )
    missing_policy = readiness._lookup_outcomes_security_check(
        table_rows=[{"table_name": "lookup_job_outcomes", "relrowsecurity": True}],
        policy_rows=[],
        grant_rows=[
            {"grantee": "service_role", "privilege_type": privilege}
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
        ],
    )

    assert client_leak["status"] == "failed"
    assert client_leak["client_grants"] == ["authenticated:SELECT"]
    assert missing_policy["status"] == "failed"
    assert missing_policy["policy_ok"] is False
