"""Authenticated ruling and workflow-action controls."""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from decisions.models import HumanRulingDecision, HumanRulingInput, OverrideType, WorkflowActionType
from routers.authority import require_write_path, with_authority_metadata
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["decisions"])


class RulingBody(BaseModel):
    recommendation_id: Optional[str] = None
    decision: HumanRulingDecision
    rationale: str = Field(min_length=3, max_length=2000)
    risk_acknowledgement: Optional[str] = Field(default=None, max_length=1000)
    mandate_exception: Optional[str] = Field(default=None, max_length=1000)
    investor_confidence: float = Field(default=0.5, ge=0, le=1)
    override_type: Optional[OverrideType] = None
    override_note: Optional[str] = Field(default=None, max_length=1000)


class ActionBody(BaseModel):
    action_type: WorkflowActionType
    due_at: Optional[datetime] = None
    external_destination: Optional[str] = Field(default=None, max_length=500)


class ApproveActionBody(BaseModel):
    approved_content: Optional[Dict[str, Any]] = None


def _repository(request: Request):
    repo = getattr(request.app.state, "decision_repository", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Decision store unavailable")
    return repo


@router.post("/api/opportunities/{opportunity_id}/rulings")
async def create_ruling(request: Request, opportunity_id: str, body: RulingBody):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    authority = await require_write_path(request, operation="human ruling creation")
    try:
        record = await _repository(request).create_ruling(
            HumanRulingInput(
                user_id=user_id,
                opportunity_id=opportunity_id,
                **body.model_dump(),
            ),
            actor_id=user_id,
        )
        return with_authority_metadata(record, authority)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity or recommendation not found") from exc


@router.get("/api/opportunities/{opportunity_id}/rulings")
async def list_rulings(
    request: Request,
    opportunity_id: str,
    limit: int = Query(default=50, ge=1, le=100),
):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    records = await _repository(request).list_rulings(
        user_id=user_id,
        opportunity_id=opportunity_id,
        limit=limit,
    )
    return {"rulings": [record.model_dump(mode="json") for record in records]}


@router.post("/api/opportunities/{opportunity_id}/actions")
async def create_action(request: Request, opportunity_id: str, body: ActionBody):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    authority = await require_write_path(request, operation="workflow action creation")
    try:
        record = await _repository(request).create_action(
            user_id=user_id, opportunity_id=opportunity_id,
            action_type=body.action_type, due_at=body.due_at,
            external_destination=body.external_destination,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
    return with_authority_metadata(record.model_dump(mode="json"), authority)


@router.get("/api/opportunities/{opportunity_id}/actions")
async def list_actions(request: Request, opportunity_id: str, limit: int = Query(default=100, ge=1, le=200)):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    records = await _repository(request).list_actions(user_id=user_id, opportunity_id=opportunity_id, limit=limit)
    return {"actions": [record.model_dump(mode="json") for record in records]}


@router.post("/api/actions/{workflow_action_id}/approve")
async def approve_action(request: Request, workflow_action_id: str, body: ApproveActionBody):
    validate_route_id(workflow_action_id, field_name="workflow_action_id")
    user_id = require_authenticated_user(request)
    authority = await require_write_path(request, operation="workflow action approval")
    try:
        record = await _repository(request).approve_action(
            user_id=user_id, workflow_action_id=workflow_action_id,
            approved_by=user_id, approved_content=body.approved_content,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Pending action not found") from exc
    return with_authority_metadata(record.model_dump(mode="json"), authority)
