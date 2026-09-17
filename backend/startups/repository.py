"""Provider-neutral asyncpg reads for the canonical ``startups`` table."""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from tenant_context import require_user_id
from models import Startup


FULL_COLUMNS = (
    "id,user_id,startup_id,scout_info,review_info,partner_info,financials,version,"
    "human_resolution,created_at,updated_at,investment_memo_markdown,conviction_state,"
    "unresolved_at,agent_trace,first_seen_at,last_seen_by_user_at,acknowledged_at,"
    "queue_reason,priority_reason"
)

LIST_COLUMNS = (
    "user_id,startup_id,updated_at,created_at,first_seen_at,last_seen_by_user_at,"
    "acknowledged_at,unresolved_at,scout_info,review_info,partner_info,"
    "human_resolution,investment_memo_markdown,display_name,list_one_line,list_sector,list_scout_type,"
    "list_origin_type,list_lookup_query,list_lookup_website,list_confidence,list_score,"
    "list_verdict,list_consensus_verdict,list_reviewed_at,list_partnered_at,short_summary,"
    "list_reviewer_disagreement,partner_human_review_required,list_lookup_id,"
    "partner_decision,list_location,list_resolution_status,queue_reason,priority_reason"
)


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_value(value: Any) -> Any:
    return json.dumps(value) if isinstance(value, (dict, list)) else value


def _queue_reasons_for_startup(startup: Startup) -> tuple[str, str]:
    """Build queue display fields without depending on legacy storage code."""
    sector = (startup.scout_info.sector or "").split("/")[0].strip()
    review = startup.review_info
    # ponytail: legacy Reviewer scores are not queue conviction; keep priority
    # pending until a canonical evaluation projection is available.
    priority_parts = ["Priority pending"]
    human_resolution = startup.human_resolution if isinstance(startup.human_resolution, dict) else None
    if human_resolution and human_resolution.get("resolved_at"):
        decision = str(human_resolution.get("decision") or "recorded").upper()
        queue_reason = f"Human ruling recorded: {decision}."
        priority_parts.append("Human ruled")
    elif startup.partner_info and startup.partner_info.human_review_required:
        queue_reason = "Human ruling required."
        priority_parts.append("Human ruling required")
    elif startup.partner_info and startup.partner_info.recommendation:
        recommendation = startup.partner_info.recommendation
        queue_reason = f"Partner recommends {recommendation.lower()}."
        priority_parts.append(f"Partner {recommendation}")
    elif review:
        queue_reason = "Reviewer output ready for partner judgement."
        priority_parts.append("Reviewed")
    else:
        queue_reason = "New discovery awaiting review."
        priority_parts.append("New signal")
    if sector:
        priority_parts.append(sector)
    return queue_reason, " · ".join(priority_parts)


