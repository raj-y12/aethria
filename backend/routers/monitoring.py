"""Attention-level, refresh-budget, and monitoring status controls."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from monitoring.models import RefreshEnvelope, RefreshReason, RefreshRequest, ServiceLevel
from monitoring.repository import RefreshBudgetExceeded, RefreshNotPermitted
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["monitoring"])


class RefreshBody(BaseModel):
    reason: RefreshReason
    request_key: str = Field(min_length=8, max_length=200)
    envelope: RefreshEnvelope = Field(default_factory=RefreshEnvelope)


class ServiceLevelBody(BaseModel):
    service_level: ServiceLevel
    lifecycle_reason: str = Field(min_length=3, max_length=1000)
    next_review_at: Optional[datetime] = None


def _repository(request: Request):
    repository = getattr(request.app.state, "monitoring_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Monitoring store unavailable")
    return repository


@router.post("/api/opportunities/{opportunity_id}/refresh")
async def request_refresh(request: Request, opportunity_id: str, body: RefreshBody):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    try:
        job, reservation = await _repository(request).reserve_and_enqueue(
            RefreshRequest(
                user_id=user_id,
                opportunity_id=opportunity_id,
                reason=body.reason,
                request_key=body.request_key,
                envelope=body.envelope,
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
    except RefreshNotPermitted as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RefreshBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted" if job.status.value == "queued" else job.status.value,
            "job_id": job.job_id,
            "pipeline_run_id": job.pipeline_run_id,
            "accepted_at": job.accepted_at.isoformat(),
            "budget_reservation": reservation.model_dump(mode="json"),
        },
    )


@router.patch("/api/opportunities/{opportunity_id}/service-level")
async def set_service_level(request: Request, opportunity_id: str, body: ServiceLevelBody):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    try:
        return await _repository(request).set_service_level(
            user_id=user_id,
            opportunity_id=opportunity_id,
            service_level=body.service_level,
            lifecycle_reason=body.lifecycle_reason,
            next_review_at=body.next_review_at,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc


@router.get("/api/opportunities/{opportunity_id}/monitoring")
async def get_monitoring_status(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    try:
        return await _repository(request).get_status(user_id=user_id, opportunity_id=opportunity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
