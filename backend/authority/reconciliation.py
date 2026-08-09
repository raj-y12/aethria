"""Live authority reconciliation check, run inline before clearing a kill switch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    missing_legacy_projections: int


async def check_tenant_reconciliation(conn: Any, user_id: str) -> ReconciliationResult:
    """Check the safety invariant required before an authority kill-switch re-arm.

    Runs on the caller's connection so it can execute inside the same
    transaction as the re-arm write, instead of a separate background pass
    with a staleness window.
    """
    missing = int(await conn.fetchval(
        """
        select count(*)
        from public.opportunities o
        left join public.startups s
          on s.user_id=o.user_id
         and s.startup_id=o.legacy_startup_id::text
        where o.user_id=$1
          and o.legacy_startup_id is not null
          and s.startup_id is null
        """,
        user_id,
    ) or 0)
    return ReconciliationResult(
        status="green" if missing == 0 else "red",
        missing_legacy_projections=missing,
    )
