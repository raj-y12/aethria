"""Governed Fund Intelligence proposal inbox and explicit publication API."""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from fund_intelligence.models import PolicyProposalStatus, ProposalReviewAction
from security.request_guards import require_authenticated_user, validate_route_id
from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
)
from services.scoring.policy_store import publish_policy


router = APIRouter(prefix="/api/fund-intelligence", tags=["fund-intelligence"])


class ReviewBody(BaseModel):
    action: ProposalReviewAction
    rationale: str = Field(min_length=3, max_length=2000)
    resulting_fund_config: Optional[Dict[str, Any]] = None


class PreviewBody(BaseModel):
    resulting_fund_config: Dict[str, Any]


def _repository(request: Request):
    repository = getattr(request.app.state, "fund_intelligence_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Fund Intelligence store unavailable")
    return repository


@router.post("/derive-overrides")
async def derive_override_patterns(request: Request):
    user_id = require_authenticated_user(request)
    return await _repository(request).derive_override_patterns(user_id=user_id)


@router.get("/proposals")
async def list_proposals(
    request: Request,
    status: Optional[PolicyProposalStatus] = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    user_id = require_authenticated_user(request)
    proposals = await _repository(request).list_proposals(
        user_id=user_id, status=status, limit=limit
    )
    return {"proposals": proposals}


@router.get("/proposals/{policy_proposal_id}")
async def get_proposal(request: Request, policy_proposal_id: str):
    validate_route_id(policy_proposal_id, field_name="policy_proposal_id")
    user_id = require_authenticated_user(request)
    result = await _repository(request).get_proposal(
        user_id=user_id, policy_proposal_id=policy_proposal_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Policy proposal not found")
    return result


@router.post("/proposals/{policy_proposal_id}/preview")
async def preview_proposal(
    request: Request, policy_proposal_id: str, body: PreviewBody
):
    validate_route_id(policy_proposal_id, field_name="policy_proposal_id")
    user_id = require_authenticated_user(request)
    try:
        compiled = await asyncio.to_thread(
            compile_policy_from_fund_config,
            body.resulting_fund_config,
            require_publish_ready=True,
        )
        return await _repository(request).preview_impact(
            user_id=user_id,
            policy_proposal_id=policy_proposal_id,
            actor_id=user_id,
            policy_hash=compiled["policy_hash"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Policy proposal not found") from exc
    except PolicyValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy validation failed", "errors": exc.errors},
        ) from exc


@router.post("/proposals/{policy_proposal_id}/review")
async def review_proposal(request: Request, policy_proposal_id: str, body: ReviewBody):
    validate_route_id(policy_proposal_id, field_name="policy_proposal_id")
    user_id = require_authenticated_user(request)
    try:
        accepting = body.action in {
            ProposalReviewAction.ACCEPT,
            ProposalReviewAction.EDIT_AND_ACCEPT,
        }
        compiled = None
        if accepting:
            if body.resulting_fund_config is None:
                raise ValueError("resulting_fund_config is required for acceptance")
            compiled = await asyncio.to_thread(
                compile_policy_from_fund_config,
                body.resulting_fund_config,
                require_publish_ready=True,
            )
        return await _repository(request).review_proposal(
            user_id=user_id,
            policy_proposal_id=policy_proposal_id,
            actor_id=user_id,
            action=body.action,
            rationale=body.rationale,
            resulting_fund_config=body.resulting_fund_config,
            policy_hash=compiled["policy_hash"] if compiled else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Policy proposal not found") from exc
    except PolicyValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy validation failed", "errors": exc.errors},
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/policy-versions/{governed_policy_version_id}/publish")
async def publish_governed_policy(
    request: Request, governed_policy_version_id: str
):
    validate_route_id(governed_policy_version_id, field_name="governed_policy_version_id")
    user_id = require_authenticated_user(request)
    repository = _repository(request)
    try:
        publishable = await repository.get_publishable_version(
            user_id=user_id, governed_policy_version_id=governed_policy_version_id
        )
        published = await asyncio.to_thread(
            publish_policy, user_id, fund_config=publishable["policy_patch"]
        )
        if published["policy_hash"] != publishable["policy_hash"]:
            raise RuntimeError("Published policy hash does not match the accepted draft")
        version = await repository.mark_published(
            user_id=user_id,
            governed_policy_version_id=governed_policy_version_id,
            actor_id=user_id,
            published_policy_id=published["policy_version_id"],
            published_policy_hash=published["policy_hash"],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Policy version not found") from exc
    except PolicyValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy validation failed", "errors": exc.errors},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"policy_version": version, "published_policy": published}
