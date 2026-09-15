"""Canonical opportunity application endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from identity.models import SourceChannel, SourceObservationInput
from opportunity_pipeline import OpportunityPipeline
from investment_analysis.model_gateway import AnalysisBlocked
from routers.deps import (
    LOOKUP_DAY_POLICY as _LOOKUP_DAY_POLICY,
    LOOKUP_MINUTE_POLICY as _LOOKUP_MINUTE_POLICY,
    enforce_rate_limits as _enforce_rate_limits,
)
from security.request_guards import require_authenticated_user

router = APIRouter(tags=["opportunities"])


_MANUAL_LOOKUP_ITEM_STRING_MAX_LENGTH = 10_000


class ManualLookupBody(BaseModel):
    company_name: str = Field(min_length=1, max_length=300)
    website: Optional[str] = Field(default=None, max_length=2000)
    lookup_id: Optional[str] = Field(default=None, max_length=200)
    references: List[Dict[str, Any]] = Field(default_factory=list, max_length=20)
    claims: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)

    # references/claims are freeform dicts (no nested schema), unlike the
    # scalar fields above -- so unlike those, nothing capped an individual
    # string value's length. List length alone doesn't bound payload size:
    # 50 claims with a single multi-megabyte string field is still 50 items.
    @field_validator("references", "claims")
    @classmethod
    def _reject_oversized_string_values(cls, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in items:
            for key, value in item.items():
                if isinstance(value, str) and len(value) > _MANUAL_LOOKUP_ITEM_STRING_MAX_LENGTH:
                    raise ValueError(
                        f"field '{key}' exceeds {_MANUAL_LOOKUP_ITEM_STRING_MAX_LENGTH} characters"
                    )
        return items


@router.post("/api/opportunities/manual-lookup")
async def manual_lookup(request: Request, body: ManualLookupBody):
    user_id = require_authenticated_user(request)
    # Fixed 2026-08-18 (audit HIGH-H9): this endpoint triggers a canonical
    # evaluate() call (an LLM-driven pipeline stage) with no rate limit at
    # all, unlike the legacy /api/lookup endpoint's LOOKUP_MINUTE_POLICY/
    # LOOKUP_DAY_POLICY -- an authenticated user could loop it with distinct
    # company names for unbounded LLM cost (AGENTS.md invariant #8).
    limited = await _enforce_rate_limits(
        f"user:{user_id}:manual_lookup", [_LOOKUP_MINUTE_POLICY, _LOOKUP_DAY_POLICY]
    )
    if limited is not None:
        return limited
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
    try:
        result = await pipeline.process(
            user_id=user_id, observation=observation,
            references=body.references, claims=body.claims,
        )
    except AnalysisBlocked as exc:
        raise HTTPException(
            status_code=409 if exc.code == "analysis_dependencies_changed" else 503,
            detail={"code": exc.code, "detail": str(exc)},
        ) from exc
    status = 200 if result.status == "completed" else 409
    if status != 200:
        raise HTTPException(status_code=status, detail=result.__dict__)
    return result.__dict__
