"""Asyncpg repository and snapshot for Batch 2 portfolio-derived state."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tenant_context import require_user_id


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _timestamp(value: Any) -> Any:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class Batch2State:
    user_id: str
    feed_cache: dict[str, Any] | None = None
    rejection_patterns: dict[str, Any] | None = None
    agent_metrics: list[dict[str, Any]] = field(default_factory=list)
    dirty_feed_cache: bool = False
    dirty_rejection_patterns: bool = False
    dirty_metrics: bool = False

    def get_feed_cache(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.feed_cache)

    def set_feed_cache(self, value: dict[str, Any]) -> None:
        self.feed_cache = copy.deepcopy(value)
        self.dirty_feed_cache = True

    def get_rejection_patterns(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.rejection_patterns)

    def set_rejection_patterns(self, value: dict[str, Any]) -> None:
        self.rejection_patterns = copy.deepcopy(value)
        self.dirty_rejection_patterns = True

    def get_metrics(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.agent_metrics)

    def append_metric(self, record: dict[str, Any]) -> str:
        item = copy.deepcopy(record)
        item["id"] = str(item.get("id") or uuid4())
        self.agent_metrics.append(item)
        self.dirty_metrics = True
        return item["id"]

    def replace_metrics(self, records: list[dict[str, Any]]) -> None:
        self.agent_metrics = copy.deepcopy(records)
        self.dirty_metrics = True


class Batch2Repository:
    """Explicit asyncpg boundary over the three Batch 2 tables."""

    def __init__(self, pool):
        self.pool = pool

    async def load_state(self, user_id: str) -> Batch2State:
        uid = require_user_id(user_id, context="Batch2Repository.load_state")
        async with self.pool.acquire() as connection:
            feed = await connection.fetchrow(
                """select id, cached_at, items, created_at
                   from public.portfolio_feed_cache
                   where user_id=$1 order by created_at desc, id desc limit 1""", uid
            )
            rejection = await connection.fetchrow(
                """select id, stats, created_at
                   from public.portfolio_rejection_patterns
                   where user_id=$1 order by created_at desc, id desc limit 1""", uid
            )
            metrics = await connection.fetch(
                """select id, data, created_at
                   from public.portfolio_agent_metrics
                   where user_id=$1 order by created_at, id""", uid
            )
        return Batch2State(
            user_id=uid,
            feed_cache=({**dict(feed), "id": str(feed["id"]), "items": _decode(feed["items"])} if feed else None),
            rejection_patterns=({**dict(rejection), "id": str(rejection["id"]), "stats": _decode(rejection["stats"])} if rejection else None),
            agent_metrics=[{"id": r["id"], **(_decode(r["data"]) if isinstance(_decode(r["data"]), dict) else {}), "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"]} for r in metrics],
        )

    async def persist_state(self, state: Batch2State) -> None:
        uid = require_user_id(state.user_id, context="Batch2Repository.persist_state")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                if state.dirty_feed_cache and state.feed_cache is not None:
                    row_id = state.feed_cache.get("id") or str(uuid4())
                    await connection.execute(
                        """insert into public.portfolio_feed_cache
                           (id,user_id,cached_at,items)
                           values ($1::uuid,$2,$3,$4::jsonb)
                           on conflict (id) do update set cached_at=excluded.cached_at, items=excluded.items
                           where public.portfolio_feed_cache.user_id=$2""",
                        row_id, uid, state.feed_cache["cached_at"], json.dumps(state.feed_cache.get("items", [])),
                    )
                if state.dirty_rejection_patterns and state.rejection_patterns is not None:
                    row_id = state.rejection_patterns.get("id") or str(uuid4())
                    await connection.execute(
                        """insert into public.portfolio_rejection_patterns
                           (id,user_id,stats) values ($1::uuid,$2,$3::jsonb)
                           on conflict (id) do update set stats=excluded.stats
                           where public.portfolio_rejection_patterns.user_id=$2""",
                        row_id, uid, json.dumps(state.rejection_patterns.get("stats", {})),
                    )
                if state.dirty_metrics:
                    for record in state.agent_metrics:
                        data = {k: v for k, v in record.items() if k not in {"id", "created_at"}}
                        await connection.execute(
                            """insert into public.portfolio_agent_metrics (user_id,id,data,created_at)
                               values ($1,$2,$3::jsonb,coalesce($4,timezone('utc',now())))
                               on conflict (user_id,id) do update set data=excluded.data""",
                            uid, record["id"], json.dumps(data), None,
                        )
