"""Verify the preserved local production snapshot without changing it."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "db" / "snapshots" / "aethria_prod_snapshot_manifest.json"
SNAPSHOT_DATABASE_NAME = "aethria_prod_snapshot"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def collect_snapshot_facts(connection: asyncpg.Connection, table_names: list[str]) -> dict[str, Any]:
    """Collect only the immutable identity, ledger, counts, and time bounds."""
    database = await connection.fetchval("select current_database()")
    migration_head = await connection.fetchval(
        "select max(version) from app_migrations.schema_migrations"
    )
    table_counts: dict[str, int] = {}
    for table_name in table_names:
        if not table_name.replace("_", "").isalnum() or not table_name[0].isalpha():
            raise ValueError(f"invalid manifest table name: {table_name!r}")
        exists = await connection.fetchval(
            "select to_regclass($1)::text", f"public.{table_name}"
        )
        if exists is None:
            raise RuntimeError(f"manifest table is missing: public.{table_name}")
        table_counts[table_name] = int(
            await connection.fetchval(f"select count(*) from public.{table_name}")
        )
    timestamps = await connection.fetchrow(
        """
        select min(created_at) as created_min,
               max(created_at) as created_max,
               min(updated_at) as updated_min,
               max(updated_at) as updated_max
          from public.startups
        """
    )
    return {
        "database": str(database),
        "migration_head": str(migration_head) if migration_head is not None else None,
        "table_counts": table_counts,
        "startup_created_at": {
            "min": _iso(timestamps["created_min"]),
            "max": _iso(timestamps["created_max"]),
        },
        "startup_updated_at": {
            "min": _iso(timestamps["updated_min"]),
            "max": _iso(timestamps["updated_max"]),
        },
    }


def validate_snapshot_facts(facts: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """Return named drift errors; an empty list means the snapshot matches."""
    errors: list[str] = []
    if facts.get("database") != manifest.get("database"):
        errors.append(
            f"database expected {manifest.get('database')}, found {facts.get('database')}"
        )
    if facts.get("migration_head") != manifest.get("migration_head"):
        errors.append(
            "migration_head expected "
            f"{manifest.get('migration_head')}, found {facts.get('migration_head')}"
        )
    expected_counts = manifest.get("table_counts") or {}
    actual_counts = facts.get("table_counts") or {}
    for table_name, expected in expected_counts.items():
        actual = actual_counts.get(table_name)
        if actual != expected:
            errors.append(f"table_counts.{table_name} expected {expected}, found {actual}")
    for field in ("startup_created_at", "startup_updated_at"):
        expected_bounds = manifest.get(field) or {}
        actual_bounds = facts.get(field) or {}
        for bound in ("min", "max"):
            if actual_bounds.get(bound) != expected_bounds.get(bound):
                errors.append(
                    f"{field}.{bound} expected {expected_bounds.get(bound)}, "
                    f"found {actual_bounds.get(bound)}"
                )
    return errors


async def verify_snapshot(database_url: str, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("database") != SNAPSHOT_DATABASE_NAME:
        raise RuntimeError("local_snapshot_manifest_invalid: unexpected database name")
    connection = await asyncpg.connect(database_url)
    try:
        facts = await collect_snapshot_facts(
            connection, sorted((manifest.get("table_counts") or {}).keys())
        )
    finally:
        await connection.close()
    errors = validate_snapshot_facts(facts, manifest)
    if errors:
        raise RuntimeError("local_snapshot_manifest_mismatch: " + "; ".join(errors))
    return facts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    try:
        facts = asyncio.run(verify_snapshot(args.database_url))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "Local snapshot verified: "
        f"{facts['table_counts'].get('startups', 0)} startups, "
        f"migration head {facts['migration_head']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
