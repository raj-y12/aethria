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
