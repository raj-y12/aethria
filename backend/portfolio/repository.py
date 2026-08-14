"""Canonical portfolio position persistence."""

import json
from typing import Any, Dict, Optional
from uuid import uuid4

from tenant_context import require_user_id


class PortfolioRepository:
    def __init__(self, pool: Any, *, authority_service: Any = None):
        self.pool = pool
        self.authority_service = authority_service

    async def create_position_on_connection(
        self,
        conn: Any,
        *,
        user_id: str,
        opportunity_id: str,
        company_id: str,
        ruling_id: str,
        rationale: str,
        investor_confidence: float,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="PortfolioRepository.create_position")
        if not str(rationale or "").strip():
            raise ValueError("Investment rationale is required")
        row = await conn.fetchrow(
            """
            insert into public.canonical_portfolio_positions (
              position_id,user_id,opportunity_id,company_id,ruling_id,status,
              entry_rationale,investor_confidence,entered_at,metadata
            ) values ($1,$2,$3,$4,$5,'active',$6,$7,now(),'{}'::jsonb)
            on conflict (user_id, opportunity_id) do update set
              ruling_id=excluded.ruling_id, entry_rationale=excluded.entry_rationale,
              investor_confidence=excluded.investor_confidence, status='active'
            returning *
            """,
            str(uuid4()), uid, opportunity_id, company_id, ruling_id,
            str(rationale).strip(), max(0.0, min(1.0, float(investor_confidence))),
        )
        if row is None:
            raise RuntimeError("Canonical portfolio position upsert returned no row")
        return dict(row)

    async def get_position(self, *, user_id: str, opportunity_id: str) -> Optional[Dict[str, Any]]:
        uid = require_user_id(user_id, context="PortfolioRepository.get_position")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from public.canonical_portfolio_positions where user_id=$1 and opportunity_id=$2",
                uid, opportunity_id,
            )
        return dict(row) if row else None

    async def list_positions(self, *, user_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        uid = require_user_id(user_id, context="PortfolioRepository.list_positions")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select p.*, c.canonical_name, c.canonical_domain,
                       o.legacy_startup_id
                from public.canonical_portfolio_positions p
                join public.companies c on c.user_id=p.user_id and c.company_id=p.company_id
                left join public.opportunities o
                  on o.user_id=p.user_id and o.opportunity_id=p.opportunity_id
                where p.user_id=$1 and p.status='active' order by p.entered_at desc limit $2
                """, uid, max(1, min(int(limit), 200)),
            )
        return [dict(row) for row in rows]

    async def list_decision_history(
        self, *, user_id: str, limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Return canonical rulings alongside tenant-scoped legacy decisions."""
        uid = require_user_id(user_id, context="PortfolioRepository.list_decision_history")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                with canonical_history as (
                    select
                      'canonical:' || hr.ruling_id::text as history_id,
                      o.legacy_startup_id::text as startup_id,
                      o.opportunity_id::text as opportunity_id,
                      c.canonical_name,
                      hr.decision,
                      hr.rationale,
                      hr.created_at as decided_at,
                      hr.decision as recommended_state,
                      'canonical'::text as source,
                      null::text as decision_kind
                    from public.human_rulings hr
                    join public.opportunities o
                      on o.user_id=hr.user_id and o.opportunity_id=hr.opportunity_id
                    join public.companies c
                      on c.user_id=o.user_id and c.company_id=o.company_id
                    where hr.user_id=$1
                ), legacy_history as (
                    select
                      'legacy:' || s.startup_id as history_id,
                      s.startup_id,
                      null::text as opportunity_id,
                      coalesce(s.scout_info->>'name', s.startup_id) as canonical_name,
                      lower(coalesce(
                        s.partner_info->>'recommendation',
                        s.partner_info->>'decision',
                        s.partner_decision
                      )) as decision,
                      coalesce(
                        s.partner_info->>'rationale',
                        s.partner_info->>'reason',
                        ''
                      ) as rationale,
                      s.updated_at as decided_at,
                      null::text as recommended_state,
                      'legacy'::text as source,
                      null::text as decision_kind
                    from public.startups s
                    where s.user_id=$1 and s.partner_info is not null
                ), partner_history as (
                    select
                      'partner:' || pd.id as history_id,
                      pd.data->>'startup_id' as startup_id,
                      null::text as opportunity_id,
                      coalesce(
                        pd.data->>'startup_name',
                        pd.data->'scout_info'->>'name',
                        pd.id
                      ) as canonical_name,
                      lower(coalesce(pd.data->>'decision', pd.data->>'recommendation')) as decision,
                      coalesce(pd.data->>'rationale', pd.data->>'reason', '') as rationale,
                      coalesce((pd.data->>'decided_at')::timestamptz, pd.created_at) as decided_at,
                      pd.data->>'recommended_state' as recommended_state,
                      'partner'::text as source,
                      'partner'::text as decision_kind
                    from public.portfolio_decisions pd
                    where pd.user_id=$1
                )
                select * from (
                    select * from canonical_history
                    union all select * from legacy_history
                    union all select * from partner_history
                ) history
                where decision is not null
                order by decided_at desc nulls last, history_id
                limit $2
                """,
                uid,
                max(1, min(int(limit), 200)),
            )
        return [dict(row) for row in rows]
