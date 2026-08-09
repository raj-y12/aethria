"""Governed Fund Intelligence proposal inbox and explicit publication API."""

import asyncio
import hashlib
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from fund_intelligence.models import PolicyProposalStatus, ProposalReviewAction
from security.request_guards import require_authenticated_user, validate_route_id
from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
)
from utils.settings_loader import load_settings


router = APIRouter(prefix="/api/fund-intelligence", tags=["fund-intelligence"])


class ReviewBody(BaseModel):
    action: ProposalReviewAction
    rationale: str = Field(min_length=3, max_length=2000)
    edited_policy_patch: Optional[Dict[str, Any]] = None


class PreviewBody(BaseModel):
    action: ProposalReviewAction
    edited_policy_patch: Optional[Dict[str, Any]] = None


_EDITABLE_POLICY_KEYS = {"rubric", "scoringWeights"}


def _config_hash(config: Dict[str, Any]) -> str:
    canonical = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _restricted_policy_patch(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ValueError("A non-empty scoring policy patch is required")
    unsupported = sorted(set(value) - _EDITABLE_POLICY_KEYS)
    if unsupported:
        raise ValueError(
            "Policy patch contains unsupported field(s): " + ", ".join(unsupported)
        )
    patch = dict(value)
    for key, item in patch.items():
        if not isinstance(item, list):
            raise ValueError(f"{key} must be a list")
    return patch


async def _canonical_policy_result(
    request: Request,
    *,
    user_id: str,
    policy_proposal_id: str,
    action: ProposalReviewAction,
    edited_policy_patch: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any], str]:
    detail = await _repository(request).get_proposal(
        user_id=user_id, policy_proposal_id=policy_proposal_id
    )
    if detail is None:
        raise LookupError("Proposal not found for tenant")
    if action is ProposalReviewAction.ACCEPT:
        patch = _restricted_policy_patch(
            detail["proposal"].get("proposed_policy_patch")
        )
    elif action is ProposalReviewAction.EDIT_AND_ACCEPT:
        patch = _restricted_policy_patch(edited_policy_patch)
    else:
        raise ValueError("Only acceptance actions can preview a policy result")
    current: Dict[str, Any]
    current_hash: str
    active_reader = getattr(_repository(request), "get_active_published_policy", None)
    governed = None
    if callable(active_reader):
        try:
            governed = await active_reader(user_id=user_id)
        except LookupError:
            governed = None
    if governed is not None:
        current = dict(governed.get("policy_patch") or {})
        current_hash = str(governed.get("policy_hash") or "").strip()
    else:
        settings = await asyncio.to_thread(load_settings, user_id, use_cache=False)
        current = (
            dict(settings.get("fund_config"))
            if isinstance(settings.get("fund_config"), dict)
            else {}
        )
        current_hash = str(current.get("publishedPolicyHash") or "").strip()
    result = {**current, **patch}
    compiled = await asyncio.to_thread(
        compile_policy_from_fund_config, result, require_publish_ready=True
    )
    if compiled["policy_hash"] == current_hash:
        raise ValueError("The edited proposal does not change the published scoring policy")
    return result, compiled, _config_hash(result)


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


@router.get("/observations")
async def list_observations(
    request: Request,
    sector: Optional[str] = None,
    stage: Optional[str] = None,
    geography: Optional[str] = None,
    thesis_version_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    observation_type: Optional[str] = None,
):
    user_id = require_authenticated_user(request)
    from datetime import datetime

    def parse_date(value: Optional[str]):
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid ISO-8601 date filter") from exc

    observations = await _repository(request).get_observations(
        user_id=user_id,
        sector=sector,
        stage=stage,
        geography=geography,
        thesis_version_id=thesis_version_id,
        date_from=parse_date(date_from),
        date_to=parse_date(date_to),
        observation_type=observation_type,
    )
    return {"observations": observations}


@router.get("/hypotheses")
async def list_hypotheses(
    request: Request,
    sector: Optional[str] = None,
    stage: Optional[str] = None,
    geography: Optional[str] = None,
    thesis_version_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    hypothesis_family: Optional[str] = None,
):
    user_id = require_authenticated_user(request)
    from datetime import datetime

    def parse_date(value: Optional[str]):
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid ISO-8601 date filter") from exc

    hypotheses = await _repository(request).get_hypotheses(
        user_id=user_id,
        sector=sector,
        stage=stage,
        geography=geography,
        thesis_version_id=thesis_version_id,
        date_from=parse_date(date_from),
        date_to=parse_date(date_to),
        hypothesis_family=hypothesis_family,
    )
    return {"hypotheses": hypotheses}


@router.get("/hypotheses/{hypothesis_id}/replay")
async def replay_hypothesis(request: Request, hypothesis_id: str):
    validate_route_id(hypothesis_id, field_name="hypothesis_id")
    user_id = require_authenticated_user(request)
    preview = await _repository(request).get_replay_preview(
        user_id=user_id, hypothesis_id=hypothesis_id
    )
    if preview is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found for tenant")
    return preview


@router.get("/counterfactual-proposals")
async def list_counterfactual_proposals(
    request: Request,
    sector: Optional[str] = None,
    stage: Optional[str] = None,
    geography: Optional[str] = None,
    thesis_version_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    hypothesis_family: Optional[str] = None,
):
    user_id = require_authenticated_user(request)
    from datetime import datetime

    def parse_date(value: Optional[str]):
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid ISO-8601 date filter") from exc

    proposals = await _repository(request).get_counterfactual_proposals(
        user_id=user_id,
        sector=sector,
        stage=stage,
        geography=geography,
        thesis_version_id=thesis_version_id,
        date_from=parse_date(date_from),
        date_to=parse_date(date_to),
        hypothesis_family=hypothesis_family,
    )
    return {"counterfactual_proposals": proposals}


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
        _, compiled, config_hash = await _canonical_policy_result(
            request,
            user_id=user_id,
            policy_proposal_id=policy_proposal_id,
            action=body.action,
            edited_policy_patch=body.edited_policy_patch,
        )
        return await _repository(request).preview_impact(
            user_id=user_id,
            policy_proposal_id=policy_proposal_id,
            actor_id=user_id,
            policy_hash=compiled["policy_hash"],
            config_hash=config_hash,
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
        resulting_fund_config = None
        config_hash = None
        if accepting:
            resulting_fund_config, compiled, config_hash = await _canonical_policy_result(
                request,
                user_id=user_id,
                policy_proposal_id=policy_proposal_id,
                action=body.action,
                edited_policy_patch=body.edited_policy_patch,
            )
        return await _repository(request).review_proposal(
            user_id=user_id,
            policy_proposal_id=policy_proposal_id,
            actor_id=user_id,
            action=body.action,
            rationale=body.rationale,
            resulting_fund_config=resulting_fund_config,
            policy_hash=compiled["policy_hash"] if compiled else None,
            config_hash=config_hash,
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
        version = await repository.mark_published(
            user_id=user_id,
            governed_policy_version_id=governed_policy_version_id,
            actor_id=user_id,
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
    return {
        "policy_version": version,
        "published_policy": {
            "policy_version_id": version["governed_policy_version_id"],
            "policy_hash": version["policy_hash"],
            "authoritative_store": "governed_policy_versions",
        },
        "legacy_projection": "pending",
    }
