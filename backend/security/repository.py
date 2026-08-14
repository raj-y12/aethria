"""Provider-neutral PostgreSQL repository for counters and short-lived locks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

class SecurityRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def check_rate_limit(
        self, key: str, *, window_seconds: int
    ) -> tuple[int, datetime]:
        if not str(key).strip():
            raise ValueError("security rate-limit key is required")
        if int(window_seconds) <= 0:
            raise ValueError("security rate-limit window must be positive")
        row = await self.pool.fetchrow(
            """
            with boundary as (
                select
                    clock_timestamp() as now,
                    to_timestamp(
                        floor(extract(epoch from clock_timestamp()) / $2) * $2
                    ) as window_start
            )
            insert into public.security_limits as sl
                (key, kind, count, window_seconds, expires_at, lock_owner_token, updated_at)
            select $1, 'rate', 1, $2,
                   boundary.window_start + make_interval(secs => $2),
                   null, boundary.now
              from boundary
            on conflict (key) do update
              set kind = 'rate',
                  count = case when sl.expires_at <= clock_timestamp()
                               then 1 else sl.count + 1 end,
                  window_seconds = excluded.window_seconds,
                  expires_at = case when sl.expires_at <= clock_timestamp()
                                    then excluded.expires_at else sl.expires_at end,
                  lock_owner_token = null,
                  updated_at = clock_timestamp()
            returning count, expires_at
            """,
            str(key),
            int(window_seconds),
        )
        if row is None:
            raise RuntimeError("security rate-limit update returned no row")
        return int(row["count"]), row["expires_at"]

    async def acquire_lock(
        self, key: str, *, ttl_seconds: int, owner_token: str
    ) -> bool:
        if not str(key).strip():
            raise ValueError("security lock key is required")
        if int(ttl_seconds) <= 0:
            raise ValueError("security lock ttl must be positive")
        if not str(owner_token).strip():
            raise ValueError("security lock owner token is required")
        row = await self.pool.fetchrow(
            """
            insert into public.security_limits as sl
                (key, kind, count, expires_at, lock_owner_token, updated_at)
            values ($1, 'lock', 1,
                    clock_timestamp() + make_interval(secs => $2), $3,
                    clock_timestamp())
            on conflict (key) do update
              set kind = 'lock',
                  count = 1,
                  expires_at = excluded.expires_at,
                  lock_owner_token = excluded.lock_owner_token,
                  updated_at = excluded.updated_at
            where sl.kind <> 'lock' or sl.expires_at <= clock_timestamp()
            returning key
            """,
            str(key),
            int(ttl_seconds),
            str(owner_token),
        )
        return row is not None

    async def release_lock(self, key: str, *, owner_token: str) -> bool:
        if not str(key).strip() or not str(owner_token).strip():
            return False
        result = await self.pool.execute(
            """
            delete from public.security_limits
             where key = $1
               and kind = 'lock'
               and lock_owner_token = $2
            """,
            str(key),
            str(owner_token),
        )
        return result.endswith(" 1")
