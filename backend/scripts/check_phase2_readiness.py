#!/usr/bin/env python3
"""Machine-readable canonical identity rollout gate for one tenant."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.golden_set import run_golden_set
from identity.backfill import CanonicalIdentityBackfill
from identity.reconciliation import reconcile_identity
from identity.repository import IdentityRepository
from identity.service import IdentityService
from jobs.postgres import database_dsn


def _check(name: str, status: str, detail: str, **data: Any) -> Dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, **data}


async def _database_checks(dsn: str, user_id: str) -> List[Dict[str, Any]]:
    import asyncpg

    checks: List[Dict[str, Any]] = []
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            required_tables = {
                "companies",
                "source_observations",
                "company_identifiers",
                "company_aliases",
                "opportunities",
                "identity_resolution_cases",
            }
            tables = {
                row["table_name"]
                for row in await conn.fetch(
                    """
                    select table_name from information_schema.tables
                    where table_schema = 'public'
                      and table_name = any($1::text[])
                    """,
                    sorted(required_tables),
                )
            }
            checks.append(
                _check(
                    "canonical_identity_tables",
                    "passed" if tables == required_tables else "failed",
                    "canonical companies, observations, identifiers, opportunities, and cases",
                    missing=sorted(required_tables - tables),
                )
            )
            indexes = {
                row["indexname"]
                for row in await conn.fetch(
                    "select indexname from pg_indexes where schemaname = 'public'"
                )
            }
            required_indexes = {
                "companies_canonical_domain_idx",
                "source_observations_external_event_idx",
                "company_identifiers_verified_idx",
                "opportunities_state_idx",
                "identity_resolution_cases_open_idx",
                "agent_jobs_blocked_code_idx",
            }
            checks.append(
                _check(
                    "canonical_identity_indexes",
                    "passed" if required_indexes <= indexes else "failed",
                    "deduplication, queue, and operator-recovery indexes",
                    missing=sorted(required_indexes - indexes),
                )
            )
            migration_table = await conn.fetchval(
                "select to_regclass('supabase_migrations.schema_migrations')::text"
            )
            versions = set()
            if migration_table:
                versions = {
                    str(row["version"])
                    for row in await conn.fetch(
                        "select version from supabase_migrations.schema_migrations"
                    )
                }
            required_versions = {"20260715193000", "20260715210000", "20260715220000"}
            checks.append(
                _check(
                    "phase2_migrations",
                    "passed" if required_versions <= versions else "failed",
                    "durable jobs, canonical identity, and structured block migrations",
                    missing=sorted(required_versions - versions),
                )
            )
        repository = IdentityRepository(pool)
        dry_run = await CanonicalIdentityBackfill(
            pool,
            repository=repository,
            service=IdentityService(repository),
        ).run_batch(user_id=user_id, apply=False, batch_size=100)
        checks.append(
            _check(
                "backfill_dry_run",
                "passed",
                "bounded tenant backfill preview completed without writes",
                counts={
                    "rows_processed": dry_run.rows_processed,
                    "would_resolve": dry_run.would_resolve,
                    "would_require_identity_review": dry_run.would_require_identity_review,
                },
                next_cursor=dry_run.next_cursor,
                complete=dry_run.complete,
            )
        )
        reconciliation = await reconcile_identity(pool, user_id=user_id)
        checks.append(
            _check(
                "identity_reconciliation",
                "failed" if reconciliation.has_violations else "passed",
                "count-only canonical/legacy reconciliation",
                counts=reconciliation.counts,
                violations=reconciliation.violations,
            )
        )
    finally:
        await pool.close()
    return checks


async def _run(user_id: str) -> Dict[str, Any]:
    golden = run_golden_set("v2")
    checks = [
        _check(
            "golden_set_v2",
            "passed" if golden["failed"] == 0 else "failed",
            f"{golden['passed']} passed; {golden['failed']} failed",
        )
    ]
    dsn = database_dsn()
    if not dsn:
        checks.append(
            _check(
                "direct_database_dsn",
                "blocked",
                "DATABASE_URL or SUPABASE_DB_URL is required for the Phase 2 rollout gate",
            )
        )
    else:
        checks.append(
            _check("direct_database_dsn", "passed", "direct PostgreSQL configuration is present")
        )
        try:
            checks.extend(await _database_checks(dsn, user_id))
        except Exception as exc:
            checks.append(
                _check(
                    "phase2_database_readiness",
                    "failed",
                    f"database readiness query failed ({type(exc).__name__})",
                )
            )
    return {
        "ready": all(check["status"] == "passed" for check in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = asyncio.run(_run(args.user_id))
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Phase 2 readiness: {'READY' if result['ready'] else 'NOT READY'}")
        for check in result["checks"]:
            print(f"- {check['name']}: {check['status']} — {check['detail']}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
