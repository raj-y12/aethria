"""Provider-neutral PostgreSQL repository for stage cadence claims."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from tenant_context import require_user_id
from utils.timeutil import ensure_aware


class ScheduleRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def claim_due_jobs(
        self,
        user_id: str,
        intervals: Mapping[str, int],
        *,
        now: datetime | None = None,
    ) -> set[str]:
        uid = require_user_id(user_id, context="ScheduleRepository.claim_due_jobs")
        normalized = {
            str(name).strip(): max(0, int(interval))
            for name, interval in intervals.items()
            if str(name).strip()
        }
        if not normalized:
            return set()
        claim_time = ensure_aware(now) if now is not None else None
        claimed: set[str] = set()
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for job_name in sorted(normalized):
                    row = await connection.fetchrow(
                        """
                        insert into public.agent_job_schedules
                            (user_id, job_name, last_claimed_at)
                        values ($1, $2, coalesce($3::timestamptz, clock_timestamp()))
                        on conflict (user_id, job_name) do update
                          set last_claimed_at = excluded.last_claimed_at
                        where agent_job_schedules.last_claimed_at
                          < excluded.last_claimed_at - make_interval(secs => $4)
                        returning job_name
                        """,
                        uid,
                        job_name,
                        claim_time,
                        normalized[job_name],
                    )
                    if row is not None:
                        claimed.add(str(row["job_name"]))
        return claimed
