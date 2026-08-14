"""Apply Aethria's provider-neutral migrations to a PostgreSQL database."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.migration_runner import (
    _ensure_ledger,
    _tables_created_by,
    discover_migrations,
    legacy_supabase_baseline,
    migrate,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO_ROOT / "db" / "migrations"
SUPABASE_OVERLAYS = tuple(
    REPO_ROOT / "supabase" / "migrations" / filename
    for filename in (
        "20260804000001_security_limits_privilege_hardening.sql",
        "20260812000001_durable_retrieval_cache.sql",
        "20260812000002_evaluation_judgment_audit.sql",
        "20260812000003_canonical_people.sql",
        "20260812000004_external_entity_mappings.sql",
        "20260812000005_canonical_competition.sql",
        "20260814000006_startup_id_aliases.sql",
        "20260814000007_rls_auto_enable_privilege_hardening.sql",
    )
)


async def _adopt_legacy_supabase_schema(pool: asyncpg.Pool) -> bool:
    """Create the app ledger without replaying Supabase's old DDL.

    The live project predates the portable migration ledger. Replaying the
    equivalent migrations would collide with existing constraints, so we
    record only the verified legacy-equivalent versions and leave genuinely
    missing/additive versions for the normal runner.
    """

    migrations = discover_migrations(MIGRATIONS)
    baseline = legacy_supabase_baseline(migrations)
    expected_tables = sorted(_tables_created_by(baseline))
    async with pool.acquire() as connection:
        async with connection.transaction():
            if not await connection.fetchval(
                "select to_regclass('supabase_migrations.schema_migrations')::text"
            ):
                return False
            if await connection.fetchval(
                "select to_regclass('app_migrations.schema_migrations')::text"
            ):
                return False

            existing_tables = {
                str(row["table_name"])
                for row in await connection.fetch(
                    """
                    select table_name
                      from information_schema.tables
                     where table_schema = 'public'
                       and table_name = any($1::text[])
                    """,
                    expected_tables,
                )
            }
            missing_tables = sorted(set(expected_tables) - existing_tables)
            if missing_tables:
                raise RuntimeError(
                    "refusing legacy Supabase adoption; expected existing tables "
                    f"are missing: {', '.join(missing_tables)}"
                )
            if not await connection.fetchval(
                """
                select exists (
                    select 1
                      from pg_indexes
                     where schemaname = 'public'
                       and tablename = 'startups'
                       and indexname = 'startups_user_startup_id_idx'
                       and indexdef like '%UNIQUE INDEX%'
                )
                """
            ):
                raise RuntimeError(
                    "refusing legacy Supabase adoption; startups tenant identity "
                    "unique index is missing"
                )

            await _ensure_ledger(connection, "app_migrations")
            for migration in baseline:
                await connection.execute(
                    """
                    insert into app_migrations.schema_migrations (version, name)
                    values ($1, $2)
                    on conflict (version) do nothing
                    """,
                    migration.version,
                    migration.name,
                )
    return True


async def _migrate(
    database_url: str,
    *,
    apply_supabase_overlays: bool = False,
) -> tuple[list[str], bool]:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        if apply_supabase_overlays:
            await _adopt_legacy_supabase_schema(pool)
        applied = await migrate(pool, MIGRATIONS)
        overlay_applied = False
        if apply_supabase_overlays:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    for overlay in SUPABASE_OVERLAYS:
                        if not overlay.exists():
                            raise FileNotFoundError(str(overlay))
                        await connection.execute(overlay.read_text(encoding="utf-8"))
            overlay_applied = True
        return applied, overlay_applied
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=(
            os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL")
            or os.getenv("TEST_DATABASE_URL", "")
        ),
        help=(
            "PostgreSQL DSN; defaults to DATABASE_URL, then SUPABASE_DB_URL, "
            "then TEST_DATABASE_URL"
        ),
    )
    parser.add_argument(
        "--supabase-overlays",
        action="store_true",
        help=(
            "Apply the optional Supabase role/RLS overlays after the portable "
            "migrations. Use only for a Supabase database."
        ),
    )
    args = parser.parse_args()
    if not str(args.database_url).strip():
        parser.error("--database-url or TEST_DATABASE_URL is required")
    applied, overlay_applied = asyncio.run(
        _migrate(
            str(args.database_url).strip(),
            apply_supabase_overlays=args.supabase_overlays,
        )
    )
    print("Applied migrations:" if applied else "No new migrations.")
    for version in applied:
        print(version)
    if overlay_applied:
        print("Applied Supabase security overlays.")


if __name__ == "__main__":
    main()
