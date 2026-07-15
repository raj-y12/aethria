"""Current immutable evaluation/recommendation projection and explicit trigger."""

from fastapi import APIRouter, HTTPException, Request

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
        return await _repository(request).evaluate(
            user_id=user_id,
            opportunity_id=opportunity_id,
            actor_id=user_id,
            trigger_type="operator_refresh",
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
