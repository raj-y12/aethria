"""Small asyncpg-backed persistence boundary for Batch 1 JSON state."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from tenant_context import require_user_id

_DOC_TABLES = frozenset({
    "analytics_sector_concentration",
    "portfolio_budgets",
    "meta_prompt_library",
    "meta_scout_weights",
    "meta_calibration_state",
    "meta_cycle_counters",
    "meta_churn_signals",
})
_LIST_TABLES = frozenset({"meta_mutation_log", "meta_reports"})


def _decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass
class Batch1State:
    """In-memory snapshot used by synchronous domain logic after async preload."""

    user_id: str
    documents: dict[tuple[str, str], Any] = field(default_factory=dict)
    lists: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    dirty_documents: set[tuple[str, str]] = field(default_factory=set)
    appended_lists: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def get_document(self, table: str, key: str = "default") -> Any | None:
        if table not in _DOC_TABLES:
            raise ValueError(f"unsupported Batch 1 document table: {table}")
        value = self.documents.get((table, key))
        return copy.deepcopy(value)

    def set_document(self, table: str, data: Any, key: str = "default") -> None:
        if table not in _DOC_TABLES:
            raise ValueError(f"unsupported Batch 1 document table: {table}")
        self.documents[(table, key)] = copy.deepcopy(data)
        self.dirty_documents.add((table, key))

    def get_list(self, table: str) -> list[dict[str, Any]]:
        if table not in _LIST_TABLES:
            raise ValueError(f"unsupported Batch 1 list table: {table}")
        return copy.deepcopy(self.lists.setdefault(table, []))

    def append_list(self, table: str, record: dict[str, Any]) -> str:
        if table not in _LIST_TABLES:
            raise ValueError(f"unsupported Batch 1 list table: {table}")
        item = copy.deepcopy(record)
        item_id = str(item.get("id") or uuid4())
        item["id"] = item_id
        self.lists.setdefault(table, []).append(item)
        self.appended_lists.setdefault(table, []).append(item)
        return item_id


class Batch1Repository:
    """Explicit Batch 1 repository wrapping a shared asyncpg pool."""

    def __init__(self, pool: Any):
        self.pool = pool

    async def load_state(self, user_id: str) -> Batch1State:
        uid = require_user_id(user_id, context="Batch1Repository.load_state")
        state = Batch1State(uid, lists={table: [] for table in _LIST_TABLES})
        async with self.pool.acquire() as connection:
            doc_rows = await connection.fetch(
                """
                select table_name, key, data
                from (
                  select 'analytics_sector_concentration' table_name, key, data from public.analytics_sector_concentration where user_id=$1
                  union all select 'portfolio_budgets', key, data from public.portfolio_budgets where user_id=$1
                  union all select 'meta_prompt_library', key, data from public.meta_prompt_library where user_id=$1
                  union all select 'meta_scout_weights', key, data from public.meta_scout_weights where user_id=$1
                  union all select 'meta_calibration_state', key, data from public.meta_calibration_state where user_id=$1
                  union all select 'meta_cycle_counters', key, data from public.meta_cycle_counters where user_id=$1
                  union all select 'meta_churn_signals', key, data from public.meta_churn_signals where user_id=$1
                ) documents
                """,
                uid,
            )
            list_rows = await connection.fetch(
                """
                select 'meta_mutation_log' table_name, id, data, created_at
                from public.meta_mutation_log where user_id=$1
                union all
                select 'meta_reports', id, data, created_at
                from public.meta_reports where user_id=$1
                order by created_at, id
                """,
                uid,
            )
        for row in doc_rows:
            state.documents[(row["table_name"], row["key"])] = _decode(row["data"])
        for row in list_rows:
            item = _decode(row["data"])
            if not isinstance(item, dict):
                item = {"value": item}
            item.setdefault("id", row["id"])
            state.lists[row["table_name"]].append(item)
        return state

    async def increment_cycle_counter(self, user_id: str, *, key: str = "default") -> int:
        uid = require_user_id(user_id, context="Batch1Repository.increment_cycle_counter")
        return int(await self.pool.fetchval(
            "select public.increment_meta_cycle_counter($1, $2)", uid, key
        ))

    async def persist_state(self, state: Batch1State) -> None:
        uid = require_user_id(state.user_id, context="Batch1Repository.persist_state")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for table, key in sorted(state.dirty_documents):
                    data = json.dumps(state.documents[(table, key)], ensure_ascii=False)
                    await connection.execute(
                        f"""insert into public.{table} (user_id, key, data)
                        values ($1, $2, $3::jsonb)
                        on conflict (user_id, key) do update set data=excluded.data""",
                        uid, key, data,
                    )
                for table, records in state.appended_lists.items():
                    for record in records:
                        created_at = record.get("created_at")
                        if isinstance(created_at, str):
                            try:
                                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            except ValueError:
                                created_at = None
                        await connection.execute(
                            f"""insert into public.{table} (user_id, id, data, created_at)
                            values ($1, $2, $3::jsonb, coalesce($4, timezone('utc', now())))""",
                            uid, str(record["id"]), json.dumps(record, ensure_ascii=False), created_at,
                        )

    async def get_document(self, user_id: str, table: str, *, key: str = "default") -> Any | None:
        state = await self.load_state(user_id)
        return state.get_document(table, key)
