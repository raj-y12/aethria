"""Automatic, tenant-scoped authority reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tenant_context import require_user_id


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    missing_legacy_projections: int


class AuthorityReconciler:
    """Check the safety invariant required before canonical reads."""

    def __init__(self, pool: Any):
        self.pool = pool

    async def check_tenant(self, user_id: str) -> ReconciliationResult:
        uid = require_user_id(user_id, context="AuthorityReconciler.check_tenant")
        async with self.pool.acquire() as conn:
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
                uid,
            ) or 0)
        return ReconciliationResult(
            status="green" if missing == 0 else "red",
            missing_legacy_projections=missing,
        )
