"""Transactional asyncpg repository for AgentJob leases and domain outbox."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import metrics
from jobs.models import (
    AgentJob,
    CheckpointStatus,
    DomainOutboxEvent,
    JobCheckpoint,
    JobStatus,
)
from tenant_context import require_user_id
from utils.timeutil import utcnow
from utils.db_rows import db_row


def _json_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value


def _job_from_row(row: Any) -> Optional[AgentJob]:
    if row is None:
        return None
    payload = db_row(row)
    payload["payload"] = _json_payload(payload.get("payload"))
    return AgentJob.model_validate(payload)


def _checkpoint_from_row(row: Any) -> Optional[JobCheckpoint]:
    if row is None:
        return None
    payload = db_row(row)
    payload["output_metadata"] = _json_payload(payload.get("output_metadata"))
    return JobCheckpoint.model_validate(payload)


def _outbox_from_row(row: Any) -> Optional[DomainOutboxEvent]:
    if row is None:
        return None
    payload = db_row(row)
    payload["payload"] = _json_payload(payload.get("payload"))
    return DomainOutboxEvent.model_validate(payload)


class DurableJobRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def _insert_outbox(
        self,
        conn: Any,
        *,
        user_id: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id, user_id, aggregate_type, aggregate_id, event_type,
              event_version, payload, publication_attempts, next_attempt_at, created_at
            ) values ($1, $2, 'agent_job', $3, $4, 1, $5::jsonb, 0, now(), now())
            on conflict (event_id) do nothing
            """,
            str(uuid4()),
            user_id,
            aggregate_id,
            event_type,
            json.dumps(payload),
        )

    async def enqueue(self, job: AgentJob) -> AgentJob:
        require_user_id(job.user_id, context="DurableJobRepository.enqueue")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    insert into public.agent_jobs (
                      job_id, user_id, job_type, idempotency_key, payload, status,
                      priority, attempts, max_attempts, lease_owner, lease_expires_at,
                      heartbeat_at, next_attempt_at, pipeline_run_id, last_error,
                      accepted_at, started_at, completed_at, created_at, updated_at
                    ) values (
                      $1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11,
                      $12, $13, $14, $15, $16, $17, $18, $19, $20
                    )
                    on conflict (user_id, idempotency_key) do nothing
                    returning *
                    """,
                    job.job_id,
                    job.user_id,
                    job.job_type.value,
                    job.idempotency_key,
                    json.dumps(job.payload.model_dump(mode="json")),
                    job.status.value,
                    job.priority,
                    job.attempts,
                    job.max_attempts,
                    job.lease_owner,
                    job.lease_expires_at,
                    job.heartbeat_at,
                    job.next_attempt_at,
                    job.pipeline_run_id,
                    job.last_error,
                    job.accepted_at,
                    job.started_at,
                    job.completed_at,
                    job.created_at,
                    job.updated_at,
                )
                inserted = row is not None
                if row is None:
                    row = await conn.fetchrow(
                        """
                        select * from public.agent_jobs
                        where user_id = $1 and idempotency_key = $2
                        """,
                        job.user_id,
                        job.idempotency_key,
                    )
                if row is None:
                    raise RuntimeError("Idempotent job enqueue returned no row")
                accepted = _job_from_row(row)
                if inserted:
                    await self._insert_outbox(
                        conn,
                        user_id=accepted.user_id,
                        aggregate_id=accepted.job_id,
                        event_type="agent_job.accepted",
                        payload={
                            "job_id": accepted.job_id,
                            "job_type": accepted.job_type.value,
                            "status": accepted.status.value,
                        },
                    )
                    await conn.execute(
                        "select pg_notify('aethria_agent_jobs', $1)", accepted.job_id
                    )
                    metrics.inc_durable_job(
                        job_type=accepted.job_type.value, transition="accepted"
                    )
                return accepted

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> Optional[AgentJob]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    with candidate as (
                      select j.*
                      from public.agent_jobs j
                      where (
                        (j.status in ('queued', 'retry_wait') and j.next_attempt_at <= now())
                        or (j.status = 'running' and j.lease_expires_at <= now())
                      )
                      and j.attempts < j.max_attempts
                      order by j.priority desc, j.created_at
                      for update skip locked
                      limit 1
                    )
                    update public.agent_jobs as jobs
                    set status = 'running',
                        attempts = candidate.attempts + 1,
                        lease_owner = $1,
                        lease_expires_at = now() + ($2 * interval '1 second'),
                        heartbeat_at = now(),
                        started_at = coalesce(jobs.started_at, now()),
                        last_error = null,
                        block_code = null,
                        block_detail = null,
                        recovery_action = null
                    from candidate
                    where jobs.job_id = candidate.job_id
                    returning jobs.*
                    """,
                    worker_id,
                    max(1, int(lease_seconds)),
                )
                claimed = _job_from_row(row)
                if claimed is not None:
                    metrics.inc_durable_job(
                        job_type=claimed.job_type.value, transition="claimed"
                    )
                return claimed

    async def dead_letter_exhausted_leases(self) -> int:
        """Close final-attempt jobs whose worker died after the lease expired."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    update public.agent_jobs
                    set status = 'dead_letter', completed_at = now(),
                        lease_owner = null, lease_expires_at = null,
                        last_error = coalesce(
                          last_error,
                          'Worker lease expired after the final attempt'
                        )
                    where status = 'running'
                      and lease_expires_at <= now()
                      and attempts >= max_attempts
                    returning job_id, user_id, job_type
                    """
                )
                for row in rows:
                    await self._insert_outbox(
                        conn,
                        user_id=str(row["user_id"]),
                        aggregate_id=str(row["job_id"]),
                        event_type="agent_job.dead_lettered",
                        payload={
                            "job_id": str(row["job_id"]),
                            "status": "dead_letter",
                        },
                    )
                    metrics.inc_durable_job(
                        job_type=str(row["job_type"]),
                        transition="dead_lettered",
                    )
                return len(rows)

    async def heartbeat(
        self,
        *,
        user_id: str,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        uid = require_user_id(user_id, context="DurableJobRepository.heartbeat")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.agent_jobs
                set heartbeat_at = now(),
                    lease_expires_at = now() + ($4 * interval '1 second')
                where job_id = $1 and user_id = $2 and lease_owner = $3
                  and status = 'running'
                returning job_id
                """,
                job_id,
                uid,
                worker_id,
                max(1, int(lease_seconds)),
            )
            return row is not None

    async def write_checkpoint(
        self,
        *,
        user_id: str,
        job_id: str,
        pipeline_run_id: str,
        stage: str,
        attempt: int,
        status: CheckpointStatus | str,
        output_metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> JobCheckpoint:
        uid = require_user_id(user_id, context="DurableJobRepository.checkpoint")
        status_value = CheckpointStatus(status).value
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into public.agent_job_checkpoints (
                  checkpoint_id, job_id, user_id, pipeline_run_id, stage, attempt,
                  status, output_metadata, error, created_at, updated_at
                ) values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, now(), now())
                on conflict (user_id, job_id, stage, attempt, status)
                do update set output_metadata = excluded.output_metadata,
                              error = excluded.error,
                              updated_at = now()
                returning *
                """,
                str(uuid4()),
                job_id,
                uid,
                pipeline_run_id,
                str(stage).strip(),
                int(attempt),
                status_value,
                json.dumps(output_metadata or {}),
                (error or "")[:2000] or None,
            )
            checkpoint = _checkpoint_from_row(row)
            if checkpoint is None:
                raise RuntimeError("Checkpoint upsert returned no row")
            return checkpoint

    async def succeed(
        self, *, user_id: str, job_id: str, worker_id: str
    ) -> bool:
        uid = require_user_id(user_id, context="DurableJobRepository.succeed")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.agent_jobs
                    set status = 'succeeded', completed_at = now(),
                        lease_owner = null, lease_expires_at = null, heartbeat_at = now()
                    where job_id = $1 and user_id = $2 and lease_owner = $3
                      and status = 'running'
                    returning job_id, job_type
                    """,
                    job_id,
                    uid,
                    worker_id,
                )
                if row is None:
                    return False
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_id=job_id,
                    event_type="agent_job.succeeded",
                    payload={"job_id": job_id, "status": "succeeded"},
                )
                metrics.inc_durable_job(
                    job_type=str(row["job_type"]), transition="completed"
                )
                return True

    async def retry(
        self,
        *,
        user_id: str,
        job_id: str,
        worker_id: str,
        error: str,
        base_delay_seconds: int = 5,
    ) -> Optional[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.retry")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.agent_jobs
                    set status = case when attempts >= max_attempts
                                      then 'dead_letter' else 'retry_wait' end,
                        next_attempt_at = case when attempts >= max_attempts then now()
                          else now() + ($5 * power(2, greatest(attempts - 1, 0)) * interval '1 second') end,
                        last_error = $4,
                        completed_at = case when attempts >= max_attempts then now() else null end,
                        lease_owner = null, lease_expires_at = null
                    where job_id = $1 and user_id = $2 and lease_owner = $3
                      and status = 'running'
                    returning *
                    """,
                    job_id,
                    uid,
                    worker_id,
                    str(error or "")[:2000],
                    max(1, int(base_delay_seconds)),
                )
                job = _job_from_row(row)
                if job and job.status is JobStatus.DEAD_LETTER:
                    await self._insert_outbox(
                        conn,
                        user_id=uid,
                        aggregate_id=job_id,
                        event_type="agent_job.dead_lettered",
                        payload={"job_id": job_id, "status": "dead_letter"},
                    )
                    metrics.inc_durable_job(
                        job_type=job.job_type.value, transition="dead_lettered"
                    )
                elif job is not None:
                    metrics.inc_durable_job(
                        job_type=job.job_type.value, transition="retried"
                    )
                return job

    async def fail(
        self, *, user_id: str, job_id: str, worker_id: str, error: str
    ) -> Optional[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.fail")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.agent_jobs
                set status = 'failed', last_error = $4, completed_at = now(),
                    lease_owner = null, lease_expires_at = null
                where job_id = $1 and user_id = $2 and lease_owner = $3
                  and status = 'running'
                returning *
                """,
                job_id,
                uid,
                worker_id,
                str(error or "")[:2000],
            )
            return _job_from_row(row)

    async def block(
        self,
        *,
        user_id: str,
        job_id: str,
        worker_id: str,
        code: str,
        detail: str,
        recovery_action: str,
    ) -> Optional[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.block")
        safe_code = str(code or "").strip().lower()[:80]
        if not safe_code or not safe_code.replace("_", "a").isalnum():
            raise ValueError("block code must be lowercase snake_case")
        safe_detail = str(detail or "").strip()[:1000]
        safe_recovery = str(recovery_action or "").strip()[:1000]
        if not safe_recovery:
            raise ValueError("recovery_action is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.agent_jobs
                    set status = 'blocked',
                        attempts = greatest(attempts - 1, 0),
                        block_code = $4,
                        block_detail = $5,
                        recovery_action = $6,
                        last_error = null,
                        completed_at = null,
                        lease_owner = null,
                        lease_expires_at = null,
                        heartbeat_at = now()
                    where job_id = $1 and user_id = $2 and lease_owner = $3
                      and status = 'running'
                    returning *
                    """,
                    job_id,
                    uid,
                    worker_id,
                    safe_code,
                    safe_detail,
                    safe_recovery,
                )
                job = _job_from_row(row)
                if job is None:
                    return None
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_id=job_id,
                    event_type="agent_job.blocked",
                    payload={
                        "job_id": job_id,
                        "status": "blocked",
                        "code": safe_code,
                        "recovery_action": safe_recovery,
                    },
                )
                metrics.inc_durable_job(
                    job_type=job.job_type.value, transition="blocked"
                )
                return job

    async def cancel(self, *, user_id: str, job_id: str) -> Optional[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.cancel")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.agent_jobs
                    set status = 'cancelled', completed_at = coalesce(completed_at, now()),
                        lease_owner = null, lease_expires_at = null
                    where job_id = $1 and user_id = $2
                      and status not in ('succeeded', 'cancelled')
                    returning *
                    """,
                    job_id,
                    uid,
                )
                transitioned = row is not None
                if row is None:
                    row = await conn.fetchrow(
                        "select * from public.agent_jobs where job_id = $1 and user_id = $2",
                        job_id,
                        uid,
                    )
                job = _job_from_row(row)
                if transitioned and job and job.status is JobStatus.CANCELLED:
                    await self._insert_outbox(
                        conn,
                        user_id=uid,
                        aggregate_id=job_id,
                        event_type="agent_job.cancelled",
                        payload={"job_id": job_id, "status": "cancelled"},
                    )
                    metrics.inc_durable_job(
                        job_type=job.job_type.value, transition="cancelled"
                    )
                return job

    async def requeue(self, *, user_id: str, job_id: str) -> Optional[AgentJob]:
        """Grant one explicit operator retry on the same accepted job."""
        uid = require_user_id(user_id, context="DurableJobRepository.requeue")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.agent_jobs
                    set status = 'queued',
                        max_attempts = greatest(max_attempts, attempts + 1),
                        next_attempt_at = now(),
                        last_error = null,
                        block_code = null,
                        block_detail = null,
                        recovery_action = null,
                        completed_at = null,
                        lease_owner = null,
                        lease_expires_at = null,
                        heartbeat_at = null
                    where job_id = $1 and user_id = $2
                      and status in ('failed', 'dead_letter', 'blocked', 'retry_wait')
                    returning *
                    """,
                    job_id,
                    uid,
                )
                job = _job_from_row(row)
                if job is None:
                    return None
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_id=job_id,
                    event_type="agent_job.requeued",
                    payload={"job_id": job_id, "status": "queued"},
                )
                await conn.execute(
                    "select pg_notify('aethria_agent_jobs', $1)", job_id
                )
                metrics.inc_durable_job(
                    job_type=job.job_type.value, transition="retried"
                )
                return job

    async def get_job(self, *, user_id: str, job_id: str) -> Optional[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.get_job")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from public.agent_jobs where job_id = $1 and user_id = $2",
                job_id,
                uid,
            )
            return _job_from_row(row)

    async def get_by_idempotency_key(
        self, *, user_id: str, idempotency_key: str
    ) -> Optional[AgentJob]:
        uid = require_user_id(
            user_id, context="DurableJobRepository.get_by_idempotency_key"
        )
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key is required")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.agent_jobs
                where user_id = $1 and idempotency_key = $2
                """,
                uid,
                key,
            )
            return _job_from_row(row)

    async def list_jobs(
        self,
        *,
        user_id: str,
        statuses: Optional[List[JobStatus | str]] = None,
        limit: int = 50,
    ) -> List[AgentJob]:
        uid = require_user_id(user_id, context="DurableJobRepository.list_jobs")
        status_values = [JobStatus(value).value for value in (statuses or list(JobStatus))]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.agent_jobs
                where user_id = $1 and status = any($2::text[])
                order by created_at desc limit $3
                """,
                uid,
                status_values,
                max(1, min(int(limit), 200)),
            )
            return [job for row in rows if (job := _job_from_row(row)) is not None]

    async def queue_depths(self) -> Dict[str, int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select job_type, status, count(*)::integer as count
                from public.agent_jobs
                where status in ('queued', 'running', 'retry_wait', 'blocked', 'dead_letter')
                group by job_type, status
                union all
                select 'outbox' as job_type, 'pending' as status,
                       count(*)::integer as count
                from public.domain_outbox
                where published_at is null
                """
            )
            return {
                f"{row['job_type']}:{row['status']}": int(row["count"])
                for row in rows
            }

    async def claim_outbox_batch(
        self, *, limit: int = 50, visibility_seconds: int = 30
    ) -> List[DomainOutboxEvent]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    with candidates as (
                      select event_id from public.domain_outbox
                      where published_at is null and next_attempt_at <= now()
                      order by created_at
                      for update skip locked
                      limit $1
                    )
                    update public.domain_outbox as outbox
                    set publication_attempts = outbox.publication_attempts + 1,
                        next_attempt_at = now() + ($2 * interval '1 second')
                    from candidates
                    where outbox.event_id = candidates.event_id
                    returning outbox.*
                    """,
                    max(1, min(int(limit), 200)),
                    max(1, int(visibility_seconds)),
                )
                return [
                    event for row in rows if (event := _outbox_from_row(row)) is not None
                ]

    async def mark_outbox_published(self, *, event_id: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.domain_outbox
                set published_at = now(), last_error = null
                where event_id = $1 and published_at is null
                returning event_id
                """,
                event_id,
            )
            return row is not None

    async def mark_outbox_failed(self, *, event_id: str, error: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.domain_outbox
                set last_error = $2
                where event_id = $1 and published_at is null
                returning event_id
                """,
                event_id,
                str(error or "")[:2000],
            )
            return row is not None
