from pathlib import Path

import pytest

from db.migration_runner import (
    Migration,
    discover_migrations,
    inspect_migration_head,
    legacy_supabase_baseline,
    migrate,
)


def test_discover_migrations_is_timestamp_ordered_and_rejects_duplicate_versions(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260102000000_later.sql").write_text("select 2;", encoding="utf-8")
    (migrations / "20260101000000_earlier.sql").write_text("select 1;", encoding="utf-8")

    discovered = discover_migrations(migrations)

    assert [migration.version for migration in discovered] == [
        "20260101000000",
        "20260102000000",
    ]

    (migrations / "20260101000000_duplicate.sql").write_text("select 3;", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate migration version"):
        discover_migrations(migrations)


def test_legacy_supabase_baseline_leaves_missing_additive_versions_unapplied(
    tmp_path: Path,
):
    migrations = []
    for filename in (
        "20260811000018_existing.sql",
        "20260811000019_missing.sql",
        "20260811000020_existing.sql",
        "20260812000000_existing.sql",
        "20260813000001_missing.sql",
        "20260814000001_missing.sql",
        "20260814000002_compatibility.sql",
    ):
        path = tmp_path / filename
        path.write_text("select 1;", encoding="utf-8")
        migrations.append(Migration(filename[:14], filename[15:-4], path))

    baseline = legacy_supabase_baseline(migrations)

    assert [migration.version for migration in baseline] == [
        "20260811000018",
        "20260811000020",
        "20260812000000",
    ]


def test_startups_read_contract_upgrades_an_existing_legacy_table_before_indexing():
    migration = (
        Path(__file__).parents[3]
        / "db"
        / "migrations"
        / "20260811000018_startups_read_contract.sql"
    ).read_text(encoding="utf-8").lower()

    alter_start = migration.index("alter table public.startups")
    index_start = migration.index("create unique index if not exists startups_user_normalized_display_name_uidx")
    assert alter_start < index_start
    for column in (
        "display_name",
        "list_one_line",
        "list_confidence",
        "list_score",
        "partner_decision",
        "list_resolution_status",
    ):
        assert f"add column if not exists {column}" in migration


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


class _Connection:
    def __init__(self, applied=None, ledger_exists=False):
        self.applied = set(applied or ())
        self.ledger_exists = ledger_exists
        self.executed = []

    def transaction(self):
        return _Transaction()

    async def execute(self, sql, *args):
        self.executed.append((sql, args))

    async def fetch(self, sql):
        return [{"version": version} for version in sorted(self.applied)]

    async def fetchval(self, sql, *args):
        return "app_migrations.schema_migrations" if self.ledger_exists else None


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_exc):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_migrate_creates_ledger_and_applies_only_unapplied_files(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_first.sql").write_text("create table first;", encoding="utf-8")
    (migrations / "20260102000000_second.sql").write_text("create table second;", encoding="utf-8")
    connection = _Connection(applied={"20260101000000"}, ledger_exists=True)

    applied = await migrate(_Pool(connection), migrations)

    assert applied == ["20260102000000"]
    statements = [sql for sql, _args in connection.executed]
    assert any("create schema if not exists app_migrations" in sql for sql in statements)
    assert any("create table if not exists app_migrations.schema_migrations" in sql for sql in statements)
    assert "create table second;" in statements
    assert "create table first;" not in statements


@pytest.mark.asyncio
async def test_inspect_migration_head_is_read_only_and_reports_missing_versions(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_first.sql").write_text("select 1;", encoding="utf-8")
    (migrations / "20260102000000_second.sql").write_text("select 2;", encoding="utf-8")
    connection = _Connection(applied={"20260101000000"}, ledger_exists=True)

    status = await inspect_migration_head(_Pool(connection), migrations)

    assert status.ready is False
    assert status.expected_head == "20260102000000"
    assert status.applied_head == "20260101000000"
    assert status.missing_versions == ("20260102000000",)
    assert connection.executed == []
