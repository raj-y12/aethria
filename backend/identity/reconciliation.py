"""Count-only reconciliation between legacy and canonical identity stores."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tenant_context import require_user_id


class IdentityReconciliationReport(BaseModel):
    user_id: str
    counts: Dict[str, int]
    violations: List[str] = Field(default_factory=list)
    has_violations: bool = False


async def reconcile_identity(
    pool: Any, *, user_id: str, activated_at: Optional[str] = None
) -> IdentityReconciliationReport:
    uid = require_user_id(user_id, context="reconcile_identity")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select
              (select count(*) from public.startups s where s.user_id = $1) as legacy_rows,
              (select count(*) from public.source_observations o where o.user_id = $1) as observations,
              (select count(*) from public.companies c where c.user_id = $1) as companies,
              (select count(*) from public.opportunities p where p.user_id = $1) as opportunities,
              (select count(*)
                 from public.source_observations o
                where o.user_id = $1 and o.legacy_startup_id is not null
                  and not exists (
                    select 1 from public.opportunities p
                    where p.user_id = $1
                      and p.legacy_startup_id = o.legacy_startup_id
                  )) as unlinked_projections,
              (select count(*) from (
                 select identifier_type, normalized_value
                 from public.company_identifiers
                 where user_id = $1 and verification_status = 'verified'
                 group by identifier_type, normalized_value
                 having count(*) > 1
               ) duplicate_identifiers) as duplicate_verified_identifiers,
              (select count(*) from public.identity_resolution_cases c
                where c.user_id = $1 and c.status = 'open') as open_cases,
              (select count(*) from public.source_observations o
                where o.user_id = $1 and o.identity_status = 'resolved'
                  and (
                    o.opportunity_id is null or not exists (
                      select 1 from public.opportunities p
                      where p.user_id = o.user_id
                        and p.opportunity_id = o.opportunity_id
                    )
                  )) as resolved_without_stable_opportunity,
              ((select count(*) from public.opportunities p
                  where p.user_id = $1 and not exists (
                    select 1 from public.companies c
                    where c.user_id = $1 and c.company_id = p.company_id
                  ))
               +
               (select count(*) from public.source_observations o
                  where o.user_id = $1 and o.company_id is not null and not exists (
                    select 1 from public.companies c
                    where c.user_id = $1 and c.company_id = o.company_id
                  ))) as tenant_drift,
              (select count(*) from public.startups s
                where s.user_id = $1
                  and $2::timestamptz is not null
                  and s.created_at >= $2::timestamptz
                  and not exists (
                    select 1 from public.opportunities p
                    where p.user_id = $1
                      and p.legacy_startup_id::text = s.startup_id
                  )) as authoritative_legacy_only_after_activation
            """,
            uid,
            activated_at,
        )
    counts = {key: int(value or 0) for key, value in dict(row or {}).items()}
    guarded = (
        "duplicate_verified_identifiers",
        "tenant_drift",
        "authoritative_legacy_only_after_activation",
        "resolved_without_stable_opportunity",
    )
    violations = [key for key in guarded if counts.get(key, 0) > 0]
    return IdentityReconciliationReport(
        user_id=uid,
        counts=counts,
        violations=violations,
        has_violations=bool(violations),
    )
