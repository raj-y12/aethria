"""Tenant-scoped canonical identity, opportunity, and operator ruling APIs."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

from identity.models import IdentityCaseStatus, IdentityStatus
from routers.authority import authority_for_request, has_authority_control_plane, require_write_path, with_authority_metadata
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["identity"])


class ResolveIdentityCaseBody(BaseModel):
    action: Literal["match", "create", "defer", "reject"]
    selected_company_id: Optional[str] = None
    canonical_name: Optional[str] = Field(default=None, max_length=300)
    canonical_domain: Optional[str] = Field(default=None, max_length=500)
    resolution_note: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "match" and not str(self.selected_company_id or "").strip():
            raise ValueError("selected_company_id is required for match")
        if self.action == "create" and (
            not str(self.canonical_name or "").strip()
            or not str(self.canonical_domain or "").strip()
        ):
            raise ValueError("canonical_name and canonical_domain are required for create")
        return self


class CaseTransitionBody(BaseModel):
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


def _repository(request: Request):
    repository = getattr(request.app.state, "identity_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "reason": "identity_store_unavailable"},
        )
    return repository


def _company(record: Any) -> Dict[str, Any]:
    return {
        "company_id": record.company_id,
        "canonical_name": record.canonical_name,
        "canonical_domain": record.canonical_domain,
        "identity_confidence": record.identity_confidence,
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _opportunity(record: Any) -> Dict[str, Any]:
    return {
        "opportunity_id": record.opportunity_id,
        "company_id": record.company_id,
        "context_key": record.context_key,
        "decision_state": record.decision_state.value,
        "service_level": record.service_level,
        "first_observation_id": record.first_observation_id,
        "latest_observation_id": record.latest_observation_id,
        "legacy_startup_id": record.legacy_startup_id,
        "current_evaluation_id": record.current_evaluation_id,
        "current_recommendation_id": record.current_recommendation_id,
        "current_ruling_id": record.current_ruling_id,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _observation(record: Any) -> Dict[str, Any]:
    return {
        "observation_id": record.observation_id,
        "channel": record.channel.value,
        "observed_name": record.observed_name,
        "observed_domain": record.observed_domain,
        "external_event_key": record.external_event_key,
        "lookup_id": record.lookup_id,
        "legacy_startup_id": record.legacy_startup_id,
        "company_id": record.company_id,
        "identity_status": record.identity_status.value,
        "identity_confidence": record.identity_confidence,
        "observed_at": record.observed_at.isoformat(),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _candidate(candidate: Any) -> Dict[str, Any]:
    urls = [
        url
        for url in candidate.evidence_urls[:8]
        if str(url).lower().startswith(("https://", "http://"))
    ]
    return {
        "company_id": candidate.company_id,
        "canonical_name": candidate.canonical_name,
        "canonical_domain": candidate.canonical_domain,
        "confidence": candidate.confidence,
        "evidence_urls": urls,
        "reason": candidate.reason,
    }


def _case(record: Any) -> Dict[str, Any]:
    return {
        "identity_case_id": record.identity_case_id,
        "observation_id": record.observation_id,
        "status": record.status.value,
        "reason_code": record.reason_code,
        "candidates": [_candidate(item) for item in record.candidates],
        "selected_company_id": record.selected_company_id,
        "resolution_note": record.resolution_note,
        "resolved_by": record.resolved_by,
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _admission(record: Any) -> Dict[str, Any]:
    return {
        "observation_id": record.observation_id,
        "status": record.status.value,
        "company_id": record.company_id,
        "opportunity_id": record.opportunity_id,
        "identity_case_id": record.identity_case_id,
        "confidence": record.confidence,
        "blocks_evaluation": record.blocks_evaluation,
        "created": record.created,
    }


@router.get("/api/companies/{company_id}")
async def get_company(request: Request, company_id: str):
    validate_route_id(company_id, field_name="company_id")
    user_id = require_authenticated_user(request)
    record = await _repository(request).get_company(
        user_id=user_id, company_id=company_id
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return _company(record)


@router.get("/api/opportunities/{opportunity_id}")
async def get_opportunity(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    record = await _repository(request).get_opportunity(
        user_id=user_id, opportunity_id=opportunity_id
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _opportunity(record)


@router.get("/api/opportunities")
async def list_opportunities(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
):
    user_id = require_authenticated_user(request)
    authority = await authority_for_request(request) if has_authority_control_plane(request) else None
    records = await _repository(request).list_opportunities(user_id=user_id, limit=limit)
    payload = {"opportunities": records}
    return with_authority_metadata(payload, authority) if authority else payload


@router.get("/api/opportunities/{opportunity_id}/decision-view")
async def get_decision_view(request: Request, opportunity_id: str):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    user_id = require_authenticated_user(request)
    authority = await authority_for_request(request) if has_authority_control_plane(request) else None
    record = await _repository(request).get_decision_view(
        user_id=user_id, opportunity_id=opportunity_id
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return with_authority_metadata(record, authority) if authority else record


@router.get("/api/startups/{legacy_startup_id}/opportunity")
async def get_opportunity_by_legacy_startup(request: Request, legacy_startup_id: str):
    """Resolve the compatibility startup projection to its canonical opportunity."""

    validate_route_id(legacy_startup_id, field_name="legacy_startup_id")
    user_id = require_authenticated_user(request)
    record = await _repository(request).get_opportunity_by_legacy_projection(
        user_id=user_id,
        legacy_startup_id=legacy_startup_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _opportunity(record)


@router.get("/api/observations")
async def list_observations(
    request: Request,
    status: Optional[IdentityStatus] = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    user_id = require_authenticated_user(request)
    records = await _repository(request).list_observations(
        user_id=user_id,
        status=status.value if status else None,
        limit=limit,
    )
    return {"observations": [_observation(record) for record in records]}


@router.get("/api/identity-cases")
async def list_identity_cases(
    request: Request,
    status: IdentityCaseStatus = IdentityCaseStatus.OPEN,
    limit: int = Query(default=100, ge=1, le=200),
):
    user_id = require_authenticated_user(request)
    records = await _repository(request).list_cases(
        user_id=user_id, status=status.value, limit=limit
    )
    return {"cases": [_case(record) for record in records]}


def _case_group(group: Any) -> Dict[str, Any]:
    return {
        "group_key": group.group_key,
        "canonical_domain": group.canonical_domain,
        "observation_count": len(group.cases),
        "observed_names": group.observed_names,
        "sources": group.sources,
        "cases": [_case(case) for case in group.cases],
    }


@router.get("/api/identity-cases/groups")
async def list_identity_case_groups(
    request: Request,
    status: IdentityCaseStatus = IdentityCaseStatus.OPEN,
    limit: int = Query(default=100, ge=1, le=200),
):
    """Duplicate-observation-safe view of the review queue — one row per
    canonical identity instead of one row per observation. See
    docs/known-issues.md "Duplicate companies in the identity review queue"."""
    user_id = require_authenticated_user(request)
    groups = await _repository(request).list_case_groups(
        user_id=user_id, status=status.value, limit=limit
    )
    return {"groups": [_case_group(group) for group in groups]}


async def _resolved_or_existing(
    repository: Any, *, user_id: str, identity_case_id: str
) -> tuple[Any, Optional[Any]]:
    case = await repository.get_case(
        user_id=user_id, identity_case_id=identity_case_id
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Identity case not found")
    if case.status is IdentityCaseStatus.RESOLVED:
        admission = await repository.get_admission_for_observation(
            user_id=user_id, observation_id=case.observation_id
        )
        if admission is None:
            raise HTTPException(status_code=409, detail="Resolved identity is reconciling")
        return case, admission
    return case, None


@router.post("/api/identity-cases/{identity_case_id}/resolve")
async def resolve_identity_case(
    request: Request, identity_case_id: str, body: ResolveIdentityCaseBody
):
    validate_route_id(identity_case_id, field_name="identity_case_id")
    user_id = require_authenticated_user(request)
    repository = _repository(request)
    authority = await authority_for_request(request)
    case, existing = await _resolved_or_existing(
        repository, user_id=user_id, identity_case_id=identity_case_id
    )
    if existing is not None:
        return with_authority_metadata(_admission(existing), authority)
    if case.status is not IdentityCaseStatus.OPEN:
        return with_authority_metadata(_case(case), authority)
    authority = await require_write_path(request, operation="identity linkage")
    try:
        if body.action == "match":
            validate_route_id(body.selected_company_id, field_name="selected_company_id")
            result = await repository.resolve_case(
                user_id=user_id,
                identity_case_id=identity_case_id,
                selected_company_id=body.selected_company_id,
                resolved_by=user_id,
                resolution_note=body.resolution_note,
            )
            return with_authority_metadata(_admission(result), authority)
        if body.action == "create":
            result = await repository.create_company_from_case(
                user_id=user_id,
                identity_case_id=identity_case_id,
                canonical_name=body.canonical_name,
                canonical_domain=body.canonical_domain,
                resolved_by=user_id,
                resolution_note=body.resolution_note,
            )
            return with_authority_metadata(_admission(result), authority)
        if body.action == "defer":
            return with_authority_metadata(
                _case(await repository.defer_case(
                    user_id=user_id,
                    identity_case_id=identity_case_id,
                    resolved_by=user_id,
                    resolution_note=body.resolution_note,
                )),
                authority,
            )
        return with_authority_metadata(
            _case(await repository.reject_case(
                user_id=user_id,
                identity_case_id=identity_case_id,
                resolved_by=user_id,
                resolution_note=body.resolution_note,
            )),
            authority,
        )
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Identity case state changed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid identity resolution") from exc


async def _resolve_case_group(
    request: Request, group_key: str, body: ResolveIdentityCaseBody
) -> Dict[str, Any]:
    """Transition every case in a group as a unit (fix direction step 4): the
    first case runs the requested action (matching an existing company or
    creating a new one); every remaining case in the group then matches the
    same resulting company, rather than re-running "create" and producing a
    duplicate company per case."""
    user_id = require_authenticated_user(request)
    repository = _repository(request)
    groups = await repository.list_case_groups(
        user_id=user_id, status="open", limit=500
    )
    group = next((g for g in groups if g.group_key == group_key), None)
    if group is None or not group.cases:
        raise HTTPException(status_code=404, detail="Identity case group not found")

    case_ids = [case.identity_case_id for case in group.cases]
    first_id, *rest_ids = case_ids
    first_result = await resolve_identity_case(request, first_id, body)
    results = [first_result]

    if body.action in ("match", "create"):
        company_id = first_result.get("company_id")
        follow_up = (
            ResolveIdentityCaseBody(
                action="match",
                selected_company_id=company_id,
                resolution_note=body.resolution_note,
            )
            if company_id
            else None
        )
        for case_id in rest_ids:
            results.append(
                await resolve_identity_case(request, case_id, follow_up)
                if follow_up is not None
                # The first case didn't resolve to a company (e.g. it was
                # already resolved out-of-band) — fail closed per case rather
                # than guess, leaving each for individual review.
                else {"identity_case_id": case_id, "skipped": "no_resulting_company_id"}
            )
    else:
        for case_id in rest_ids:
            results.append(await resolve_identity_case(request, case_id, body))

    return {"group_key": group_key, "results": results}


@router.post("/api/identity-cases/groups/{group_key}/resolve")
async def resolve_identity_case_group(
    request: Request, group_key: str, body: ResolveIdentityCaseBody
):
    return await _resolve_case_group(request, group_key, body)


@router.post("/api/identity-cases/groups/{group_key}/defer")
async def defer_identity_case_group(
    request: Request, group_key: str, body: CaseTransitionBody
):
    return await _resolve_case_group(
        request,
        group_key,
        ResolveIdentityCaseBody(action="defer", resolution_note=body.resolution_note),
    )


@router.post("/api/identity-cases/groups/{group_key}/reject")
async def reject_identity_case_group(
    request: Request, group_key: str, body: CaseTransitionBody
):
    return await _resolve_case_group(
        request,
        group_key,
        ResolveIdentityCaseBody(action="reject", resolution_note=body.resolution_note),
    )


@router.post("/api/identity-cases/{identity_case_id}/defer")
async def defer_identity_case(
    request: Request, identity_case_id: str, body: CaseTransitionBody
):
    return await resolve_identity_case(
        request,
        identity_case_id,
        ResolveIdentityCaseBody(action="defer", resolution_note=body.resolution_note),
    )


@router.post("/api/identity-cases/{identity_case_id}/reject")
async def reject_identity_case(
    request: Request, identity_case_id: str, body: CaseTransitionBody
):
    return await resolve_identity_case(
        request,
        identity_case_id,
        ResolveIdentityCaseBody(action="reject", resolution_note=body.resolution_note),
    )
