"""Small, provider-neutral migration runner for direct PostgreSQL.

The historical ``supabase/migrations`` directory is intentionally not used by
this runner.  Portable schema migrations live under ``db/`` and are recorded
in the application-owned ``app_migrations`` schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_MIGRATION_NAME = re.compile(r"^(?P<version>\d{14})_(?P<name>[a-z0-9][a-z0-9_-]*)\.sql$")
_PUBLIC_TABLE_MIGRATION = re.compile(
    r"create\s+table\s+if\s+not\s+exists\s+public\.(?P<table>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)

# The production Supabase project already applied its historical migration
# chain. These portable migrations are equivalent schema coverage, except for
# the explicitly re-applied additive migrations below. Keep this list narrow:
# it is only used when adopting a legacy Supabase database that has no
# application-owned ledger yet.
LEGACY_SUPABASE_BASELINE_CUTOFF = "20260812000000"
LEGACY_SUPABASE_REAPPLY_VERSIONS = frozenset(
    {
        "20260811000019",  # missing from the current Supabase schema
        "20260813000001",  # canonical people tables
        "20260814000001",  # retrieval/interoperability tables
        "20260814000002",  # legacy-schema compatibility constraints
    }
)


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path


@dataclass(frozen=True)
class MigrationHeadStatus:
    """Read-only comparison between repository migrations and a database ledger."""

    expected_versions: tuple[str, ...]
    applied_versions: tuple[str, ...]
    ledger_exists: bool

    @property
    def missing_versions(self) -> tuple[str, ...]:
        applied = set(self.applied_versions)
        return tuple(version for version in self.expected_versions if version not in applied)

    @property
    def ready(self) -> bool:
        return self.ledger_exists and not self.missing_versions

    @property
    def expected_head(self) -> str | None:
        return self.expected_versions[-1] if self.expected_versions else None

    @property
    def applied_head(self) -> str | None:
        return self.applied_versions[-1] if self.applied_versions else None


def discover_migrations(directory: Path) -> list[Migration]:
    """Return timestamped SQL migrations in deterministic order."""

    migrations: list[Migration] = []
    seen_versions: set[str] = set()
    for path in sorted(directory.glob("*.sql")):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(
                f"invalid migration filename {path.name!r}; expected YYYYMMDDHHMMSS_name.sql"
            )
        version = match.group("version")
        if version in seen_versions:
            raise ValueError(f"duplicate migration version: {version}")
        seen_versions.add(version)
        migrations.append(Migration(version, match.group("name"), path))
    return sorted(migrations, key=lambda migration: migration.version)


def legacy_supabase_baseline(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    """Return the portable versions already represented by legacy Supabase.

    This is intentionally an explicit adoption boundary, not a general
    migration bypass. The current Supabase schema has the historical
    canonical tables and constraints, while the versions returned here are
    the compatible portion of that schema. Missing/additive versions remain
    in the normal migration stream.
    """

    return tuple(
        migration
        for migration in migrations
        if migration.version <= LEGACY_SUPABASE_BASELINE_CUTOFF
        and migration.version not in LEGACY_SUPABASE_REAPPLY_VERSIONS
    )


def _tables_created_by(migrations: Iterable[Migration]) -> set[str]:
    tables: set[str] = set()
    for migration in migrations:
        tables.update(
            match.group("table")
            for match in _PUBLIC_TABLE_MIGRATION.finditer(
                migration.path.read_text(encoding="utf-8")
            )
        )
    return tables


async def _ensure_ledger(connection: Any, ledger_schema: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", ledger_schema):
        raise ValueError(f"invalid migration ledger schema: {ledger_schema!r}")
    await connection.execute(f"create schema if not exists {ledger_schema}")
    await connection.execute(
        f"""
        create table if not exists {ledger_schema}.schema_migrations (
            version text primary key,
            name text not null,
            applied_at timestamptz not null default now()
        )
        """
    )


def _versions(rows: Iterable[Any]) -> set[str]:
    return {str(row["version"]) for row in rows}


async def inspect_migration_head(
    pool: Any,
    directory: Path,
    *,
    ledger_schema: str = "app_migrations",
) -> MigrationHeadStatus:
    """Compare the application migration head with an existing ledger.

    This performs no DDL and never consults Supabase's historical migration
    schema. Callers can use it as a readiness gate before serving database work.
    """

    migrations = discover_migrations(directory)
    expected = tuple(migration.version for migration in migrations)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", ledger_schema):
        raise ValueError(f"invalid migration ledger schema: {ledger_schema!r}")
    async with pool.acquire() as connection:
        ledger_exists = bool(
            await connection.fetchval(
                "select to_regclass($1)::text",
                f"{ledger_schema}.schema_migrations",
            )
        )
        applied_rows = (
            await connection.fetch(
                f"select version from {ledger_schema}.schema_migrations order by version"
            )
            if ledger_exists
            else []
        )
    applied = tuple(sorted(_versions(applied_rows)))
    return MigrationHeadStatus(expected, applied, ledger_exists)


async def migrate(
    pool: Any,
    directory: Path,
    *,
    ledger_schema: str = "app_migrations",
) -> list[str]:
    """Apply unapplied migrations and return their versions in apply order."""

    migrations = discover_migrations(directory)
    applied_now: list[str] = []
    async with pool.acquire() as connection:
        async with connection.transaction():
            await _ensure_ledger(connection, ledger_schema)
            rows = await connection.fetch(
                f"select version from {ledger_schema}.schema_migrations order by version"
            )
            applied = _versions(rows)
            for migration in migrations:
                if migration.version in applied:
                    continue
                await connection.execute(migration.path.read_text(encoding="utf-8"))
                await connection.execute(
                    f"insert into {ledger_schema}.schema_migrations (version, name) values ($1, $2)",
                    migration.version,
                    migration.name,
                )
                applied_now.append(migration.version)
    return applied_now
