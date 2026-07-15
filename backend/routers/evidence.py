"""Evidence ledger, gap plan, and correction APIs."""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["evidence"])


class EvidencePlanBody(BaseModel):
    trigger_type: str = Field(min_length=1, max_length=100)
    missing_evidence: List[str] = Field(default_factory=list, max_length=30)
    search_questions: List[str] = Field(default_factory=list, max_length=30)
    max_artifacts: int = Field(default=5, ge=1, le=20)
    budget_usd: float = Field(default=0, ge=0, le=100)


class ClaimCorrectionBody(BaseModel):
    action: Literal["withdraw", "contradict", "mark_stale", "supersede"]
    rationale: str = Field(min_length=3, max_length=1000)


def _repository(request: Request):
    repository = getattr(request.app.state, "evidence_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Evidence store unavailable")
    return repository


def _safe_ledger(ledger):
    artifacts = []
    for source in ledger["artifacts"]:
        item = dict(source)
        item.pop("storage_reference", None)
        if item.get("access_class") == "restricted":
            item["source_uri"] = None
        artifacts.append(item)
    return {**ledger, "artifacts": artifacts}


@router.get("/api/opportunities/{opportunity_id}/evidence")
async def get_evidence_ledger(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    ledger = await _repository(request).get_ledger(
        user_id=user_id, opportunity_id=opportunity_id
    )
    return _safe_ledger(ledger)


@router.post("/api/opportunities/{opportunity_id}/evidence-plans")
async def create_evidence_plan(
    request: Request, opportunity_id: str, body: EvidencePlanBody
):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    plan = await _repository(request).create_plan(
        user_id=user_id,
        opportunity_id=opportunity_id,
        trigger_type=body.trigger_type,
        missing_evidence=body.missing_evidence,
        search_questions=body.search_questions,
        max_artifacts=body.max_artifacts,
        budget_usd=body.budget_usd,
    )
    return plan.model_dump(mode="json")


@router.post("/api/claims/{claim_id}/correct")
async def correct_claim(request: Request, claim_id: str, body: ClaimCorrectionBody):
    validate_route_id(claim_id, field_name="claim_id")
    user_id = require_authenticated_user(request)
    try:
        claim = await _repository(request).correct_claim(
            user_id=user_id,
            claim_id=claim_id,
            actor_id=user_id,
            action=body.action,
            rationale=body.rationale,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Claim not found") from exc
    return {
        "claim_id": str(claim["claim_id"]),
        "status": str(claim["status"]),
        "updated_at": claim["updated_at"].isoformat(),
    }
