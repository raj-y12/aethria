"""Load read-only Supabase extraction batches into the local production snapshot.

The source extraction is deliberately performed by the caller through read-only
SQL. This tool owns only target-local writes, archive files, dependency ordering,
and the auditable import manifest.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import json
import os
import urllib.parse
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg


TARGET_DB_NAME = "aethria_prod_snapshot"
ARCHIVE_TABLES = ("portfolio_startups", "fund_policy_versions")
GENERATED_STARTUP_COLUMNS = {
    "display_name",
    "list_one_line",
    "list_sector",
    "list_scout_type",
    "list_origin_type",
    "list_lookup_query",
    "list_lookup_website",
    "list_confidence",
    "list_score",
    "list_verdict",
    "list_consensus_verdict",
    "list_reviewed_at",
    "list_partnered_at",
    "short_summary",
    "list_reviewer_disagreement",
    "partner_human_review_required",
    "list_lookup_id",
    "partner_decision",
    "list_location",
    "list_resolution_status",
}

# These nullable back-references are staged as NULL, then restored with the
# ``patch`` command after their referenced rows exist. This is required because
# the live domain graph intentionally contains cycles.
STAGED_COLUMNS = {
    "fund_thesis": {"active_version_id"},
    "opportunities": {"current_evaluation_id", "current_recommendation_id", "current_ruling_id"},
    "policy_proposals": {"resulting_policy_version_id"},
}
PATCH_KEYS = {
    "fund_thesis": ("id",),
    "opportunities": ("user_id", "opportunity_id"),
    "policy_proposals": ("user_id", "policy_proposal_id"),
}
ALIAS_ARTIFACT = Path(__file__).resolve().parents[2] / "db" / "reconciliation" / "portfolio_startup_aliases.json"

# This is the accepted live public-table inventory, excluding the two archive-only
# tables and the target-only startup_id_aliases reconciliation table.
COPY_TABLES = {
    "admin_audit_log", "agent_job_checkpoints", "agent_job_schedules", "agent_jobs",
    "analytics_sector_concentration", "authority_projection_receipts", "companies",
    "company_aliases", "company_identifiers", "domain_outbox", "evaluation_runs",
    "evidence_artifacts", "evidence_items", "evidence_plans", "fund_intelligence_settings",
    "fund_thesis", "fund_thesis_embeddings", "fund_thesis_pipeline_link", "fund_thesis_versions",
    "governed_policy_versions", "human_rulings", "identity_resolution_cases", "import_batches",
    "import_rows", "learning_signals", "lookup_job_outcomes", "material_change_checks", "memory",
    "meta_calibration_state", "meta_churn_signals", "meta_cycle_counters", "meta_mutation_log",
    "meta_prompt_library", "meta_reports", "meta_scout_weights", "opportunities", "outcome_evidence_links",
    "outcome_observations", "override_signals", "pipeline_activity", "policy_impact_previews",
    "policy_proposals", "portfolio_agent_metrics", "portfolio_budgets", "portfolio_decisions",
    "portfolio_feed_cache", "portfolio_rejection_patterns", "portfolio_positions", "portfolio_rejections",
    "portfolio_signals", "portfolio_watchlist", "recommendations", "ruling_interpretations", "scoring_trails",
    "security_limits", "settings", "source_observations", "startup_pipeline_state", "startups",
    "tenant_authority_rollouts", "triage_assessments", "user_state", "workflow_actions", "claims",
    "claim_corrections", "claim_evidence_links", "criterion_assessments", "canonical_portfolio_positions",
    "budget_reservations", "fund_thesis_embeddings", "fund_thesis_pipeline_link",
}


def _ident(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[:1].isdigit():
        raise ValueError(f"unsafe SQL identifier: {value}")
    return f'"{value}"'


def _decode_payload(value: str) -> Any:
    if value.startswith("url:"):
        return json.loads(urllib.parse.unquote(value[4:]))
    encoded = base64.b64decode(value)
    try:
        encoded = gzip.decompress(encoded)
    except OSError:
        pass
    return json.loads(encoded.decode("utf-8"))


async def _target_columns(conn: asyncpg.Connection, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name=$1
        order by ordinal_position
        """,
        table,
    )
    if not rows:
        raise RuntimeError(f"target table is missing: {table}")
    excluded = GENERATED_STARTUP_COLUMNS if table == "startups" else set()
    return [str(row["column_name"]) for row in rows if row["column_name"] not in excluded]


