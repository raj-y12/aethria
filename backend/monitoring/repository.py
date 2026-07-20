"""Tenant-safe lifecycle, refresh-budget, and material-change repository."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import uuid4

from env_config import get_float
from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
from evaluation_v2.service import materiality_digest, snapshot_claims
from jobs.models import AgentJob, EvidenceRefreshPayload, JobStatus, JobType
from monitoring.models import (
    BudgetReservationRecord,
    RefreshReason,
    RefreshRequest,
    ReservationStatus,
    ServiceLevel,
)
from monitoring.service import can_auto_refresh, material_change
from tenant_context import require_user_id
from utils.timeutil import utcnow
from utils.db_rows import db_row


class RefreshBudgetExceeded(RuntimeError):
    pass


class RefreshNotPermitted(RuntimeError):
    pass


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _job(row: Any) -> AgentJob:
    payload = db_row(row)
    payload["payload"] = _json(payload.get("payload"), {})
    return AgentJob.model_validate(payload)


def _reservation(row: Any) -> BudgetReservationRecord:
    payload = db_row(row)
    payload["providers"] = _json(payload.get("providers"), [])
    return BudgetReservationRecord.model_validate(payload)


class MonitoringRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def reserve_and_enqueue(
        self, request: RefreshRequest
    ) -> tuple[AgentJob, BudgetReservationRecord]:
        uid = require_user_id(request.user_id, context="MonitoringRepository.reserve_and_enqueue")
        now = utcnow()
        deadline = request.envelope.deadline_at or (now + timedelta(minutes=15))
        expires_at = max(now + timedelta(minutes=5), deadline + timedelta(minutes=5))
        reservation_id = str(uuid4())
        job = AgentJob(
            user_id=uid,
            job_type=JobType.EVIDENCE_REFRESH,
            idempotency_key=f"evidence-refresh:{request.request_key}",
            payload=EvidenceRefreshPayload(
                user_id=uid,
                opportunity_id=request.opportunity_id,
                reason=request.reason.value,
                budget_reservation_id=reservation_id,
            ),
            priority=10 if request.reason is RefreshReason.HUMAN_REQUEST else 0,
        )
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                opportunity = await conn.fetchrow(
                    """
                    select opportunity_id, service_level from public.opportunities
                    where user_id=$1 and opportunity_id=$2 for update
                    """,
                    uid,
                    request.opportunity_id,
                )
                if opportunity is None:
                    raise LookupError("Opportunity not found for tenant")
                level = ServiceLevel(int(opportunity["service_level"]))
                if not can_auto_refresh(level, request.reason):
                    raise RefreshNotPermitted(
                        f"{request.reason.value} is not permitted at service level {int(level)}"
                    )

                existing_job_row = await conn.fetchrow(
                    "select * from public.agent_jobs where user_id=$1 and idempotency_key=$2",
                    uid,
                    job.idempotency_key,
                )
                if existing_job_row is not None:
                    existing_job = _job(existing_job_row)
                    existing_reservation_row = await conn.fetchrow(
                        """
                        select * from public.budget_reservations
                        where user_id=$1 and job_id=$2
                        """,
                        uid,
                        existing_job.job_id,
                    )
                    if existing_reservation_row is None:
                        raise RuntimeError("Existing refresh job has no budget reservation")
                    return existing_job, _reservation(existing_reservation_row)

                reserved = await conn.fetchval(
                    """
                    select coalesce(sum(estimated_cost_usd), 0)
                    from public.budget_reservations
                    where user_id=$1
                      and created_at >= date_trunc('day', now())
                      and status='reserved' and expires_at > now()
                    """,
                    uid,
                )
                settled = await conn.fetchval(
                    """
                    select coalesce(sum(actual_cost_usd), 0)
                    from public.budget_reservations
                    where user_id=$1
                      and created_at >= date_trunc('day', now())
                      and status='settled'
                    """,
                    uid,
                )
                projected = float(reserved or 0) + float(settled or 0) + request.envelope.estimated_cost_usd
                if projected > get_float("MONITOR_DAILY_BUDGET_USD"):
                    raise RefreshBudgetExceeded("Tenant daily refresh budget is exhausted")

                job_row = await conn.fetchrow(
                    """
                    insert into public.agent_jobs (
                      job_id,user_id,job_type,idempotency_key,payload,status,priority,
                      attempts,max_attempts,next_attempt_at,pipeline_run_id,accepted_at,
                      created_at,updated_at
                    ) values ($1,$2,$3,$4,$5::jsonb,$6,$7,0,$8,$9,$10,$11,$12,$12)
                    returning *
                    """,
                    job.job_id,
                    uid,
                    job.job_type.value,
                    job.idempotency_key,
                    json.dumps(job.payload.model_dump(mode="json")),
                    job.status.value,
                    job.priority,
                    job.max_attempts,
                    job.next_attempt_at,
                    job.pipeline_run_id,
                    job.accepted_at,
                    job.created_at,
                )
                reservation_row = await conn.fetchrow(
                    """
                    insert into public.budget_reservations (
                      budget_reservation_id,user_id,opportunity_id,job_id,reason,
                      service_level,max_search_queries,max_artifacts,max_model_tokens,
                      estimated_cost_usd,providers,deadline_at,status,expires_at,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,'reserved',$13,$14)
                    returning *
                    """,
                    reservation_id,
                    uid,
                    request.opportunity_id,
                    job.job_id,
                    request.reason.value,
                    int(level),
                    request.envelope.max_search_queries,
                    request.envelope.max_artifacts,
                    request.envelope.max_model_tokens,
                    request.envelope.estimated_cost_usd,
                    json.dumps(request.envelope.providers),
                    deadline,
                    expires_at,
                    now,
                )
                await conn.execute(
                    """
                    insert into public.domain_outbox (
                      event_id,user_id,aggregate_type,aggregate_id,event_type,
                      event_version,payload,publication_attempts,next_attempt_at,created_at
                    ) values ($1,$2,'agent_job',$3,'agent_job.accepted',1,$4::jsonb,0,now(),now())
                    """,
                    str(uuid4()),
                    uid,
                    job.job_id,
                    json.dumps({"job_id": job.job_id, "job_type": job.job_type.value, "status": "queued"}),
                )
                await conn.execute("select pg_notify('aethria_agent_jobs', $1)", job.job_id)
                return _job(job_row), _reservation(reservation_row)

    async def check_material_change(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        job_id: str,
        reason: RefreshReason | str,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="MonitoringRepository.check_material_change")
        trigger = RefreshReason(reason)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                opportunity = await conn.fetchrow(
                    """
                    select current_evaluation_id from public.opportunities
                    where user_id=$1 and opportunity_id=$2
                    """,
                    uid,
                    opportunity_id,
                )
                if opportunity is None:
                    raise LookupError("Opportunity not found for tenant")
                previous_hash: Optional[str] = None
                if opportunity.get("current_evaluation_id"):
                    previous_evaluation = await conn.fetchrow(
                        """
                        select evidence_materiality_digest, claim_snapshot
                        from public.evaluation_runs
                        where user_id=$1 and evaluation_id=$2
                        """,
                        uid,
                        opportunity["current_evaluation_id"],
                    )
                    if previous_evaluation is not None:
                        previous_hash = str(
                            previous_evaluation.get("evidence_materiality_digest")
                            or ""
                        ).strip() or None
                        if previous_hash is None:
                            previous_snapshot = _json(
                                previous_evaluation.get("claim_snapshot"), []
                            )
                            previous_hash = materiality_digest(previous_snapshot)
                claims = [dict(row) for row in await conn.fetch(
                    """
                    select * from public.claims
                    where user_id=$1 and opportunity_id=$2 and status in ('current','contradicted')
                    """,
                    uid,
                    opportunity_id,
                )]
                for claim in claims:
                    claim["normalized_value"] = _json(claim.get("normalized_value"), {})
                links = [dict(row) for row in await conn.fetch(
                    enriched_claim_evidence_sql(),
                    uid,
                    opportunity_id,
                )]
                current_snapshot, _ = snapshot_claims(claims, links)
                current_hash = materiality_digest(current_snapshot)
                changed = material_change(previous_hash, current_hash)
                row = await conn.fetchrow(
                    """
                    insert into public.material_change_checks (
                      material_change_check_id,user_id,opportunity_id,job_id,reason,
                      previous_materiality_digest,current_materiality_digest,
                      material_change,detail,checked_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,now()) returning *
                    """,
                    str(uuid4()),
                    uid,
                    opportunity_id,
                    job_id,
                    trigger.value,
                    previous_hash,
                    current_hash,
                    changed,
                    json.dumps({"claim_count": len(claims)}),
                )
                payload = dict(row)
                payload["detail"] = _json(payload.get("detail"), {})
                payload["previous_materiality_digest"] = previous_hash
                payload["current_materiality_digest"] = current_hash
                # Compatibility aliases for callers deployed before the explicit
                # materiality naming cutover.
                payload["previous_snapshot_hash"] = previous_hash
                payload["current_snapshot_hash"] = current_hash
                return payload

    async def current_missing_evidence(self, *, user_id: str, opportunity_id: str) -> list[str]:
        uid = require_user_id(user_id, context="MonitoringRepository.current_missing_evidence")
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                select r.missing_information from public.opportunities o
                left join public.recommendations r
                  on r.user_id=o.user_id and r.recommendation_id=o.current_recommendation_id
                where o.user_id=$1 and o.opportunity_id=$2
                """,
                uid,
                opportunity_id,
            )
        return [str(item) for item in _json(value, [])][:50]

    async def settle(
        self,
        *,
        user_id: str,
        budget_reservation_id: str,
        actual_cost_usd: float,
    ) -> BudgetReservationRecord:
        uid = require_user_id(user_id, context="MonitoringRepository.settle")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.budget_reservations
                set status='settled', actual_cost_usd=least(estimated_cost_usd,$3), settled_at=now()
                where user_id=$1 and budget_reservation_id=$2 and status='reserved'
                returning *
                """,
                uid,
                budget_reservation_id,
                max(0.0, float(actual_cost_usd)),
            )
        if row is None:
            raise LookupError("Active budget reservation not found for tenant")
        return _reservation(row)

    async def set_service_level(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        service_level: ServiceLevel | int,
        lifecycle_reason: str,
        next_review_at: Optional[Any] = None,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="MonitoringRepository.set_service_level")
        level = ServiceLevel(service_level)
        reason = str(lifecycle_reason or "").strip()
        if not reason:
            raise ValueError("lifecycle_reason is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                previous = await conn.fetchrow(
                    """
                    select service_level from public.opportunities
                    where user_id=$1 and opportunity_id=$2 for update
                    """,
                    uid,
                    opportunity_id,
                )
                if previous is None:
                    raise LookupError("Opportunity not found for tenant")
                row = await conn.fetchrow(
                    """
                    update public.opportunities
                    set service_level=$3,lifecycle_reason=$4,next_review_at=$5,updated_at=now()
                    where user_id=$1 and opportunity_id=$2 returning *
                    """,
                    uid,
                    opportunity_id,
                    int(level),
                    reason,
                    next_review_at,
                )
                if int(level) < int(previous["service_level"]):
                    await conn.execute(
                        """
                        with released as (
                          update public.budget_reservations
                          set status='released',settled_at=now(),actual_cost_usd=0
                          where user_id=$1 and opportunity_id=$2 and status='reserved'
                          returning job_id
                        )
                        update public.agent_jobs j set status='cancelled',completed_at=now()
                        from released r where j.user_id=$1 and j.job_id=r.job_id and j.status='queued'
                        """,
                        uid,
                        opportunity_id,
                    )
                return dict(row)

    async def get_status(self, *, user_id: str, opportunity_id: str) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="MonitoringRepository.get_status")
        async with self.pool.acquire() as conn:
            opportunity = await conn.fetchrow(
                """
                select opportunity_id,decision_state,service_level,next_review_at,lifecycle_reason,updated_at
                from public.opportunities where user_id=$1 and opportunity_id=$2
                """,
                uid,
                opportunity_id,
            )
            if opportunity is None:
                raise LookupError("Opportunity not found for tenant")
            reservations = await conn.fetch(
                """
                select * from public.budget_reservations
                where user_id=$1 and opportunity_id=$2 order by created_at desc limit 20
                """,
                uid,
                opportunity_id,
            )
            checks = await conn.fetch(
                """
                select * from public.material_change_checks
                where user_id=$1 and opportunity_id=$2 order by checked_at desc limit 20
                """,
                uid,
                opportunity_id,
            )
        return {
            "opportunity": dict(opportunity),
            "budget_reservations": [dict(_reservation(row).model_dump(mode="json")) for row in reservations],
            "material_change_checks": [
                {**dict(row), "detail": _json(row.get("detail"), {})} for row in checks
            ],
        }
