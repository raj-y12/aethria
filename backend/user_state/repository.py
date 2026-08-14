"""Async repository for the tenant-scoped ``user_state`` row."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from tenant_context import require_user_id


class UserStateRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def get_last_seen_at(self, user_id: str) -> Optional[datetime]:
        uid = require_user_id(user_id, context="UserStateRepository.get_last_seen_at")
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select last_seen_at
                from public.user_state
                where user_id = $1
                """,
                uid,
            )
        if row is None:
            return None
        return row["last_seen_at"]

    async def upsert_last_seen_at(self, user_id: str, last_seen_at: datetime) -> None:
        uid = require_user_id(user_id, context="UserStateRepository.upsert_last_seen_at")
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                insert into public.user_state (user_id, last_seen_at)
                values ($1, $2)
                on conflict (user_id) do update
                set last_seen_at = excluded.last_seen_at
                """,
                uid,
                last_seen_at,
            )