async def _assert_target(conn: asyncpg.Connection) -> None:
    db_name = await conn.fetchval("select current_database()")
    if db_name != TARGET_DB_NAME:
        raise RuntimeError(f"refusing non-snapshot database: {db_name}")
    host = os.getenv("SNAPSHOT_DATABASE_URL", "")
    if "127.0.0.1" not in host and "localhost" not in host:
        raise RuntimeError("refusing target without a local host DSN")
    if await conn.fetchval("select count(*) from pg_stat_activity where datname=$1", TARGET_DB_NAME) < 1:
        raise RuntimeError("snapshot database is not reachable")


async def _fk_order(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        """
        select tc.constraint_name, tc.table_name, ccu.table_name as parent_table
        from information_schema.table_constraints tc
        join information_schema.constraint_column_usage ccu
          on ccu.constraint_name=tc.constraint_name
         and ccu.constraint_schema=tc.constraint_schema
        where tc.table_schema='public' and tc.constraint_type='FOREIGN KEY'
        """
    )
    tables = set(COPY_TABLES)
    parents: dict[str, set[str]] = {table: set() for table in tables}
    children: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        child, parent = str(row["table_name"]), str(row["parent_table"])
        if child in tables and parent in tables and child != parent:
            staged = STAGED_COLUMNS.get(child, set())
            if row["constraint_name"] in {
                "opportunities_current_evaluation_fk",
                "opportunities_current_recommendation_fk",
                "opportunities_current_ruling_fk",
                "policy_proposals_resulting_version_fk",
                "fund_thesis_active_version_tenant_fk",
            }:
                continue
            parents[child].add(parent)
            children[parent].add(child)
    ready = deque(sorted(table for table, required in parents.items() if not required))
    ordered: list[str] = []
    while ready:
        table = ready.popleft()
        ordered.append(table)
        for child in sorted(children[table]):
            parents[child].discard(table)
            if not parents[child]:
                ready.append(child)
    if len(ordered) != len(tables):
        unresolved = sorted(tables - set(ordered))
        raise RuntimeError(f"FK graph contains unresolved cycle or missing dependency: {unresolved}")
    return ordered


