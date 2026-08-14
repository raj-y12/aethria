"""Asyncpg repository for the five owned portfolio collections."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from tenant_context import require_user_id

TABLES = (
    "portfolio_decisions",
    "portfolio_positions",
    "portfolio_rejections",
    "portfolio_watchlist",
    "portfolio_signals",
)


def _decode(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, dict) else {}


@dataclass
class Batch3State:
    user_id: str
    collections: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    dirty_tables: set[str] = field(default_factory=set)

    def get_all(self, table: str) -> list[dict[str, Any]]:
        if table not in TABLES:
            raise ValueError(f"unsupported Batch 3 table: {table}")
        return copy.deepcopy(self.collections.get(table, []))

    def upsert(self, table: str, record: dict[str, Any]) -> str:
        if table not in TABLES:
            raise ValueError(f"unsupported Batch 3 table: {table}")
        item = copy.deepcopy(record)
        record_id = str(item["id"])
        rows = self.collections.setdefault(table, [])
        for index, existing in enumerate(rows):
            if str(existing.get("id")) == record_id:
                item["version"] = int(existing.get("version") or 0) + 1
                rows[index] = item
                self.dirty_tables.add(table)
                return record_id
        rows.append(item)
        self.dirty_tables.add(table)
        return record_id

    def replace(self, table: str, records: list[dict[str, Any]]) -> None:
        if table not in TABLES:
            raise ValueError(f"unsupported Batch 3 table: {table}")
        self.collections[table] = copy.deepcopy(records)
        self.dirty_tables.add(table)


class Batch3Repository:
    def __init__(self, pool):
        self.pool = pool

    async def load_state(self, user_id: str) -> Batch3State:
        uid = require_user_id(user_id, context="Batch3Repository.load_state")
        state = Batch3State(uid, {table: [] for table in TABLES})
        async with self.pool.acquire() as connection:
            for table in TABLES:
                rows = await connection.fetch(
                    f"select id, data from public.{table} where user_id=$1 order by created_at, id", uid
                )
                state.collections[table] = [
                    {"id": row["id"], **_decode(row["data"])} for row in rows
                ]
        return state

    async def persist_state(self, state: Batch3State) -> None:
        uid = require_user_id(state.user_id, context="Batch3Repository.persist_state")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for table in sorted(state.dirty_tables):
                    for record in state.collections.get(table, []):
                        await connection.execute(
                            f"""insert into public.{table} (user_id,id,data)
                                values ($1,$2,$3::jsonb)
                                on conflict (user_id,id) do update set data=excluded.data""",
                            uid, str(record["id"]), json.dumps(record),
                        )
