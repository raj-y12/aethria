"""Async PostgreSQL repository for the tenant-scoped memory document."""

from __future__ import annotations

import json
from typing import Any

from tenant_context import require_user_id


class MemoryRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def get(self, user_id: str, *, key: str = "default") -> Any | None:
        uid = require_user_id(user_id, context="MemoryRepository.get")
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select data
                from public.memory
                where user_id = $1 and key = $2
                """,
                uid,
                key,
            )
        if row is None:
            return None
        data = row["data"]
        return json.loads(data) if isinstance(data, str) else data

    async def upsert(self, user_id: str, data: Any, *, key: str = "default") -> None:
        uid = require_user_id(user_id, context="MemoryRepository.upsert")
        encoded = json.dumps(data)
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                insert into public.memory (user_id, key, data)
                values ($1, $2, $3::jsonb)
                on conflict (user_id, key) do update
                set data = excluded.data
                """,
                uid,
                key,
                encoded,
            )