async def _ingest(args: argparse.Namespace) -> None:
    rows = _decode_payload(args.payload_b64)
    if not isinstance(rows, list):
        raise ValueError("payload must be a JSON array")
    dsn = os.environ["SNAPSHOT_DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    try:
        await _assert_target(conn)
        if args.table not in COPY_TABLES:
            raise ValueError(f"table is not an approved runtime copy target: {args.table}")
        columns = await _target_columns(conn, args.table)
        if args.table == "security_limits":
            for row in rows:
                row.setdefault("lock_owner_token", None)
        for column in STAGED_COLUMNS.get(args.table, set()):
            for row in rows:
                row[column] = None
        if args.table == "startups":
            for row in rows:
                for column in GENERATED_STARTUP_COLUMNS:
                    row.pop(column, None)
        unknown = set().union(*(set(row) for row in rows)) - set(columns)
        if unknown:
            raise ValueError(f"source columns not accepted by target {args.table}: {sorted(unknown)}")
        if rows:
            column_sql = ",".join(_ident(column) for column in columns if column in rows[0])
            query = (
                f"insert into public.{_ident(args.table)} ({column_sql}) "
                f"select {column_sql} from jsonb_populate_recordset(null::public.{_ident(args.table)}, $1::jsonb) "
                "on conflict do nothing"
            )
            await conn.execute(query, json.dumps(rows, separators=(",", ":"), sort_keys=True))
        print(json.dumps({"table": args.table, "imported": len(rows)}))
    finally:
        await conn.close()


async def _insert_rows(conn: asyncpg.Connection, table: str, rows: list[dict[str, Any]]) -> int:
    columns = await _target_columns(conn, table)
    if table == "security_limits":
        for row in rows:
            row.setdefault("lock_owner_token", None)
    for column in STAGED_COLUMNS.get(table, set()):
        for row in rows:
            row[column] = None
    if table == "startups":
        for row in rows:
            for column in GENERATED_STARTUP_COLUMNS:
                row.pop(column, None)
    unknown = set().union(*(set(row) for row in rows)) - set(columns)
    if unknown:
        raise ValueError(f"source columns not accepted by target {table}: {sorted(unknown)}")
    if not rows:
        return 0
    column_sql = ",".join(_ident(column) for column in columns if column in rows[0])
    query = (
        f"insert into public.{_ident(table)} ({column_sql}) "
        f"select {column_sql} from jsonb_populate_recordset(null::public.{_ident(table)}, $1::jsonb) "
        "on conflict do nothing"
    )
    await conn.execute(query, json.dumps(rows, separators=(",", ":"), sort_keys=True))
    return len(rows)


async def _stream(args: argparse.Namespace) -> None:
    if args.table not in COPY_TABLES:
        raise ValueError(f"table is not an approved runtime copy target: {args.table}")
    conn = await asyncpg.connect(os.environ["SNAPSHOT_DATABASE_URL"])
    total = 0
    try:
        await _assert_target(conn)
        while line := await asyncio.to_thread(__import__("sys").stdin.readline):
            rows = json.loads(line)
            if not isinstance(rows, list):
                raise ValueError("stream payload must be a JSON array")
            total += await _insert_rows(conn, args.table, rows)
        print(json.dumps({"table": args.table, "stream_rows": total}))
    finally:
        await conn.close()


async def _archive(args: argparse.Namespace) -> None:
    rows = _decode_payload(args.payload_b64)
    if args.table not in ARCHIVE_TABLES:
        raise ValueError(f"table is not archive-only: {args.table}")
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_table": args.table,
        "snapshot_timestamp": args.snapshot_timestamp,
        "rows": rows,
    }
    path = archive_dir / f"{args.table}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"table": args.table, "archived": len(rows), "path": str(path)}))


async def _archive_append(args: argparse.Namespace) -> None:
    rows = _decode_payload(args.payload_b64)
    if args.table not in ARCHIVE_TABLES:
        raise ValueError(f"table is not archive-only: {args.table}")
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / f"{args.table}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_table") != args.table:
            raise ValueError("archive source table mismatch")
        payload["rows"].extend(rows)
    else:
        payload = {"source_table": args.table, "snapshot_timestamp": args.snapshot_timestamp, "rows": rows}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"table": args.table, "archived": len(payload["rows"]), "path": str(path)}))


async def _patch(args: argparse.Namespace) -> None:
    rows = _decode_payload(args.payload_b64)
    if args.table not in PATCH_KEYS:
        raise ValueError(f"table has no approved staged columns: {args.table}")
    staged = STAGED_COLUMNS[args.table]
    keys = PATCH_KEYS[args.table]
    if not rows:
        return
    conn = await asyncpg.connect(os.environ["SNAPSHOT_DATABASE_URL"])
    try:
        await _assert_target(conn)
        columns = await _target_columns(conn, args.table)
        updates = sorted(staged & set(columns))
        if not updates:
            raise ValueError(f"no staged columns found for {args.table}")
        key_sql = " and ".join(f"t.{_ident(key)}=src.{_ident(key)}" for key in keys)
        set_sql = ",".join(f"{_ident(column)}=src.{_ident(column)}" for column in updates)
        query = (
            f"update public.{_ident(args.table)} as t set {set_sql} "
            f"from jsonb_populate_recordset(null::public.{_ident(args.table)}, $1::jsonb) src "
            f"where {key_sql}"
        )
        result = await conn.execute(query, json.dumps(rows, separators=(",", ":"), sort_keys=True))
        print(json.dumps({"table": args.table, "patched": result}))
    finally:
        await conn.close()


