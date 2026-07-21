#!/usr/bin/env python3
"""Machine-readable rollout gate for the Phase 3–8 institutional domain."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.golden_set import run_golden_set
from jobs.postgres import database_dsn
from meta.calibrator import ThresholdCalibrator
from meta.reweighter import ScoutReweighter


PHASE3_8_MIGRATIONS = (
    "20260715230000_evidence_claim_ledger.sql",
    "20260715240000_immutable_evaluations.sql",
    "20260715250000_rulings_and_actions.sql",
    "20260715260000_attention_enrichment.sql",
    "20260715270000_fund_intelligence.sql",
    "20260715280000_channels_outcomes.sql",
    "20260720120000_materiality_digests.sql",
)
POLICY_UPGRADE_MIGRATION = (
    "20260721143000_patch_upgrade_fund_policy_settings.sql"
)
LOOKUP_OUTCOMES_SECURITY_MIGRATION = (
    "20260721150000_lookup_job_outcomes_rls.sql"
)

_MATERIALITY_COLUMNS = (
    ("evaluation_runs", "evidence_materiality_digest"),
    ("material_change_checks", "previous_materiality_digest"),
    ("material_change_checks", "current_materiality_digest"),
)


def _check(name: str, status: str, detail: str, **data: Any) -> Dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, **data}


def _migration_files_check(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    missing = [
        name
        for name in PHASE3_8_MIGRATIONS
        if not (repo_root / "supabase" / "migrations" / name).exists()
    ]
    return _check(
        "phase3_8_migration_files",
        "passed" if not missing else "failed",
        "evidence through materiality and outcome migrations are present",
        missing=missing,
    )


def _migration_versions_check(versions: set[str]) -> Dict[str, Any]:
    required_versions = {
        name.split("_", 1)[0] for name in PHASE3_8_MIGRATIONS
    }
    return _check(
        "phase3_8_migrations_applied",
        "passed" if required_versions <= versions else "failed",
        "all Phase 3–8 schema versions are recorded",
        missing=sorted(required_versions - versions),
    )


def _policy_upgrade_migration_file_check(
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    missing = []
    if not (
        repo_root / "supabase" / "migrations" / POLICY_UPGRADE_MIGRATION
    ).exists():
        missing.append(POLICY_UPGRADE_MIGRATION)
    return _check(
        "policy_upgrade_migration_file",
        "passed" if not missing else "failed",
        "atomic published-policy upgrade migration is present",
        missing=missing,
    )


def _policy_upgrade_version_check(versions: set[str]) -> Dict[str, Any]:
    required = POLICY_UPGRADE_MIGRATION.split("_", 1)[0]
    missing = [] if required in versions else [required]
    return _check(
        "policy_upgrade_migration_applied",
        "passed" if not missing else "failed",
        "atomic published-policy upgrade schema version is recorded",
        missing=missing,
    )


def _lookup_outcomes_security_migration_file_check(
    repo_root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    missing = []
    if not (
        repo_root
        / "supabase"
        / "migrations"
        / LOOKUP_OUTCOMES_SECURITY_MIGRATION
    ).exists():
        missing.append(LOOKUP_OUTCOMES_SECURITY_MIGRATION)
    return _check(
        "lookup_outcomes_security_migration_file",
        "passed" if not missing else "failed",
        "authoritative lookup outcome RLS migration is present",
        missing=missing,
    )


def _lookup_outcomes_security_version_check(
    versions: set[str],
) -> Dict[str, Any]:
    required = LOOKUP_OUTCOMES_SECURITY_MIGRATION.split("_", 1)[0]
    missing = [] if required in versions else [required]
    return _check(
        "lookup_outcomes_security_migration_applied",
        "passed" if not missing else "failed",
        "authoritative lookup outcome RLS schema version is recorded",
        missing=missing,
    )


def _policy_roles(raw: Any) -> set[str]:
    if isinstance(raw, (list, tuple, set)):
        return {str(role).strip().lower() for role in raw if str(role).strip()}
    text = str(raw or "").strip().strip("{}")
    return {
        role.strip().strip('"').lower()
        for role in text.split(",")
        if role.strip()
    }


def _lookup_outcomes_security_check(
    *,
    table_rows: List[Any],
    policy_rows: List[Any],
    grant_rows: List[Any],
) -> Dict[str, Any]:
    """Require exact RLS policy and client/service-role grants from live catalogs."""
    table = next(
        (
            row
            for row in table_rows
            if str(row["table_name"]) == "lookup_job_outcomes"
        ),
        None,
    )
    rls_enabled = bool(table and table["relrowsecurity"])
    policy_ok = len(policy_rows) == 1 and all(
        (
            str(row["policyname"]) == "lookup_job_outcomes_service_role_all"
            and _policy_roles(row["roles"]) == {"service_role"}
            and str(row["cmd"]).upper() == "ALL"
        )
        for row in policy_rows
    )
    grants = {
        (
            str(row["grantee"]).strip().lower(),
            str(row["privilege_type"]).strip().upper(),
        )
        for row in grant_rows
    }
    client_grants = sorted(
        f"{grantee}:{privilege}"
        for grantee, privilege in grants
        if grantee in {"public", "anon", "authenticated"}
    )
    service_grants = sorted(
        privilege
        for grantee, privilege in grants
        if grantee == "service_role"
    )
    expected_service_grants = ["DELETE", "INSERT", "SELECT", "UPDATE"]
    passed = (
        rls_enabled
        and policy_ok
        and not client_grants
        and service_grants == expected_service_grants
    )
    return _check(
        "lookup_outcomes_rls_and_grants",
        "passed" if passed else "failed",
        "lookup_job_outcomes is isolated to the service role",
        table_present=table is not None,
        rls_enabled=rls_enabled,
        policy_ok=policy_ok,
        client_grants=client_grants,
        service_grants=service_grants,
        expected_service_grants=expected_service_grants,
    )


def _materiality_columns_check(rows: List[Any]) -> Dict[str, Any]:
    observed = {
        (str(row["table_name"]), str(row["column_name"])): (
            str(row["data_type"]),
            str(row["udt_name"]),
        )
        for row in rows
    }
    missing = sorted(
        f"{table}.{column}"
        for table, column in _MATERIALITY_COLUMNS
        if (table, column) not in observed
    )
    wrong_type = []
    for table, column in _MATERIALITY_COLUMNS:
        actual = observed.get((table, column))
        if actual is None or actual == ("text", "text"):
            continue
        wrong_type.append(
            {
                "column": f"{table}.{column}",
                "expected": "text",
                "actual": f"{actual[0]} ({actual[1]})",
            }
        )
    return _check(
        "materiality_digest_columns",
        "passed" if not missing and not wrong_type else "failed",
        "all materiality digest columns exist with compatible types",
        missing=missing,
        wrong_type=wrong_type,
    )


def _code_checks() -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    golden = run_golden_set("v7")
    checks.append(
        _check(
            "golden_set_v7",
            "passed" if golden["failed"] == 0 else "failed",
            f"{golden['passed']} passed; {golden['failed']} failed",
        )
    )
    checks.append(_migration_files_check())
    checks.append(_policy_upgrade_migration_file_check())
    checks.append(_lookup_outcomes_security_migration_file_check())
    proposal_only = True
    for target, payload in (
        (object.__new__(ScoutReweighter), [{"scout_type": "x"}]),
        (object.__new__(ThresholdCalibrator), [{"parameter": "x"}]),
    ):
        try:
            target.apply(payload)
            proposal_only = False
        except RuntimeError:
            pass
    checks.append(
        _check(
            "meta_proposal_only",
            "passed" if proposal_only else "failed",
            "legacy reweighting and calibration apply paths cannot mutate production",
        )
    )
    return checks


async def _database_checks(dsn: str) -> List[Dict[str, Any]]:
    import asyncpg

    checks: List[Dict[str, Any]] = []
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            required_tables = {
                "evidence_artifacts", "evidence_items", "claims", "claim_evidence_links",
                "evidence_plans", "evaluation_runs", "criterion_assessments", "recommendations",
                "human_rulings", "override_signals", "workflow_actions", "budget_reservations",
                "material_change_checks", "learning_signals", "policy_proposals",
                "policy_impact_previews", "governed_policy_versions", "import_batches",
                "import_rows", "outcome_observations", "outcome_evidence_links",
                "lookup_job_outcomes",
            }
            rows = await conn.fetch(
                """
                select c.relname as table_name,c.relrowsecurity
                from pg_class c join pg_namespace n on n.oid=c.relnamespace
                where n.nspname='public' and c.relkind='r' and c.relname=any($1::text[])
                """,
                sorted(required_tables),
            )
            present = {str(row["table_name"]) for row in rows}
            rls_missing = sorted(str(row["table_name"]) for row in rows if not row["relrowsecurity"])
            checks.append(
                _check(
                    "phase3_8_tables_and_rls",
                    "passed" if present == required_tables and not rls_missing else "failed",
                    "all institutional tables exist with row-level security enabled",
                    missing=sorted(required_tables - present),
                    rls_missing=rls_missing,
                )
            )
            triggers = {
                str(row["tgname"])
                for row in await conn.fetch(
                    """
                    select tgname from pg_trigger
                    where not tgisinternal and tgname=any($1::text[])
                    """,
                    [
                        "evaluation_runs_immutable", "recommendations_immutable",
                        "human_rulings_append_only", "override_signals_append_only",
                        "learning_signals_append_only", "outcome_observations_append_only",
                    ],
                )
            }
            required_triggers = {
                "evaluation_runs_immutable", "recommendations_immutable",
                "human_rulings_append_only", "override_signals_append_only",
                "learning_signals_append_only", "outcome_observations_append_only",
            }
            checks.append(
                _check(
                    "immutability_triggers",
                    "passed" if required_triggers <= triggers else "failed",
                    "evaluations, recommendations, rulings, learning signals, and outcomes are protected",
                    missing=sorted(required_triggers - triggers),
                )
            )
            proposal_columns = {
                str(row["column_name"])
                for row in await conn.fetch(
                    """
                    select column_name from information_schema.columns
                    where table_schema='public' and table_name='policy_proposals'
                    """
                )
            }
            checks.append(
                _check(
                    "proposal_has_no_activation_column",
                    "passed" if not ({"active", "auto_activate", "activated_at"} & proposal_columns) else "failed",
                    "policy proposals cannot directly represent an active production policy",
                )
            )
            materiality_rows = await conn.fetch(
                """
                select table_name, column_name, data_type, udt_name
                from information_schema.columns
                where table_schema = 'public'
                  and (
                    (table_name = 'evaluation_runs'
                     and column_name = 'evidence_materiality_digest')
                    or
                    (table_name = 'material_change_checks'
                     and column_name in (
                       'previous_materiality_digest',
                       'current_materiality_digest'
                     ))
                  )
                """
            )
            checks.append(_materiality_columns_check(materiality_rows))
            lookup_policy_rows = await conn.fetch(
                """
                select policyname, roles, cmd
                from pg_policies
                where schemaname = 'public'
                  and tablename = 'lookup_job_outcomes'
                """
            )
            lookup_grant_rows = await conn.fetch(
                """
                select grantee, privilege_type
                from information_schema.table_privileges
                where table_schema = 'public'
                  and table_name = 'lookup_job_outcomes'
                  and lower(grantee) in (
                    'public', 'anon', 'authenticated', 'service_role'
                  )
                """
            )
            checks.append(
                _lookup_outcomes_security_check(
                    table_rows=list(rows),
                    policy_rows=list(lookup_policy_rows),
                    grant_rows=list(lookup_grant_rows),
                )
            )
            migration_table = await conn.fetchval(
                "select to_regclass('supabase_migrations.schema_migrations')::text"
            )
            versions = set()
            if migration_table:
                versions = {
                    str(row["version"])
                    for row in await conn.fetch("select version from supabase_migrations.schema_migrations")
                }
            checks.append(_migration_versions_check(versions))
            checks.append(_policy_upgrade_version_check(versions))
            checks.append(_lookup_outcomes_security_version_check(versions))
            policy_upgrade_rpc = await conn.fetchval(
                """
                select to_regprocedure(
                  'public.upgrade_fund_policy(text,text,text,text,text,jsonb,jsonb)'
                )::text
                """
            )
            checks.append(
                _check(
                    "policy_upgrade_rpc",
                    "passed" if policy_upgrade_rpc else "failed",
                    "service-role atomic published-policy upgrade RPC exists",
                )
            )
    finally:
        await pool.close()
    return checks


async def _run() -> Dict[str, Any]:
    checks = _code_checks()
    dsn = database_dsn()
    if not dsn:
        checks.append(
            _check(
                "direct_database_dsn",
                "blocked",
                "DATABASE_URL or SUPABASE_DB_URL is required for target PostgreSQL certification",
            )
        )
    else:
        checks.append(_check("direct_database_dsn", "passed", "direct PostgreSQL configuration is present"))
        try:
            checks.extend(await _database_checks(dsn))
        except Exception as exc:
            checks.append(
                _check(
                    "phase3_8_database_readiness",
                    "failed",
                    f"database readiness query failed ({type(exc).__name__})",
                )
            )
    return {"ready": all(item["status"] == "passed" for item in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = asyncio.run(_run())
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Phase 3–8 readiness: {'READY' if result['ready'] else 'NOT READY'}")
        for check in result["checks"]:
            print(f"- {check['name']}: {check['status']} — {check['detail']}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
