"""Current immutable evaluation/recommendation projection and explicit trigger."""

from fastapi import APIRouter, HTTPException, Request

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from evaluation_v2.repository import EvaluationLifecycleError
from security.request_guards import require_authenticated_user, validate_route_id


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
        prerequisites = await load_evaluation_prerequisites(
            user_id=user_id,
            fund_intelligence_repository=getattr(
                request.app.state, "fund_intelligence_repository", None
            ),
        )
        repository = _repository(request)
        await repository.evaluate(
            user_id=user_id,
            opportunity_id=opportunity_id,
            actor_id=user_id,
            trigger_type="operator_refresh",
            policy=prerequisites.policy,
            thesis_version_id=prerequisites.thesis_version_id,
        )
        current = await repository.get_current(
            user_id=user_id, opportunity_id=opportunity_id
        )
        if current is None:
            raise RuntimeError("Completed evaluation projection is unavailable")
        return current
    except EvaluationPrerequisiteError as exc:
        status_code = (
            409
            if exc.code in {"thesis_required", "published_policy_required"}
            else 503
        )
        raise HTTPException(status_code=status_code, detail=exc.detail) from exc
    except EvaluationLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