async def _aliases(args: argparse.Namespace) -> None:
    payload = json.loads(ALIAS_ARTIFACT.read_text(encoding="utf-8"))
    mappings = payload.get("mappings") or []
    if payload.get("approved_batch") != "4B.5C" or payload.get("source") != "portfolio_startups":
        raise RuntimeError("startup alias artifact provenance is invalid")
    if payload.get("mapping_count") != 133 or len(mappings) != 133:
        raise RuntimeError("startup alias artifact must contain exactly 133 mappings")
    rows = [
        {
            "user_id": item["user_id"],
            "legacy_startup_id": item["legacy_startup_id"],
            "canonical_startup_id": item["canonical_startup_id"],
            "source": "portfolio_startups",
            "source_reference": f"portfolio_startups:{item['legacy_startup_id']}",
            "verification_state": "approved",
            "verification_evidence": item.get("evidence") or {},
        }
        for item in mappings
    ]
    conn = await asyncpg.connect(os.environ["SNAPSHOT_DATABASE_URL"])
    try:
        await _assert_target(conn)
        await conn.executemany(
            """
            insert into public.startup_id_aliases
              (user_id,legacy_startup_id,canonical_startup_id,source,source_reference,verification_state,verification_evidence)
            values ($1,$2,$3,$4,$5,$6,$7::jsonb)
            on conflict (user_id,legacy_startup_id) do update set
              canonical_startup_id=excluded.canonical_startup_id,
              source=excluded.source,
              source_reference=excluded.source_reference,
              verification_state=excluded.verification_state,
              verification_evidence=excluded.verification_evidence,
              updated_at=now()
            """,
            [
                (row["user_id"], row["legacy_startup_id"], row["canonical_startup_id"], row["source"], row["source_reference"], row["verification_state"], json.dumps(row["verification_evidence"], separators=(",", ":")))
                for row in rows
            ],
        )
        count = await conn.fetchval("select count(*) from public.startup_id_aliases")
        resolved = await conn.fetchval(
            """
            select count(*) from public.startup_id_aliases a
            join public.startups s on s.user_id=a.user_id and s.startup_id=a.canonical_startup_id
            where a.verification_state='approved'
            """
        )
        print(json.dumps({"artifact_rows": len(rows), "alias_rows": count, "resolved": resolved}))
    finally:
        await conn.close()


async def _order(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(os.environ["SNAPSHOT_DATABASE_URL"])
    try:
        await _assert_target(conn)
        print("\n".join(await _fk_order(conn)))
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    order = sub.add_parser("order")
    order.set_defaults(handler=_order)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("table")
    ingest.add_argument("payload_b64")
    ingest.set_defaults(handler=_ingest)
    stream = sub.add_parser("stream")
    stream.add_argument("table")
    stream.set_defaults(handler=_stream)
    archive = sub.add_parser("archive")
    archive.add_argument("table")
    archive.add_argument("payload_b64")
    archive.add_argument("snapshot_timestamp")
    archive.add_argument("archive_dir")
    archive.set_defaults(handler=_archive)
    archive_append = sub.add_parser("archive-append")
    archive_append.add_argument("table")
    archive_append.add_argument("payload_b64")
    archive_append.add_argument("snapshot_timestamp")
    archive_append.add_argument("archive_dir")
    archive_append.set_defaults(handler=_archive_append)
    patcher = sub.add_parser("patch")
    patcher.add_argument("table")
    patcher.add_argument("payload_b64")
    patcher.set_defaults(handler=_patch)
    aliases = sub.add_parser("aliases")
    aliases.set_defaults(handler=_aliases)
    args = parser.parse_args()
    asyncio.run(args.handler(args))


if __name__ == "__main__":
    main()
