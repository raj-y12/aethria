"""Tenant-scoped status, retry, and cancellation controls for durable work."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from jobs.lookup_outcomes import (
    LookupOutcomeStoreUnavailable,
)
from jobs.models import (
    AgentJob,
    JobCancellationDisposition,
    JobStatus,
)
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_RETRYABLE = {
    JobStatus.FAILED,
    JobStatus.DEAD_LETTER,
    JobStatus.BLOCKED,
    JobStatus.RETRY_WAIT,
}

_PUBLIC_FAILURE_CODES = frozenset(
    {
        "cluster_analysis_failed",
        "lookup_attempt_failed",
        "lookup_engine_initialization_failed",
        "meta_cycle_failed",
        "partner_candidate_failures",
        "partner_stage_failed",
        "pipeline_engine_initialization_failed",
        "pipeline_execution_failed",
        "portfolio_subjob_failures",
        "reviewer_candidate_failures",
        "reviewer_stage_failed",
        "scout_lookup_failed",
        "scout_persona_failures",
    }
)


def _repository(request: Request):
    repository = getattr(request.app.state, "durable_job_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "reason": "durable_job_store_unavailable",
            },
        )
    return repository


def _public_status(status: JobStatus) -> str:
    return "accepted" if status is JobStatus.QUEUED else status.value


def _safe_error(status: JobStatus) -> Optional[str]:
    if status is JobStatus.DEAD_LETTER:
        return "Execution failed after all retry attempts."
    if status is JobStatus.FAILED:
        return "Execution failed."
    if status is JobStatus.BLOCKED:
        return "Execution is blocked and requires operator review."
    return None


def _failure_code(job: AgentJob) -> Optional[str]:
    """Expose only a bounded machine-readable error code, never raw exception text."""
    raw = str(job.last_error or "").strip()
    if not raw:
        return None
    prefix = raw.split(":", 1)[0].strip().lower().replace(" ", "_")
    if prefix in _PUBLIC_FAILURE_CODES:
        return prefix
    return "pipeline_execution_failed"


def _serialize(job: AgentJob) -> Dict[str, Any]:
    lookup_id = getattr(job.payload, "lookup_id", None)
    return {
        "job_id": job.job_id,
        "job_type": job.job_type.value,
        "status": _public_status(job.status),
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "pipeline_run_id": job.pipeline_run_id,
        "lookup_id": lookup_id,
        "accepted_at": job.accepted_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "next_attempt_at": job.next_attempt_at.isoformat(),
        "error": _safe_error(job.status),
        "failure_code": _failure_code(job)
        if job.status in {JobStatus.FAILED, JobStatus.DEAD_LETTER}
        else None,
        "block_code": job.block_code if job.status is JobStatus.BLOCKED else None,
        "recovery_action": (
            job.recovery_action if job.status is JobStatus.BLOCKED else None
        ),
    }


def _parse_statuses(raw: Optional[str]) -> Optional[List[JobStatus]]:
    if not raw:
        return None
    values: List[JobStatus] = []
    for item in raw.split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized == "accepted":
            normalized = JobStatus.QUEUED.value
        try:
            values.append(JobStatus(normalized))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid job status filter") from exc
    return values or None


@router.get("")
async def list_jobs(
    request: Request,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    user_id = require_authenticated_user(request)
    jobs = await _repository(request).list_jobs(
        user_id=user_id,
        statuses=_parse_statuses(status),
        limit=limit,
    )
    return {"jobs": [_serialize(job) for job in jobs]}


@router.get("/{job_id}")
async def get_job(request: Request, job_id: str):
    validate_route_id(job_id, field_name="job_id")
    user_id = require_authenticated_user(request)
    job = await _repository(request).get_job(user_id=user_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize(job)


@router.post("/{job_id}/retry")
async def retry_job(request: Request, job_id: str):
    validate_route_id(job_id, field_name="job_id")
    user_id = require_authenticated_user(request)
    repository = _repository(request)
    current = await repository.get_job(user_id=user_id, job_id=job_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if current.status not in _RETRYABLE:
        raise HTTPException(status_code=409, detail="Job is not retryable in its current state")
    try:
        job = await repository.requeue(user_id=user_id, job_id=job_id)
    except LookupOutcomeStoreUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "reason": "lookup_outcome_store_unavailable",
            },
        ) from exc
    if job is None:
        raise HTTPException(status_code=409, detail="Job state changed; refresh before retrying")
    return JSONResponse(status_code=202, content=_serialize(job))


@router.post("/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str):
    validate_route_id(job_id, field_name="job_id")
    user_id = require_authenticated_user(request)
    repository = _repository(request)
    try:
        result = await repository.cancel(user_id=user_id, job_id=job_id)
    except LookupOutcomeStoreUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "reason": "lookup_outcome_store_unavailable",
            },
        ) from exc
    if result.disposition is JobCancellationDisposition.NOT_FOUND:
        raise HTTPException(status_code=404, detail="Job not found")
    if not result.cancellation_won:
        raise HTTPException(status_code=409, detail="Job state changed; refresh before cancelling")
    assert result.job is not None
    return JSONResponse(status_code=202, content=_serialize(result.job))
