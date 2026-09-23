"""Current immutable evaluation/recommendation projection and explicit trigger."""

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from investment_analysis.repository import EvaluationLifecycleError
from investment_analysis.model_gateway import AnalysisBlocked
from routers.authority import (
    has_authority_control_plane,
    require_write_path,
    with_authority_metadata,
)
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["evaluations"])


def analyst_evaluation(record: dict) -> dict:
    """Investment explanations and link keys, without duplicated audit payloads."""
    def pick(value, fields):
        return {key: value[key] for key in fields if key in value}
    return {
        "evaluation": pick(record["evaluation"], ("evaluation_id", "status", "created_at")),
        "criteria": [{**pick(item, ("criterion_assessment_id", "criterion", "score", "confidence",
            "evidence_sufficiency", "reasoning", "supporting_claim_ids", "contradicting_claim_ids",
            "missing_evidence", "quality_flags")), "deterministic_adjustments": pick(
                item.get("deterministic_adjustments") or {}, ("assessment_validation", "change_from_prior_review"))}
            for item in record.get("criteria", [])],
        "recommendation": pick(record["recommendation"], ("recommendation_id", "recommended_state",
            "attention_priority", "confidence", "decision_drivers", "principal_risks", "mandate_conflicts",
            "missing_information", "change_conditions", "human_review_required", "change_explanation"))
            if record.get("recommendation") else None,
        "provenance": pick(record.get("provenance") or {}, ("score_origin", "recommendation_origin")),
        **({"dependencies": record["dependencies"]} if "dependencies" in record else {}),
    }


def _repository(request: Request):
    repository = getattr(request.app.state, "evaluation_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Evaluation store unavailable")
    return repository


@router.get("/api/opportunities/{opportunity_id}/evaluation")
async def get_current_evaluation(request: Request, opportunity_id: str, view: Literal["full", "analyst"] = "full"):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    result = await _repository(request).get_current(
        user_id=user_id, opportunity_id=opportunity_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Completed evaluation not found")
    inspect = getattr(_repository(request), "inspect_dependencies", None)
    if callable(inspect):
        try:
            dependencies = await inspect(user_id=user_id, opportunity_id=opportunity_id, record=result)
        except EvaluationPrerequisiteError:
            dependencies = {"state": "unknown", "reasons": ["fund_context_unavailable"],
                            "message": "Current fund context is unavailable. This historical review has not been revalidated."}
        result = {**result, "dependencies": dependencies}
    return analyst_evaluation(result) if view == "analyst" else result


@router.post("/api/opportunities/{opportunity_id}/evaluate")
async def evaluate_opportunity(request: Request, opportunity_id: str, scope: Literal["full", "partner"] = "full"):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    authority = await require_write_path(request, operation="evaluation creation")
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
            trigger_type="operator_partner_refresh" if scope == "partner" else "operator_refresh",
            policy=prerequisites.policy,
            thesis_version_id=prerequisites.thesis_version_id,
            **({"review_mode": "partner_only"} if scope == "partner" else {}),
        )
        current = await repository.get_current(
            user_id=user_id, opportunity_id=opportunity_id
        )
        if current is None:
            raise RuntimeError("Completed evaluation projection is unavailable")
        return (
            with_authority_metadata(current, authority)
            if has_authority_control_plane(request)
            else current
        )
    except EvaluationPrerequisiteError as exc:
        status_code = (
            409
            if exc.code in {"thesis_required", "published_policy_required"}
            else 503
        )
        raise HTTPException(status_code=status_code, detail=exc.detail) from exc
    except AnalysisBlocked as exc:
        raise HTTPException(
            status_code=409 if exc.code == "analysis_dependencies_changed" else 503,
            detail={"code": exc.code, "detail": str(exc)},
        ) from exc
    except EvaluationLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found") from exc
