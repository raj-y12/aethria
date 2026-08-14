"""Atomic tenant-scoped schedule claims for reconstructed pipeline engines."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Set

from schedule_repository import ScheduleRepository
from tenant_context import require_user_id
from utils.timeutil import ensure_aware


_schedule_repository: ScheduleRepository | None = None


def configure_schedule_repository(pool: Any | None) -> None:
    global _schedule_repository
    _schedule_repository = ScheduleRepository(pool) if pool is not None else None


async def claim_due_jobs(
    user_id: str,
    intervals: Mapping[str, int],
    *,
    now: Optional[datetime] = None,
) -> Set[str]:
    """Atomically claim and return tenant jobs whose interval has elapsed."""
    uid = require_user_id(user_id, context="claim_due_jobs")
    normalized = {}
    for raw_name, raw_interval in intervals.items():
        name = str(raw_name).strip()
        if name:
            normalized[name] = max(0, int(raw_interval))
    if not normalized:
        return set()

    if _schedule_repository is None:
        raise RuntimeError("schedule_repository_unavailable")
    return await _schedule_repository.claim_due_jobs(uid, normalized, now=now)
