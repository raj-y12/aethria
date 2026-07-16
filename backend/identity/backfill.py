"""Restartable, conservative migration from legacy startup projections."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from identity.models import (
    IdentityStatus,
    OpportunityState,
    SourceChannel,
    SourceObservationInput,
)
from identity.normalization import extract_identifier_candidates, normalize_domain
from identity.projection import link_admission_projection
from tenant_context import require_user_id


def _json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def legacy_state_to_opportunity_state(value: Any) -> OpportunityState:
    normalized = str(value or "").strip().upper()
    if normalized in {"YES", "INVEST", "ADVANCE"}:
        return OpportunityState.ADVANCE
    if normalized in {"MAYBE", "MONITOR"}:
        return OpportunityState.MONITOR
    if normalized in {"NO", "PASS"}:
        return OpportunityState.PASS
    return OpportunityState.DISCOVERED


def _legacy_decision(row: Dict[str, Any]) -> Any:
    human = _json(row.get("human_resolution"))
    partner = _json(row.get("partner_info"))
    return (
        human.get("decision")
        or partner.get("recommendation")
        or partner.get("decision")
    )


def legacy_row_to_observation(
    *, user_id: str, row: Dict[str, Any]
) -> SourceObservationInput:
    uid = require_user_id(user_id, context="legacy_row_to_observation")
    scout = _json(row.get("scout_info"))
    partner = _json(row.get("partner_info"))
    human = _json(row.get("human_resolution"))
    resolution = _json(scout.get("company_resolution")) or None
    provider_identifiers = {}
    for key, kind in (
        ("linkedin_url", "linkedin"),
        ("crunchbase_url", "crunchbase"),
        ("dealroom_url", "dealroom"),
        ("yc_url", "yc"),
    ):
        value = (resolution or {}).get(key)
        if value:
            provider_identifiers[kind] = str(value)
    startup_id = str(row.get("startup_id") or "").strip()
    name = str(scout.get("name") or row.get("display_name") or "").strip()
    if not startup_id or not name:
        raise ValueError("legacy startup_id and scout name are required")
    observed_at = row.get("created_at")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    return SourceObservationInput(
        user_id=uid,
        channel=SourceChannel.BACKFILL,
        observed_name=name,
        observed_domain=normalize_domain(
            (resolution or {}).get("website") or scout.get("lookup_website")
        ),
        provider_identifiers=provider_identifiers,
        external_event_key=f"backfill:{startup_id}",
        lookup_id=str(scout.get("lookup_id") or "").strip() or None,
        legacy_startup_id=startup_id,
        source_metadata={
            "source": "legacy_startups_backfill",
            "legacy_scout_payload": scout,
            "legacy_partner_payload": partner,
            "legacy_human_resolution": human,
        },
        resolution_payload=resolution,
        observed_at=observed_at,
    )


class BackfillReport(BaseModel):
    user_id: str
    applied: bool
    rows_processed: int = 0
    resolved: int = 0
    identity_review_required: int = 0
    companies_created: int = 0
    would_resolve: int = 0
    would_require_identity_review: int = 0
    next_cursor: Optional[str] = None
    complete: bool = False
    state_counts: Dict[str, int] = Field(default_factory=dict)


class CanonicalIdentityBackfill:
    def __init__(self, pool: Any, *, repository: Any, service: Any):
        self.pool = pool
        self.repository = repository
        self.service = service

    async def _fetch_batch(
        self, *, user_id: str, after: Optional[str], batch_size: int
    ) -> list[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select user_id, startup_id, scout_info, partner_info,
                       human_resolution, created_at
                from public.startups
                where user_id = $1 and ($2::text is null or startup_id > $2)
                order by startup_id
                limit $3
                """,
                user_id,
                after,
                batch_size,
            )
        return [dict(row) for row in rows]

    async def run_batch(
        self,
        *,
        user_id: str,
        apply: bool = False,
        batch_size: int = 100,
        after: Optional[str] = None,
    ) -> BackfillReport:
        uid = require_user_id(user_id, context="CanonicalIdentityBackfill.run_batch")
        bounded_size = max(1, min(int(batch_size), 500))
        rows = await self._fetch_batch(
            user_id=uid, after=(str(after).strip() if after else None), batch_size=bounded_size
        )
        report = BackfillReport(
            user_id=uid,
            applied=bool(apply),
            rows_processed=len(rows),
            next_cursor=str(rows[-1]["startup_id"]) if rows else after,
            complete=len(rows) < bounded_size,
        )
        for row in rows:
            observation = legacy_row_to_observation(user_id=uid, row=row)
            state = legacy_state_to_opportunity_state(_legacy_decision(row))
            report.state_counts[state.value] = report.state_counts.get(state.value, 0) + 1
            has_verified = any(
                item.verification_status.value == "verified"
                for item in extract_identifier_candidates(observation)
            )
            if not apply:
                if has_verified:
                    report.would_resolve += 1
                else:
                    report.would_require_identity_review += 1
                continue
            admission = await self.service.admit(observation)
            if admission.status is IdentityStatus.RESOLVED and admission.opportunity_id:
                report.resolved += 1
                report.companies_created += int(admission.created)
                await link_admission_projection(
                    self.repository,
                    admission=admission,
                    legacy_startup_id=observation.legacy_startup_id,
                )
                await self.repository.set_opportunity_state(
                    user_id=uid,
                    opportunity_id=admission.opportunity_id,
                    decision_state=state,
                )
            else:
                report.identity_review_required += 1
        return report
