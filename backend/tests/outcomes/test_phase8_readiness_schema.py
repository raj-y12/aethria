from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from scripts import check_phase8_readiness as readiness


def test_required_migration_file_order_includes_materiality_digest_last(tmp_path: Path):
    migrations = tmp_path / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    for name in readiness.PHASE3_8_MIGRATIONS[:-1]:
        (migrations / name).write_text("-- present\n")

    check = readiness._migration_files_check(tmp_path)

    assert readiness.PHASE3_8_MIGRATIONS[-1] == (
        "20260720120000_materiality_digests.sql"
    )
    assert check["status"] == "failed"
    assert check["missing"] == ["20260720120000_materiality_digests.sql"]


def test_applied_migration_ledger_requires_materiality_digest_version():
    versions = {
        name.split("_", 1)[0] for name in readiness.PHASE3_8_MIGRATIONS[:-1]
    }

    check = readiness._migration_versions_check(versions)

    assert check["status"] == "failed"
    assert check["missing"] == ["20260720120000"]


def _materiality_rows():
    return [
        {
            "table_name": "evaluation_runs",
            "column_name": "evidence_materiality_digest",
            "data_type": "text",
            "udt_name": "text",
        },
        {
            "table_name": "material_change_checks",
            "column_name": "previous_materiality_digest",
            "data_type": "text",
            "udt_name": "text",
        },
        {
            "table_name": "material_change_checks",
            "column_name": "current_materiality_digest",
            "data_type": "text",
            "udt_name": "text",
        },
    ]


@pytest.mark.parametrize("missing_count", [1, 2, 3])
def test_materiality_schema_fails_when_any_required_columns_are_missing(
    missing_count,
):
    rows = _materiality_rows()[: 3 - missing_count]

    check = readiness._materiality_columns_check(rows)

    assert check["status"] == "failed"
    assert len(check["missing"]) == missing_count
    assert check["wrong_type"] == []


def test_materiality_schema_fails_on_incompatible_column_type():
    rows = _materiality_rows()
    rows[-1] = {**rows[-1], "data_type": "jsonb", "udt_name": "jsonb"}

    check = readiness._materiality_columns_check(rows)

    assert check["status"] == "failed"
    assert check["missing"] == []
    assert check["wrong_type"] == [
        {
            "column": "material_change_checks.current_materiality_digest",
            "expected": "text",
            "actual": "jsonb (jsonb)",
        }
    ]


def test_materiality_schema_passes_only_with_all_exact_text_columns():
    check = readiness._materiality_columns_check(_materiality_rows())

    assert check == {
        "name": "materiality_digest_columns",
        "status": "passed",
        "detail": "all materiality digest columns exist with compatible types",
        "missing": [],
        "wrong_type": [],
    }


@pytest.mark.asyncio
async def test_database_readiness_queries_live_columns_in_addition_to_ledger(
    monkeypatch,
):
    queries = []

    class Connection:
        async def fetch(self, query, *args):
            queries.append(query)
            if "from pg_class" in query:
                return [
                    {"table_name": table, "relrowsecurity": True}
                    for table in args[0]
                ]
            if "from pg_trigger" in query:
                return [{"tgname": name} for name in args[0]]
            if "table_name='policy_proposals'" in query:
                return []
            if "evidence_materiality_digest" in query:
                return _materiality_rows()
            if "supabase_migrations.schema_migrations" in query:
                return [
                    {"version": name.split("_", 1)[0]}
                    for name in (
                        *readiness.PHASE3_8_MIGRATIONS,
                        readiness.POLICY_UPGRADE_MIGRATION,
                    )
                ]
            raise AssertionError(f"unexpected readiness query: {query}")

        async def fetchval(self, query):
            queries.append(query)
            if "to_regclass" in query:
                return "supabase_migrations.schema_migrations"
            if "to_regprocedure" in query:
                return "upgrade_fund_policy(text,text,text,text,text,jsonb,jsonb)"
            raise AssertionError(f"unexpected readiness scalar query: {query}")

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

        async def close(self):
            return None

    async def create_pool(**_kwargs):
        return Pool()

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=create_pool))

    checks = await readiness._database_checks("postgresql://redacted")

    by_name = {check["name"]: check for check in checks}
    assert by_name["phase3_8_migrations_applied"]["status"] == "passed"
    assert by_name["materiality_digest_columns"]["status"] == "passed"
    assert by_name["policy_upgrade_migration_applied"]["status"] == "passed"
    assert by_name["policy_upgrade_rpc"]["status"] == "passed"
    assert any("data_type, udt_name" in query for query in queries)
