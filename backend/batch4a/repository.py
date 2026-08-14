"""Explicit asyncpg repositories for Batch 4A domains."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tenant_context import require_user_id

STATUSES = frozenset({
    "pending", "ingesting", "scouting", "processing_signals",
    "generating_memo", "writing_memo", "ready", "failed",
})


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, dict) else {}


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _db_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Batch4AState:
    user_id: str
    pipeline_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    scoring_trails: list[dict[str, Any]] = field(default_factory=list)
    pipeline_activity: list[dict[str, Any]] = field(default_factory=list)
    dirty_pipeline_states: set[str] = field(default_factory=set)
    appended_scoring_trails: list[dict[str, Any]] = field(default_factory=list)
    appended_activity: list[dict[str, Any]] = field(default_factory=list)

    def get_pipeline_state(self, startup_id: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.pipeline_states.get(startup_id))

    def upsert_pipeline_state(self, row: dict[str, Any]) -> None:
        self.pipeline_states[row["startup_id"]] = copy.deepcopy(row)
        self.dirty_pipeline_states.add(row["startup_id"])

    def remove_pipeline_state(self, startup_id: str) -> None:
        self.pipeline_states.pop(startup_id, None)
        self.dirty_pipeline_states.discard(startup_id)

    def append_scoring_trail(self, row: dict[str, Any]) -> bool:
        item = copy.deepcopy(row)
        item["id"] = str(item.get("id") or uuid4())
        self.scoring_trails.append(item)
        self.appended_scoring_trails.append(item)
        return True

    def append_activity(self, row: dict[str, Any]) -> str:
        item = copy.deepcopy(row)
        item["id"] = str(item.get("id") or uuid4())
        self.pipeline_activity.append(item)
        self.appended_activity.append(item)
        return item["id"]


class Batch4ARepository:
    def __init__(self, pool):
        self.pool = pool

    async def load_state(self, user_id: str) -> Batch4AState:
        uid = require_user_id(user_id, context="Batch4ARepository.load_state")
        async with self.pool.acquire() as connection:
            states = await connection.fetch(
                """select id,user_id,startup_id,pipeline_run_id,status,updated_at,error
                   from public.startup_pipeline_state where user_id=$1""", uid
            )
            trails = await connection.fetch(
                """select id,startup_id,created_at,rubric_version,policy_version_id,
                          policy_hash,overall_score,overall_confidence,stage_cohort,
                          sector_tam_benchmark,trail
                   from public.scoring_trails where user_id=$1 order by created_at,id""", uid
            )
            activity = await connection.fetch(
                """select id,timestamp,startups_found,reviewed_count,decisions_made,escalations_count
                   from public.pipeline_activity where user_id=$1 order by timestamp,id""", uid
            )
        return Batch4AState(
            uid,
            {row["startup_id"]: {k: (_iso(v) if k in {"updated_at"} else str(v) if k in {"id", "pipeline_run_id"} else v) for k, v in dict(row).items()} for row in states},
            [{**dict(row), "id": str(row["id"]), "created_at": _iso(row["created_at"]), "trail": _json(row["trail"])} for row in trails],
            [{**dict(row), "id": str(row["id"]), "timestamp": _iso(row["timestamp"])} for row in activity],
        )

    async def get_pipeline_state(self, user_id: str, startup_id: str) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="Batch4ARepository.get_pipeline_state")
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """select pipeline_run_id,status,updated_at,error from public.startup_pipeline_state
                   where user_id=$1 and startup_id=$2 limit 1""", uid, startup_id,
            )
        if not row:
            return None
        return {"pipeline_run_id": str(row["pipeline_run_id"]), "status": row["status"], "updated_at": _iso(row["updated_at"]), "error": row["error"]}

    async def list_pipeline_activity_since(self, user_id: str, last_seen_at: str | None = None) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="Batch4ARepository.list_pipeline_activity_since")
        since = _db_timestamp(last_seen_at) if last_seen_at else datetime(1970, 1, 1, tzinfo=timezone.utc)
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """select user_id,timestamp,startups_found,reviewed_count,decisions_made,escalations_count
                   from public.pipeline_activity where user_id=$1 and timestamp>$2 order by timestamp,id""",
                uid, since,
            )
        return [{**dict(row), "timestamp": _iso(row["timestamp"])} for row in rows]

    async def list_all_pipeline_activity(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """select user_id,timestamp,startups_found,reviewed_count,decisions_made,escalations_count
                   from public.pipeline_activity order by timestamp,id"""
            )
        return [{**dict(row), "timestamp": _iso(row["timestamp"])} for row in rows]

    async def persist_state(self, state: Batch4AState) -> None:
        uid = require_user_id(state.user_id, context="Batch4ARepository.persist_state")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for startup_id in state.dirty_pipeline_states:
                    row = state.pipeline_states[startup_id]
                    await connection.execute(
                        """insert into public.startup_pipeline_state
                           (id,user_id,startup_id,pipeline_run_id,status,updated_at,error)
                           values ($1::uuid,$2,$3,$4::uuid,$5,$6,$7)
                           on conflict (user_id,startup_id) do update set
                             pipeline_run_id=excluded.pipeline_run_id,status=excluded.status,
                             updated_at=excluded.updated_at,error=excluded.error""",
                        row.get("id") or str(uuid4()), uid, startup_id, row["pipeline_run_id"],
                        row["status"], _db_timestamp(row.get("updated_at")), row.get("error"),
                    )
                for row in state.appended_scoring_trails:
                    await connection.execute(
                        """insert into public.scoring_trails
                           (id,user_id,startup_id,rubric_version,policy_version_id,policy_hash,
                            overall_score,overall_confidence,stage_cohort,sector_tam_benchmark,trail)
                           values ($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)""",
                        row["id"], uid, row["startup_id"], row.get("rubric_version"),
                        row.get("policy_version_id"), row.get("policy_hash"), row.get("overall_score"),
                        row.get("overall_confidence"), row.get("stage_cohort"), row.get("sector_tam_benchmark"),
                        json.dumps(row["trail"]),
                    )
                for row in state.appended_activity:
                    await connection.execute(
                        """insert into public.pipeline_activity
                           (id,user_id,timestamp,startups_found,reviewed_count,decisions_made,escalations_count)
                           values ($1::uuid,$2,coalesce($3,now()),$4,$5,$6,$7)""",
                        row["id"], uid, _db_timestamp(row.get("timestamp")), int(row.get("startups_found", 0)),
                        int(row.get("reviewed_count", 0)), int(row.get("decisions_made", 0)),
                        int(row.get("escalations_count", 0)),
                    )
        state.dirty_pipeline_states.clear()
        state.appended_scoring_trails.clear()
        state.appended_activity.clear()