def startup_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Map a database row to the existing API/model startup shape."""
    return {
        "startup_id": row.get("startup_id"),
        "scout_info": _decode(row.get("scout_info")) or {},
        "review_info": _decode(row.get("review_info")),
        "partner_info": _decode(row.get("partner_info")),
        "financials": _decode(row.get("financials")) or {},
        "version": row.get("version", 1),
        "human_resolution": _decode(row.get("human_resolution")),
        "conviction_state": _decode(row.get("conviction_state")),
        "agent_trace": _decode(row.get("agent_trace")),
        "investment_memo_markdown": row.get("investment_memo_markdown"),
        "unresolved_at": row.get("unresolved_at"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_by_user_at": row.get("last_seen_by_user_at"),
        "acknowledged_at": row.get("acknowledged_at"),
        "queue_reason": row.get("queue_reason"),
        "priority_reason": row.get("priority_reason"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _iso_row(row: Any) -> dict[str, Any]:
    result = dict(row)
    for key in ("created_at", "updated_at", "first_seen_at", "last_seen_by_user_at", "acknowledged_at", "unresolved_at"):
        value = result.get(key)
        if value is not None and hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    for key in ("scout_info", "review_info", "partner_info", "financials", "human_resolution", "conviction_state", "agent_trace"):
        result[key] = _decode(result.get(key))
    return result


class StartupRepository:
    """Async repository for the canonical ``startups`` table."""

    def __init__(self, pool: Any):
        self.pool = pool

    async def create_startup(
        self,
        user_id: str,
        scout_info: Any,
        *,
        financials: Any | None = None,
        pipeline_run_id: str | None = None,
    ) -> str:
        """Insert a discovery without replacing an existing startup row.

        Exception (product decision, 2026-08-19): if the existing row hasn't
        been reviewed yet, refresh its confidence_score from this fresh
        discovery. Without this, a startup Scout keeps rediscovering (the
        common case -- Scout's queries tend to resurface the same handful of
        companies) is stuck forever on whatever confidence its first-ever
        discovery computed, which is exactly wrong for the triage-funnel
        gate that compares confidence_score against a threshold: a company
        that only cleared 1 of 3 mandate categories on day one but 2 of 3
        today would never re-enter review. Everything else about the row
        (review_info, partner_info, queue state, other scout_info fields)
        is untouched -- only confidence_score, and only while unreviewed.
        """
        uid = require_user_id(user_id, context="StartupRepository.create_startup")
        startup_id = str(scout_info.startup_id)
        name = str(getattr(scout_info, "name", "") or "").strip()
        async with self.pool.acquire() as connection:
            existing = await connection.fetchval(
                "select startup_id from public.startups where user_id=$1 and startup_id=$2 limit 1",
                uid, startup_id,
            )
            if existing is not None:
                await self._refresh_confidence_if_unreviewed(connection, uid, str(existing), scout_info)
                return str(existing)
            if name:
                existing = await connection.fetchval(
                    "select startup_id from public.startups "
                    "where user_id=$1 and lower(btrim(display_name))=$2 limit 1",
                    uid, name.casefold(),
                )
                if existing is not None:
                    await self._refresh_confidence_if_unreviewed(connection, uid, str(existing), scout_info)
                    return str(existing)

            now = datetime.now(timezone.utc)
            scout_payload = scout_info.model_dump(mode="json")
            financial_payload = (
                financials.model_dump(mode="json") if financials is not None else {}
            )
            queue_reason = "New discovery awaiting review."
            sector = str(getattr(scout_info, "sector", "") or "").split("/")[0].strip()
            priority_reason = "Priority pending"
            if sector:
                priority_reason = f"{priority_reason} · {sector}"
            try:
                await connection.execute(
                    """insert into public.startups
                       (user_id,startup_id,scout_info,financials,version,unresolved_at,
                        first_seen_at,queue_reason,priority_reason,created_at,updated_at)
                       values ($1,$2,$3::jsonb,$4::jsonb,1,$5,$5,$6,$7,$5,$5)""",
                    uid, startup_id, json.dumps(scout_payload), json.dumps(financial_payload),
                    now, queue_reason, priority_reason,
                )
            except Exception as exc:
                # The database unique constraints close races between the preflight
                # checks. Resolve only a genuine duplicate; never overwrite its row.
                raced = await connection.fetchval(
                    "select startup_id from public.startups where user_id=$1 and "
                    "(startup_id=$2 or ($3 <> '' and lower(btrim(display_name))=$3)) limit 1",
                    uid, startup_id, name.casefold(),
                )
                if raced is None:
                    raise
                await self._refresh_confidence_if_unreviewed(connection, uid, str(raced), scout_info)
                return str(raced)
        # Startup insertion is the durable boundary. Pipeline state is a
        # separate, eventual-consistency side effect, matching the legacy
        # creation contract; a state-write failure must not roll back the row.
        if pipeline_run_id:
            from pipeline_state import pipeline_stage_log, upsert_pipeline_state

            pipeline_stage_log(
                pipeline_run_id,
                startup_id=startup_id,
                user_id=uid,
                stage="scouting",
                phase="DONE",
            )
            upsert_pipeline_state(
                None,
                user_id=uid,
                startup_id=startup_id,
                pipeline_run_id=pipeline_run_id,
                status="pending",
            )
        return startup_id

    async def _refresh_confidence_if_unreviewed(
        self, connection: Any, user_id: str, startup_id: str, scout_info: Any
    ) -> None:
        """Refresh scout_info.confidence_score on a re-discovered startup --
        see create_startup's docstring. No-ops if the row has since been
        reviewed (WHERE clause is the authoritative guard, not the caller)."""
        confidence = getattr(scout_info, "confidence_score", None)
        if confidence is None:
            return
        await connection.execute(
            "update public.startups set "
            "scout_info = jsonb_set(scout_info, '{confidence_score}', $3::jsonb), "
            "updated_at = now() "
            "where user_id=$1 and startup_id=$2 and review_info is null",
            user_id, startup_id, json.dumps(float(confidence)),
        )

    async def update_financials(self, user_id: str, startup_id: str, financials: Any) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.update_financials")
        payload = financials.model_dump(mode="json")
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "update public.startups set financials=$3::jsonb, updated_at=now() "
                "where user_id=$1 and startup_id=$2",
                uid, str(startup_id), json.dumps(payload),
            )
        return result.endswith(" 1")

    async def acknowledge_startup(self, user_id: str, startup_id: str, seen_at: datetime) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.acknowledge_startup")
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "update public.startups set acknowledged_at=$3, last_seen_by_user_at=$3, "
                "updated_at=now() where user_id=$1 and startup_id=$2",
                uid, str(startup_id), seen_at,
            )
        return result.endswith(" 1")

    async def update_scalar_fields(self, user_id: str, startup_id: str, **fields: Any) -> bool:
        """Update only scalar queue fields with exclusive ownership."""
        allowed = {"first_seen_at", "last_seen_by_user_at", "acknowledged_at", "unresolved_at", "queue_reason", "priority_reason"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"StartupRepository.update_scalar_fields: unsupported fields: {sorted(unknown)}")
        if not fields:
            return await self.exists(user_id, startup_id)
        uid = require_user_id(user_id, context="StartupRepository.update_scalar_fields")
        assignments = [f"{name}=${index}" for index, name in enumerate(fields, start=3)]
        values = [uid, str(startup_id), *fields.values()]
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                f"update public.startups set {', '.join(assignments)}, updated_at=now() "
                "where user_id=$1 and startup_id=$2",
                *values,
            )
        return result.endswith(" 1")

    async def update_review(
        self,
        user_id: str,
        startup_id: str,
        review_info: Any,
        *,
        pipeline_run_id: str | None = None,
        enrichment_review_output: dict[str, Any] | None = None,
        enrichment_gap_reference_urls: list[str] | None = None,
        enrichment_founder_resolution: Any = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.update_review")
        from context import merge_scout_info_enrichment
        from utils.founder_enrichment import merge_founder_resolution_into_scout_info
        from agent_trace import build_review_trace

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    f"select {FULL_COLUMNS} from public.startups where user_id=$1 and startup_id=$2 for update",
                    uid, str(startup_id),
                )
                if row is None:
                    return False
                current = Startup.from_dict(startup_dict(_iso_row(row)))
                if enrichment_review_output is not None:
                    current.scout_info = merge_scout_info_enrichment(
                        current.scout_info,
                        review_output=enrichment_review_output,
                        gap_reference_urls=enrichment_gap_reference_urls,
                    )
                if enrichment_founder_resolution is not None:
                    current.scout_info = merge_founder_resolution_into_scout_info(
                        current.scout_info, enrichment_founder_resolution
                    )
                current.review_info = review_info
                review_payload = (
                    dict(enrichment_review_output)
                    if isinstance(enrichment_review_output, dict)
                    else review_info.model_dump(mode="json")
                )
                trace_entry = build_review_trace(
                    review_payload,
                    scout=current.scout_info.model_dump(mode="json"),
                    pipeline_run_id=pipeline_run_id,
                    gap_reference_urls=enrichment_gap_reference_urls,
                    settings=settings or {},
                )
                current.queue_reason, current.priority_reason = _queue_reasons_for_startup(current)
                await connection.execute(
                    """update public.startups set scout_info=$3::jsonb, review_info=$4::jsonb,
                       queue_reason=$5, priority_reason=$6, updated_at=now(),
                       agent_trace=coalesce(agent_trace,'{}'::jsonb) || $7::jsonb
                       where user_id=$1 and startup_id=$2""",
                    uid, str(startup_id), json.dumps(current.scout_info.model_dump(mode="json")),
                    json.dumps(review_info.model_dump(mode="json")), current.queue_reason,
                    current.priority_reason, json.dumps({"reviewer": trace_entry}),
                )
        return True

    async def update_partner(
        self,
        user_id: str,
        startup_id: str,
        partner_info: Any,
        *,
        investment_memo_markdown: str | None = None,
        pipeline_run_id: str | None = None,
        evaluation_manifest_identity: Any = None,
        partner_execution_prompt_version: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.update_partner")
        from agent_trace import handoff_quality_from_trace
        from agent_trace import build_partner_trace
        trace_updates: dict[str, Any]
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    f"select {FULL_COLUMNS} from public.startups where user_id=$1 and startup_id=$2 for update",
                    uid, str(startup_id),
                )
                if row is None:
                    return False
                current = Startup.from_dict(startup_dict(_iso_row(row)))
                trace_updates = {
                    "partner": build_partner_trace(
                        partner_info.model_dump(mode="json"),
                        scout=current.scout_info.model_dump(mode="json"),
                        review=current.review_info.model_dump(mode="json") if current.review_info else {},
                        pipeline_run_id=pipeline_run_id,
                        handoff_quality=handoff_quality_from_trace(current.agent_trace),
                        settings=settings or {},
                    )
                }
                # Build the governed manifest from the candidate post-write
                # snapshot. Manifest validation requires the partner artifact
                # and the partner stage trace to be present on that snapshot.
                current.partner_info = partner_info
                current.agent_trace = {
                    **(current.agent_trace or {}),
                    **trace_updates,
                }
                current.unresolved_at = partner_info.partnered_at if partner_info.human_review_required else None
                current.queue_reason, current.priority_reason = _queue_reasons_for_startup(current)
                if pipeline_run_id:
                    from evaluation.manifest import build_evaluation_manifest, validate_evaluation_manifest_for_persistence
                    if evaluation_manifest_identity is None:
                        raise ValueError("evaluation_manifest_identity is required for governed persistence")
                    path = "rerun" if str(getattr(current.scout_info, "operator_context", None) or "").strip() else (
                        "manual_lookup" if getattr(current.scout_info, "origin_type", None) == "on_demand_lookup" else "autonomous_discovery"
                    )
                    manifest = validate_evaluation_manifest_for_persistence(
                        build_evaluation_manifest(
                            current,
                            pipeline_run_id=pipeline_run_id,
                            evaluation_path=path,
                            manifest_identity=evaluation_manifest_identity,
                            partner_execution_prompt_version=partner_execution_prompt_version,
                        ),
                        manifest_identity=evaluation_manifest_identity,
                        partner_execution_prompt_version=partner_execution_prompt_version,
                        user_id=uid,
                    )
                    trace_updates["evaluation_manifest"] = manifest.model_dump(mode="json")
                values: list[Any] = [uid, str(startup_id), json.dumps(partner_info.model_dump(mode="json")), json.dumps(trace_updates), current.unresolved_at, current.queue_reason, current.priority_reason]
                memo_sql = ""
                if investment_memo_markdown is not None:
                    memo_sql = ", investment_memo_markdown=$8"
                    values.append(investment_memo_markdown)
                await connection.execute(
                    f"""update public.startups set partner_info=$3::jsonb, agent_trace=coalesce(agent_trace,'{{}}'::jsonb) || $4::jsonb,
                       unresolved_at=$5, queue_reason=$6, priority_reason=$7, updated_at=now(){memo_sql}
                       where user_id=$1 and startup_id=$2""",
                    *values,
                )
        return True

    async def merge_agent_trace_stage(self, user_id: str, startup_id: str, stage: str, payload: dict[str, Any]) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.merge_agent_trace_stage")
        if stage not in {"scout", "reviewer", "partner", "evaluation_manifest", "authority_projection"}:
            raise ValueError(f"unsupported agent_trace stage: {stage}")
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "update public.startups set agent_trace=coalesce(agent_trace,'{}'::jsonb) || $3::jsonb, "
                "updated_at=now() where user_id=$1 and startup_id=$2",
                uid, str(startup_id), json.dumps({stage: payload}),
            )
        return result.endswith(" 1")

    async def record_evaluation_manifest(self, user_id: str, startup_id: str, manifest: Any, *, manifest_identity: Any, partner_execution_prompt_version: str | None) -> bool:
        from evaluation.manifest import validate_evaluation_manifest_for_persistence
        validated = validate_evaluation_manifest_for_persistence(
            manifest,
            manifest_identity=manifest_identity,
            partner_execution_prompt_version=partner_execution_prompt_version,
            user_id=user_id,
        )
        return await self.merge_agent_trace_stage(user_id, startup_id, "evaluation_manifest", validated.model_dump(mode="json"))

    async def prepare_rerun(self, user_id: str, startup_id: str, *, operator_context: str, lookup_id: str | None = None, pipeline_run_id: str | None = None) -> str | None:
        uid = require_user_id(user_id, context="StartupRepository.prepare_rerun")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    f"select {FULL_COLUMNS} from public.startups where user_id=$1 and startup_id=$2 for update", uid, str(startup_id)
                )
                if row is None:
                    return None
                current = Startup.from_dict(startup_dict(_iso_row(row)))
                current.scout_info.operator_context = operator_context
                if lookup_id:
                    current.scout_info.lookup_id = lookup_id
                current.queue_reason, current.priority_reason = _queue_reasons_for_startup(current)
                await connection.execute(
                    "update public.startups set scout_info=$3::jsonb, queue_reason=$4, priority_reason=$5, updated_at=now() where user_id=$1 and startup_id=$2",
                    uid, str(startup_id), json.dumps(current.scout_info.model_dump(mode="json")), current.queue_reason, current.priority_reason,
                )
        if pipeline_run_id:
            from pipeline_state import upsert_pipeline_state
            upsert_pipeline_state(None, user_id=uid, startup_id=str(startup_id), pipeline_run_id=pipeline_run_id, status="ingesting")
        return str(startup_id)

    async def apply_human_resolution(self, user_id: str, startup_id: str, patch: dict[str, Any]) -> bool:
        allowed = {"human_resolution", "conviction_state", "unresolved_at", "queue_reason", "priority_reason"}
        if set(patch) - allowed:
            raise ValueError(f"unsupported human-resolution fields: {sorted(set(patch) - allowed)}")
        uid = require_user_id(user_id, context="StartupRepository.apply_human_resolution")
        json_fields = {"human_resolution", "conviction_state"}
        assignments = [
            f"{key}=${index}{'::jsonb' if key in json_fields else ''}"
            for index, key in enumerate(patch, start=3)
        ]
        values = [uid, str(startup_id), *[_json_value(patch[key]) for key in patch]]
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                f"update public.startups set {', '.join(assignments)}, updated_at=now() where user_id=$1 and startup_id=$2",
                *values,
            )
        return result.endswith(" 1")

    async def update_partner_memo(self, user_id: str, startup_id: str, memo: str) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.update_partner_memo")
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "update public.startups set investment_memo_markdown=$3, updated_at=now() "
                "where user_id=$1 and startup_id=$2",
                uid, str(startup_id), memo,
            )
        return result.endswith(" 1")

    async def remove_startup(self, user_id: str, startup_id: str) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.remove_startup")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "delete from public.startup_pipeline_state where user_id=$1 and startup_id=$2",
                    uid,
                    str(startup_id),
                )
                result = await connection.execute(
                    "delete from public.startups where user_id=$1 and startup_id=$2",
                    uid,
                    str(startup_id),
                )
        return result.endswith(" 1")

    async def remove_startups_without_references(self, user_id: str) -> int:
        """Best-effort tenant-scoped pruning of autonomous rows without evidence."""
        uid = require_user_id(user_id, context="StartupRepository.remove_startups_without_references")
        from research.reference_validation import is_generic_reference

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                rows = await connection.fetch(
                    "select startup_id,scout_info from public.startups where user_id=$1 for update",
                    uid,
                )
                bad_ids: list[str] = []
                for row in rows:
                    scout = _decode(row["scout_info"]) or {}
                    if str(scout.get("origin_type") or "").strip().lower() == "on_demand_lookup":
                        continue
                    if scout.get("company_resolution") or scout.get("resolution_status"):
                        continue
                    refs = scout.get("references")
                    valid = [ref for ref in refs or [] if isinstance(ref, str) and ref.strip() and not is_generic_reference(ref)]
                    if not valid:
                        bad_ids.append(str(row["startup_id"]))
                if not bad_ids:
                    return 0
                await connection.execute(
                    "delete from public.startup_pipeline_state where user_id=$1 and startup_id=any($2::text[])",
                    uid,
                    bad_ids,
                )
                result = await connection.execute(
                    "delete from public.startups where user_id=$1 and startup_id=any($2::text[])",
                    uid, bad_ids,
                )
        return int(result.rsplit(" ", 1)[-1])

    async def mark_partner_human_review(self, user_id: str, startup_id: str) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.mark_partner_human_review")
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                """update public.startups set
                   partner_info=jsonb_set(coalesce(partner_info,'{}'::jsonb), '{human_review_required}', 'true'::jsonb, true),
                   queue_reason='Human ruling required.', priority_reason='Human ruling required', updated_at=now()
                   where user_id=$1 and startup_id=$2""",
                uid, str(startup_id),
            )
        return result.endswith(" 1")

    async def get_row(self, user_id: str, startup_id: str, *, columns: str = FULL_COLUMNS) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="StartupRepository.get_row")
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"select {columns} from public.startups where user_id=$1 and startup_id=$2 limit 1",
                uid, str(startup_id),
            )
        return _iso_row(row) if row is not None else None

    async def get_startup(self, user_id: str, startup_id: str) -> dict[str, Any] | None:
        row = await self.get_row(user_id, startup_id)
        return startup_dict(row) if row is not None else None

    async def get_memo_projection(self, user_id: str, startup_id: str) -> dict[str, Any] | None:
        columns = "startup_id,scout_info,review_info,partner_info,financials,investment_memo_markdown,agent_trace,unresolved_at,updated_at"
        return await self.get_row(user_id, startup_id, columns=columns)

    async def list_projection(self, user_id: str, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="StartupRepository.list_projection")
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"""select {LIST_COLUMNS} from public.startups
                    where user_id=$1 order by updated_at desc, startup_id desc
                    limit $2 offset $3""", uid, limit, offset,
            )
        return [_iso_row(row) for row in rows]

    async def list_startups(self, user_id: str, *, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="StartupRepository.list_startups")
        args: list[Any] = [uid]
        pagination = ""
        if limit is not None:
            args.extend([max(1, min(int(limit), 500)), max(0, int(offset))])
            pagination = " limit $2 offset $3"
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"select {FULL_COLUMNS} from public.startups where user_id=$1 order by updated_at desc, startup_id desc{pagination}",
                *args,
            )
        return [startup_dict(_iso_row(row)) for row in rows]

    async def list_admin_summary(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "select user_id,partner_decision from public.startups order by user_id,startup_id"
            )
        return [dict(row) for row in rows]

    async def _list_filtered(self, user_id: str, predicate: str, *, limit: int | None = None, oldest: bool = False) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="StartupRepository._list_filtered")
        args: list[Any] = [uid]
        pagination = ""
        if limit is not None:
            args.append(max(1, min(int(limit), 500)))
            pagination = " limit $2"
        order = "updated_at asc" if oldest else "updated_at desc"
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"select {FULL_COLUMNS} from public.startups where user_id=$1 and {predicate} order by {order}, startup_id desc{pagination}",
                *args,
            )
        return [startup_dict(_iso_row(row)) for row in rows]

    async def list_unreviewed(self, user_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        return await self._list_filtered(user_id, "review_info is null", limit=limit, oldest=True)

    async def list_undecided(self, user_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        return await self._list_filtered(user_id, "review_info is not null and partner_info is null", limit=limit)

    async def list_reviewed(self, user_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        return await self._list_filtered(user_id, "review_info is not null", limit=limit)

    async def list_decided(self, user_id: str, *, decision: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        predicate = "partner_info is not null"
        args: list[Any] = [require_user_id(user_id, context="StartupRepository.list_decided")]
        if decision is not None:
            predicate += " and partner_decision=$2"
            args.append(decision)
        limit_sql = ""
        if limit is not None:
            args.append(max(1, min(int(limit), 500)))
            limit_sql = f" limit ${len(args)}"
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"select {FULL_COLUMNS} from public.startups where user_id=$1 and {predicate} order by updated_at desc, startup_id desc{limit_sql}",
                *args,
            )
        return [startup_dict(_iso_row(row)) for row in rows]

    async def list_pending_escalations(self, user_id: str) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="StartupRepository.list_pending_escalations")
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "select startup_id,scout_info,partner_info,human_resolution from public.startups "
                "where user_id=$1 and partner_human_review_required=true order by updated_at desc, startup_id desc", uid,
            )
        result = []
        for row in rows:
            item = startup_dict(_iso_row(row))
            resolution = item.get("human_resolution")
            if isinstance(resolution, dict) and resolution.get("resolved_at"):
                continue
            result.append(item)
        return result

    async def list_missing_thesis(self, user_id: str, *, limit: int = 1000) -> list[str]:
        uid = require_user_id(user_id, context="StartupRepository.list_missing_thesis")
        limit = max(1, min(int(limit), 2000))
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """select startup_id from public.startups
                   where user_id=$1 and review_info is not null
                     and nullif(trim(review_info->>'fund_thesis_version_id'), '') is null
                   order by updated_at desc, startup_id desc limit $2""", uid, limit,
            )
        return [str(row["startup_id"]) for row in rows]

    async def find_by_display_name(self, user_id: str, name: str) -> str | None:
        uid = require_user_id(user_id, context="StartupRepository.find_by_display_name")
        normalized = str(name or "").strip().casefold()
        if not normalized:
            return None
        async with self.pool.acquire() as connection:
            return await connection.fetchval(
                "select startup_id from public.startups where user_id=$1 and lower(btrim(display_name))=$2 limit 1",
                uid, normalized,
            )

    async def exists(self, user_id: str, startup_id: str) -> bool:
        uid = require_user_id(user_id, context="StartupRepository.exists")
        async with self.pool.acquire() as connection:
            return bool(await connection.fetchval(
                "select 1 from public.startups where user_id=$1 and startup_id=$2 limit 1", uid, str(startup_id)
            ))

    async def load_snapshot(self, user_id: str) -> "StartupReadSnapshot":
        uid = require_user_id(user_id, context="StartupRepository.load_snapshot")
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"select {FULL_COLUMNS} from public.startups where user_id=$1 order by updated_at desc, startup_id desc",
                uid,
            )
        return StartupReadSnapshot(uid, [startup_dict(_iso_row(row)) for row in rows])

    async def count_unreviewed(self, user_id: str) -> int:
        return await self._count(user_id, "review_info is null")

    async def count_undecided(self, user_id: str) -> int:
        return await self._count(user_id, "review_info is not null and partner_info is null")

    async def count_tenant(self, user_id: str) -> int:
        uid = require_user_id(user_id, context="StartupRepository.count_tenant")
        async with self.pool.acquire() as connection:
            return int(await connection.fetchval("select count(*) from public.startups where user_id=$1", uid) or 0)

    async def list_thesis_alignment(self, user_id: str, *, limit: int = 2000) -> list[dict[str, Any]]:
        """Return only the review fields needed for thesis-alignment reporting."""
        uid = require_user_id(user_id, context="StartupRepository.list_thesis_alignment")
        limit = max(1, min(int(limit), 2000))
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """select review_info->>'fund_thesis_version_id' as v,
                          review_info->>'thesis_alignment_score' as s,
                          review_info->>'fund_thesis_alignment_score' as s2,
                          review_info->>'thesis_matches_fund' as m
                   from public.startups
                  where user_id=$1 and review_info is not null
                  limit $2""", uid, limit,
            )
        return [dict(row) for row in rows]

    async def count_human_reviewed_since(self, user_id: str, since: str) -> int:
        uid = require_user_id(user_id, context="StartupRepository.count_human_reviewed_since")
        parsed = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        async with self.pool.acquire() as connection:
            return int(await connection.fetchval(
                "select count(*) from public.startups where user_id=$1 and (human_resolution->>'resolved_at')::timestamptz>$2",
                uid, parsed,
            ) or 0)

    async def count_unresolved(self, user_id: str) -> int:
        uid = require_user_id(user_id, context="StartupRepository.count_unresolved")
        async with self.pool.acquire() as connection:
            return int(await connection.fetchval(
                "select count(*) from public.startups where user_id=$1 and unresolved_at is not null", uid
            ) or 0)

    async def mark_existing_rerun_cancelled(self, user_id: str, lookup_id: str) -> str | None:
        """Restore readiness after cancelling an in-place startup re-review."""
        uid = require_user_id(user_id, context="StartupRepository.mark_existing_rerun_cancelled")
        lid = str(lookup_id or "").strip()
        if not lid:
            return None
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """select startup_id, partner_info, investment_memo_markdown
                   from public.startups
                   where user_id=$1 and list_lookup_id=$2 limit 1""", uid, lid,
            )
            if row is None or (not row["partner_info"] and not row["investment_memo_markdown"]):
                return None
            startup_id = str(row["startup_id"] or "").strip()
            if not startup_id:
                return None
            await connection.execute(
                """update public.startup_pipeline_state
                   set status='ready', updated_at=now()
                   where user_id=$1 and startup_id=$2 and pipeline_run_id is not null""",
                uid, startup_id,
            )
        return startup_id

    async def _count(self, user_id: str, predicate: str) -> int:
        uid = require_user_id(user_id, context="StartupRepository._count")
        async with self.pool.acquire() as connection:
            return int(await connection.fetchval(f"select count(*) from public.startups where user_id=$1 and {predicate}", uid) or 0)


@dataclass
class StartupReadSnapshot:
    user_id: str
    rows: list[dict[str, Any]]

    def _models(self) -> list[Startup]:
        return [Startup.from_dict(copy.deepcopy(row)) for row in self.rows]

    def get_startup(self, startup_id: str) -> Startup | None:
        for row in self.rows:
            if str(row.get("startup_id")) == str(startup_id):
                return Startup.from_dict(copy.deepcopy(row))
        return None

    def get_all(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(row) for row in self.rows]

    def get_by_id(self, startup_id: str) -> dict[str, Any] | None:
        startup = self.get_startup(startup_id)
        return startup.to_dict() if startup else None

    def get_unreviewed(self, limit: int | None = None) -> list[Startup]:
        rows = [row for row in self.rows if row.get("review_info") is None]
        result = [Startup.from_dict(copy.deepcopy(row)) for row in rows]
        result.sort(key=lambda item: item.scout_info.discovered_at)
        return result[:limit] if limit is not None else result

    def get_undecided(self, limit: int | None = None) -> list[Startup]:
        result = [Startup.from_dict(copy.deepcopy(row)) for row in self.rows
                  if row.get("review_info") is not None and row.get("partner_info") is None]
        return result[:limit] if limit is not None else result

    def get_with_review(self, limit: int | None = None) -> list[Startup]:
        result = [Startup.from_dict(copy.deepcopy(row)) for row in self.rows if row.get("review_info") is not None]
        return result[:limit] if limit is not None else result

    def get_with_decision(self, decision: str | None = None, limit: int | None = None) -> list[Startup]:
        result = [Startup.from_dict(copy.deepcopy(row)) for row in self.rows if row.get("partner_info") is not None]
        if decision is not None:
            result = [item for item in result if item.partner_info and item.partner_info.recommendation == decision]
        return result[:limit] if limit is not None else result

    def get_pending_escalations(self, limit: int | None = None) -> list[dict[str, Any]]:
        result = []
        for row in self.rows:
            partner = row.get("partner_info") or {}
            human = row.get("human_resolution") or {}
            if partner.get("human_review_required") and not human.get("resolved_at"):
                result.append(copy.deepcopy(row))
        return result[:limit] if limit is not None else result

    def missing_thesis(self, limit: int = 1000) -> list[str]:
        result = []
        for row in self.rows:
            review = row.get("review_info") or {}
            if row.get("review_info") is not None and not str(review.get("fund_thesis_version_id") or "").strip():
                result.append(str(row["startup_id"]))
        return result[:limit]

    def count_unreviewed(self) -> int:
        return sum(1 for row in self.rows if row.get("review_info") is None)

    def count_undecided(self) -> int:
        return sum(1 for row in self.rows if row.get("review_info") is not None and row.get("partner_info") is None)


class StartupReadStorageAdapter:
    """Read facade over a PostgreSQL snapshot with writes delegated unchanged."""

    def __init__(self, write_storage: Any, snapshot: StartupReadSnapshot):
        self._write_storage = write_storage
        self._snapshot = snapshot

    def get_startup(self, startup_id: str):
        return self._snapshot.get_startup(startup_id)

    def get_by_id(self, startup_id: str):
        return self._snapshot.get_by_id(startup_id)

    def get_all(self):
        return self._snapshot.get_all()

    def get_unreviewed(self, limit: int | None = None, **_kwargs):
        return self._snapshot.get_unreviewed(limit)

    def get_undecided(self, limit: int | None = None, **_kwargs):
        return self._snapshot.get_undecided(limit)

    def get_startups_with_review(self, limit: int | None = None):
        return self._snapshot.get_with_review(limit)

    def get_startups_with_decision(self, decision: str | None = None, limit: int | None = None):
        return self._snapshot.get_with_decision(decision, limit)

    def get_startups_requiring_human_review(self, limit: int | None = None):
        return [Startup.from_dict(row) for row in self._snapshot.get_pending_escalations(limit)]

    def query_pending_escalations_raw(self):
        return self._snapshot.get_pending_escalations()

    def count_unreviewed(self):
        return self._snapshot.count_unreviewed()

    def count_undecided(self):
        return self._snapshot.count_undecided()

    def get_startups_missing_thesis(self, *, limit: int = 1000):
        return self._snapshot.missing_thesis(limit)

    def get_startup_id_name_map(self):
        return {str(row["startup_id"]): str(row.get("scout_info", {}).get("name") or "") for row in self._snapshot.rows}

    def __getattr__(self, name: str):
        return getattr(self._write_storage, name)
