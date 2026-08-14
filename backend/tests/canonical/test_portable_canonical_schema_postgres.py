import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for canonical schema PostgreSQL contracts",
)

CANONICAL_TABLES = {
    "budget_reservations",
    "canonical_portfolio_positions",
    "claim_corrections",
    "claim_evidence_links",
    "claims",
    "criterion_assessments",
    "evaluation_runs",
    "evidence_artifacts",
    "evidence_items",
    "evidence_plans",
    "human_rulings",
    "import_batches",
    "import_rows",
    "material_change_checks",
    "outcome_evidence_links",
    "outcome_observations",
    "override_signals",
    "recommendations",
    "ruling_interpretations",
    "triage_assessments",
    "workflow_actions",
}


@pytest.mark.asyncio
async def test_portable_canonical_schema_bootstraps_all_scoped_tables():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        rows = await connection.fetch(
            """
            select table_name
            from information_schema.tables
            where table_schema='public' and table_name = any($1::text[])
            """,
            list(CANONICAL_TABLES),
        )
        assert {row["table_name"] for row in rows} == CANONICAL_TABLES

        nullable = await connection.fetchval(
            """
            select is_nullable
            from information_schema.columns
            where table_schema='public'
              and table_name='governed_policy_versions'
              and column_name='publication_source'
            """
        )
        assert nullable == "NO"
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_portable_canonical_schema_preserves_tenant_fks_and_immutability():
    import asyncpg

    connection = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    try:
        constraints = await connection.fetch(
            """
            select distinct tc.constraint_name
            from information_schema.table_constraints tc
            where tc.table_schema='public'
              and tc.constraint_type='FOREIGN KEY'
              and tc.constraint_name = any($1::text[])
            """,
            [
                "evidence_items_user_id_artifact_id_fkey",
                "criterion_assessments_user_id_evaluation_id_fkey",
                "human_rulings_user_id_opportunity_id_fkey",
                "outcome_evidence_links_user_id_outcome_observation_id_fkey",
            ],
        )
        assert {row["constraint_name"] for row in constraints} == {
            "evidence_items_user_id_artifact_id_fkey",
            "criterion_assessments_user_id_evaluation_id_fkey",
            "human_rulings_user_id_opportunity_id_fkey",
            "outcome_evidence_links_user_id_outcome_observation_id_fkey",
        }

        triggers = await connection.fetch(
            """
            select trigger_name
            from information_schema.triggers
            where trigger_schema='public'
              and trigger_name = any($1::text[])
            """,
            [
                "evaluation_runs_immutable",
                "human_rulings_append_only",
                "outcome_observations_append_only",
            ],
        )
        assert {row["trigger_name"] for row in triggers} == {
            "evaluation_runs_immutable",
            "human_rulings_append_only",
            "outcome_observations_append_only",
        }
    finally:
        await connection.close()


def test_new_portable_migrations_contain_no_supabase_security_objects():
    migration_dir = Path(__file__).parents[3] / "db" / "migrations"
    scoped = sorted(migration_dir.glob("*.sql"))
    sql = "\n".join(path.read_text(encoding="utf-8").lower() for path in scoped)
    for forbidden in (
        "auth.uid",
        "auth.jwt",
        "auth.role",
        "service_role",
        "role anon",
        "role authenticated",
        "supabase_migrations",
    ):
        assert forbidden not in sql
