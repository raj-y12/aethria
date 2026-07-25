"""Canonical opportunity application endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from identity.models import SourceChannel, SourceObservationInput
from opportunity_pipeline import OpportunityPipeline
from security.request_guards import require_authenticated_user

router = APIRouter(tags=["opportunities"])


class ManualLookupBody(BaseModel):
    company_name: str = Field(min_length=1, max_length=300)
    website: Optional[str] = Field(default=None, max_length=2000)
    lookup_id: Optional[str] = Field(default=None, max_length=200)
    references: List[Dict[str, Any]] = Field(default_factory=list, max_length=20)
    claims: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)


@router.post("/api/opportunities/manual-lookup")
async def manual_lookup(request: Request, body: ManualLookupBody):
    user_id = require_authenticated_user(request)
    pipeline = getattr(request.app.state, "opportunity_pipeline", None)
    if not isinstance(pipeline, OpportunityPipeline):
        raise HTTPException(status_code=503, detail="Opportunity pipeline unavailable")
    observation = SourceObservationInput(
        user_id=user_id, channel=SourceChannel.MANUAL_LOOKUP,
        observed_name=body.company_name.strip(), observed_domain=body.website,
        lookup_id=body.lookup_id,
        external_event_key=(f"manual:{body.lookup_id}" if body.lookup_id else None),
        resolution_payload={"website": body.website} if body.website else None,
    )
    result = await pipeline.process(
        user_id=user_id, observation=observation,
        references=body.references, claims=body.claims,
    )
    status = 200 if result.status == "completed" else 409
    if status != 200:
        raise HTTPException(status_code=status, detail=result.__dict__)
    return result.__dict__
