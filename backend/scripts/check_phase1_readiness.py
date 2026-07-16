#!/usr/bin/env python3
"""Machine-readable readiness gate for the institutional Phase 0–1 substrate."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import metrics
from evaluation.golden_set import run_golden_set
from jobs.postgres import database_dsn
from jobs.repository import DurableJobRepository
from meta.agent import MetaAgent


def _check(name: str, status: str, detail: str, **data: Any) -> Dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, **data}


def _offline_checks() -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    golden = run_golden_set("v1")
    checks.append(
        _check(
            "golden_set_v1",
            "passed" if golden["failed"] == 0 else "failed",
            f"{golden['passed']} passed; {golden['failed']} failed",
        )
    )

    agent = MetaAgent(user_id="phase1-readiness-smoke")
    agent.min_reviews = 1
    agent.min_decisions = 1
    insufficient = {"data_sufficiency": {"total_reviews": 0, "total_decisions": 0}}
    with patch.object(agent, "_increment_cycle", return_value=1), patch(
        "meta.agent.MetaAnalyser"
    ) as analyser, patch("meta.agent._append_to_json_list"):
        analyser.return_value.analyse.return_value = insufficient
        report = agent._run_cycle_sync()
    meta_safe = bool(
        report
        and report.get("analysis_only") is True
        and report.get("production_mutations_applied") == 0
        and report.get("mutations_applied") == []
    )
    checks.append(
        _check(
            "meta_analysis_only",
            "passed" if meta_safe else "failed",
            "automatic Meta output cannot activate production mutations",
        )
    )

    expected_metrics = {
        "aethria_decision_ready_cost_usd",
        "aethria_decision_ready_tokens",
        "aethria_evaluation_manifest",
        "aethria_durable_jobs",
        "aethria_durable_job_wait_seconds",
        "aethria_durable_job_run_seconds",
        "aethria_outbox_backlog",
    }
    registered = (
        {metric.name for metric in metrics.REGISTRY.collect()} if metrics.ENABLED else set()
    )
    missing = sorted(expected_metrics - registered)
    checks.append(
        _check(
            "institutional_metrics",
            "passed" if not missing else "failed",
            "required cost, manifest, latency, job, and outbox metrics are registered",
            missing=missing,
        )
    )
    return checks


async def _database_checks(dsn: str) -> List[Dict[str, Any]]:
    import asyncpg

    checks: List[Dict[str, Any]] = []
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            version = int(await conn.fetchval("show server_version_num"))
            checks.append(
                _check(
                    "postgres_version",
                    "passed" if version >= 140000 else "failed",
                    f"server_version_num={version}",
                )
            )
            tables = {
                row["table_name"]
                for row in await conn.fetch(
                    """
                    select table_name from information_schema.tables
                    where table_schema = 'public'
                      and table_name = any($1::text[])
                    """,
                    ["agent_jobs", "agent_job_checkpoints", "domain_outbox"],
                )
            }
            required_tables = {"agent_jobs", "agent_job_checkpoints", "domain_outbox"}
            checks.append(
                _check(
                    "durable_job_tables",
                    "passed" if tables == required_tables else "failed",
                    "transactional job, checkpoint, and outbox tables",
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
                "agent_jobs_claim_idx",
                "agent_jobs_lease_recovery_idx",
                "agent_jobs_tenant_status_idx",
                "agent_job_checkpoints_job_idx",
                "domain_outbox_unpublished_idx",
            }
            checks.append(
                _check(
                    "durable_job_indexes",
                    "passed" if required_indexes <= indexes else "failed",
                    "claim, recovery, tenant, checkpoint, and outbox indexes",
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
            required_versions = {
                "20260714192632",
                "20260714192642",
                "20260714192902",
                "20260715193000",
            }
            checks.append(
                _check(
                    "required_migrations",
                    "passed" if required_versions <= versions else "failed",
                    "schedule, tenant uniqueness, RLS optimization, and durable jobs migrations",
                    missing=sorted(required_versions - versions),
                )
            )
        depths = await DurableJobRepository(pool).global_queue_depths()
        checks.append(
            _check(
                "durable_job_depths",
                "passed",
                "queue, recovery, dead-letter, and outbox depths readable",
                counts=depths,
            )
        )
    finally:
        await pool.close()
    return checks


async def _run() -> Dict[str, Any]:
    checks = _offline_checks()
    dsn = database_dsn()
    if not dsn:
        checks.append(
            _check(
                "direct_database_dsn",
                "blocked",
                "DATABASE_URL or SUPABASE_DB_URL is required before accepted work can run",
            )
        )
    else:
        checks.append(
            _check(
                "direct_database_dsn",
                "passed",
                "direct PostgreSQL configuration is present",
            )
        )
        try:
            checks.extend(await _database_checks(dsn))
        except Exception as exc:
            checks.append(
                _check(
                    "database_readiness",
                    "failed",
                    f"database readiness query failed ({type(exc).__name__})",
                )
            )
    ready = all(check["status"] == "passed" for check in checks)
    return {"ready": ready, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = asyncio.run(_run())
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Phase 0-1 readiness: {'READY' if result['ready'] else 'NOT READY'}")
        for check in result["checks"]:
            print(f"- {check['name']}: {check['status']} — {check['detail']}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
