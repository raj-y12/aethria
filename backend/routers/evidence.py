"""Evidence ledger, gap plan, and correction APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from security.request_guards import require_authenticated_user, validate_route_id
from evidence.models import AccessClass, ArtifactType, EvidenceArtifactInput, EvidenceItemInput, TrustClass, VerificationState


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


class ConfidentialEvidenceBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    storage_reference: str = Field(min_length=1, max_length=2000)
    content_hash: str = Field(min_length=8, max_length=200)
    excerpt: Optional[str] = Field(default=None, max_length=2000)
    item_type: str = Field(default="confidential_note", min_length=1, max_length=160)
    normalized_value: Dict[str, Any] = Field(default_factory=dict)
    effective_at: Optional[datetime] = None


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
async def get_evidence_ledger(request: Request, opportunity_id: str, view: Literal["full", "analyst"] = "full"):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    ledger = await _repository(request).get_ledger(
        user_id=user_id, opportunity_id=opportunity_id
    )
    safe = _safe_ledger(ledger)
    if view == "analyst":
        fields = {
            "artifacts": ("artifact_id", "artifact_type", "source_uri", "title", "trust_class", "access_class", "published_at", "effective_at", "retrieved_at"),
            "evidence_items": ("evidence_item_id", "artifact_id", "item_type", "display_excerpt", "effective_at", "expires_at", "verification_state", "source_quality", "extraction_confidence"),
            "claims": ("claim_id", "company_id", "claim_type", "display_text", "assertion_class", "confidence", "material", "status", "period"),
            "claim_evidence_links": ("link_id", "claim_id", "evidence_item_id", "relationship", "support_strength", "rationale"),
        }
        return {kind: [{key: row[key] for key in keys if key in row} for row in safe.get(kind, [])]
                for kind, keys in fields.items()}
    return safe


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


@router.post("/api/opportunities/{opportunity_id}/confidential-evidence")
async def ingest_confidential_evidence(
    request: Request, opportunity_id: str, body: ConfidentialEvidenceBody
):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    artifact, items = await _repository(request).ingest_artifact(
        EvidenceArtifactInput(
            user_id=user_id, opportunity_id=opportunity_id,
            artifact_type=ArtifactType.INTERVIEW_NOTE,
            title=body.title, content_hash=body.content_hash,
            storage_reference=body.storage_reference,
            trust_class=TrustClass.OPERATOR,
            access_class=AccessClass.TENANT_CONFIDENTIAL,
            untrusted_input=False, prompt_injection_detected=False,
            effective_at=body.effective_at,
        ),
        items=[EvidenceItemInput(
            user_id=user_id, item_type=body.item_type,
            normalized_value=body.normalized_value,
            display_excerpt=body.excerpt or "Confidential evidence received.",
            effective_at=body.effective_at,
            verification_state=VerificationState.VERIFIED,
            source_quality=1.0, extraction_confidence=1.0,
            operator_attribution=user_id,
        )],
    )
    return {
        "artifact_id": artifact.artifact_id,
        "access_class": artifact.access_class.value,
        "item_ids": [item.evidence_item_id for item in items],
        "source_uri": None,
    }


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
