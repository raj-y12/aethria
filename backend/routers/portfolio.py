"""Canonical portfolio read API."""

from fastapi import APIRouter, HTTPException, Query, Request

from routers.authority import authority_for_request, has_authority_control_plane, with_authority_metadata
from security.request_guards import require_authenticated_user

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio/positions")
async def list_positions(request: Request, limit: int = Query(default=100, ge=1, le=200)):
    user_id = require_authenticated_user(request)
    repository = getattr(request.app.state, "portfolio_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Portfolio store unavailable")
    records = await repository.list_positions(user_id=user_id, limit=limit)
    payload = {"positions": records}
    if has_authority_control_plane(request):
        return with_authority_metadata(payload, await authority_for_request(request))
    return payload
