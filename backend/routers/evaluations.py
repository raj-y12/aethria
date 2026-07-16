"""Current immutable evaluation/recommendation projection and explicit trigger."""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from core.policy_resolver import get_partner_rules
from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.repository import EvaluationLifecycleError
from fund_thesis import FundThesisError, get_active_thesis
from security.request_guards import require_authenticated_user, validate_route_id
from services.scoring.policy_store import (
    PolicyNotPublishedError,
    load_published_policy,
)
from supabase_client import get_service_client


router = APIRouter(tags=["evaluations"])


def _repository(request: Request):
    repository = getattr(request.app.state, "evaluation_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Evaluation store unavailable")
    return repository


@router.get("/api/opportunities/{opportunity_id}/evaluation")
async def get_current_evaluation(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    result = await _repository(request).get_current(
        user_id=user_id, opportunity_id=opportunity_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Completed evaluation not found")
    return result


@router.post("/api/opportunities/{opportunity_id}/evaluate")
async def evaluate_opportunity(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    try:
        thesis = await asyncio.to_thread(
            get_active_thesis, get_service_client(), user_id
        )
        if thesis is None:
            raise HTTPException(
                status_code=409,
                detail="An active fund thesis is required before evaluation",
            )
        compiled_policy, partner_rules = await asyncio.gather(
            asyncio.to_thread(load_published_policy, user_id),
            asyncio.to_thread(get_partner_rules),
        )
        policy = evaluation_policy_from_compiled(
            compiled_policy, partner_rules=partner_rules
        )
        return await _repository(request).evaluate(
            user_id=user_id,
            opportunity_id=opportunity_id,
            actor_id=user_id,
            trigger_type="operator_refresh",
            policy=policy,
            thesis_version_id=thesis.version_id,
        )
    except PolicyNotPublishedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FundThesisError as exc:
        raise HTTPException(status_code=503, detail="Fund thesis is unavailable") from exc
    except EvaluationLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
