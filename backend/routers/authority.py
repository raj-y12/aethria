"""Authenticated, tenant-scoped authority rollout controls."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from authority.models import RolloutMode, RolloutRecord
from authority.projection import AuthorityProjectionConsumer
from authority.repository import (
    AuthorityBlocked,
    AuthorityConflict,
    AuthorityRepository,
    AuthorityTransitionError,
)
from authority.service import AuthorityContext, AuthorityService
from identity.projection import StartupCompatibilityProjectionRepository
from security.request_guards import require_authenticated_user


router = APIRouter(tags=["authority"])


class _AuthorityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TransitionBody(_AuthorityBody):
    target_mode: RolloutMode
    expected_version: StrictInt = Field(ge=0)
    snapshot_id: Optional[str] = Field(default=None, max_length=300)


class RollbackBody(_AuthorityBody):
    expected_version: StrictInt = Field(ge=0)
    reason: str = Field(min_length=1, max_length=2000)


class ReplayProjectionBody(_AuthorityBody):
    event_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    opportunity_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _exactly_one_selector(self) -> "ReplayProjectionBody":
        if bool(self.event_id) == bool(self.opportunity_id):
            raise ValueError("exactly one of event_id or opportunity_id is required")
        return self

class ReconciliationBody(_AuthorityBody):
    expected_version: StrictInt = Field(ge=0)
    status: str = Field(min_length=1, max_length=20)


def _service(request: Request) -> AuthorityService:
    service = getattr(request.app.state, "authority_service", None)
    if isinstance(service, AuthorityService):
        return service
    repository = getattr(request.app.state, "authority_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTHORITY_UNAVAILABLE", "message": "Authority store unavailable"},
        )
    service = AuthorityService(repository)
    request.app.state.authority_service = service
    return service


def authority_metadata(context: AuthorityContext) -> dict[str, Any]:
    return {
        "mode": context.mode.value,
        "version": context.version,
        "kill_switch": context.kill_switch,
        "canonical_writes_allowed": context.canonical_writes_allowed,
        "canonical_reads_allowed": context.canonical_reads_allowed,
        "last_reconciliation_status": context.last_reconciliation_status,
    }


def rollout_payload(record: RolloutRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")


def _conflict(exc: Exception, *, canonical_only: bool = False) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "AUTHORITY_CANONICAL_ONLY" if canonical_only else "AUTHORITY_CONFLICT",
            "message": str(exc),
        },
    )


async def authority_for_request(request: Request) -> AuthorityContext:
    user_id = require_authenticated_user(request)
    try:
        return await _service(request).authority(user_id=user_id)
    except (AuthorityConflict, AuthorityBlocked) as exc:
        raise _conflict(exc, canonical_only=True) from exc


async def require_write_path(request: Request, *, operation: str) -> AuthorityContext:
    """Fence canonical writers before any repository mutation occurs."""
    user_id = require_authenticated_user(request)
    try:
        service = _service(request)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        # Canonical authority is only active with its durable control-plane
        # repository. Preserve the established local legacy path when that
        # repository was deliberately not started (for example unit tests).
        return AuthorityContext(
            user_id=user_id,
            mode=RolloutMode.LEGACY,
            version=0,
            kill_switch=False,
            last_reconciliation_status=None,
        )
    try:
        return await service.require_write_path(
            user_id=user_id, operation=operation
        )
    except AuthorityBlocked as exc:
        raise _conflict(exc, canonical_only=True) from exc
    except AuthorityConflict as exc:
        raise _conflict(exc) from exc


def with_authority_metadata(payload: Any, context: AuthorityContext) -> Any:
    """Additive metadata keeps legacy/shadow DTOs backwards compatible."""
    if isinstance(payload, dict):
        return {**payload, "authority": authority_metadata(context)}
    return payload


def has_authority_control_plane(request: Request) -> bool:
    return (
        getattr(request.app.state, "authority_service", None) is not None
        or getattr(request.app.state, "authority_repository", None) is not None
    )


def _projection_consumer(request: Request) -> AuthorityProjectionConsumer:
    consumer = getattr(request.app.state, "authority_projection_consumer", None)
    if consumer is not None and callable(getattr(consumer, "replay", None)):
        return consumer
    pool = getattr(request.app.state, "durable_job_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "AUTHORITY_UNAVAILABLE", "message": "Projection store unavailable"},
        )
    consumer = AuthorityProjectionConsumer(
        StartupCompatibilityProjectionRepository(pool), authority_service=_service(request)
    )
    request.app.state.authority_projection_consumer = consumer
    return consumer


@router.get("/api/authority/status")
async def authority_status(request: Request):
    return authority_metadata(await authority_for_request(request))


@router.post("/api/authority/transition")
async def transition_authority(request: Request, body: TransitionBody):
    # The authenticated tenant is also the sole operator/actor identity; no body
    # field can select or impersonate another tenant.
    user_id = require_authenticated_user(request)
    try:
        record = await _service(request).transition(
            user_id=user_id,
            expected_version=body.expected_version,
            target_mode=body.target_mode,
            actor_id=user_id,
            snapshot_id=body.snapshot_id,
        )
    except (AuthorityConflict, AuthorityTransitionError, AuthorityBlocked) as exc:
        raise _conflict(exc) from exc
    return rollout_payload(record)


@router.post("/api/authority/rollback")
async def rollback_authority(request: Request, body: RollbackBody):
    user_id = require_authenticated_user(request)
    try:
        record = await _service(request).rollback(
            user_id=user_id,
            expected_version=body.expected_version,
            actor_id=user_id,
            reason=body.reason,
        )
    except (AuthorityConflict, AuthorityTransitionError, AuthorityBlocked) as exc:
        raise _conflict(exc) from exc
    return rollout_payload(record)


@router.post("/api/authority/replay-projection")
async def replay_authority_projection(request: Request, body: ReplayProjectionBody):
    user_id = require_authenticated_user(request)
    selector = {"event_id": body.event_id} if body.event_id else {"opportunity_id": body.opportunity_id}
    applied = await _projection_consumer(request).replay(user_id=user_id, **selector)
    return {"applied": applied}

@router.post("/api/authority/reconciliation")
async def update_reconciliation(request: Request, body: ReconciliationBody):
    user_id = require_authenticated_user(request)
    try:
        record = await _service(request).set_reconciliation_status(
            user_id=user_id, expected_version=body.expected_version,
            actor_id=user_id, status=body.status,
        )
    except (AuthorityConflict, AuthorityTransitionError, AuthorityBlocked, ValueError) as exc:
        raise _conflict(exc) from exc
    return rollout_payload(record)


__all__ = [
    "authority_for_request",
    "authority_metadata",
    "has_authority_control_plane",
    "require_write_path",
    "router",
    "with_authority_metadata",
]
