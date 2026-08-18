from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ingest.service import CompanyImportService, ImportRowError
from routers.deps import enforce_rate_limits
from security.rate_limiter import RateLimitPolicy
from security.request_guards import require_authenticated_user

router = APIRouter(tags=["imports"])

# Fresh audit MEDIUM: every other mutating endpoint (manual-lookup, admin
# login/overview, settings mutation) is rate-limited; this one accepts up to
# 500 rows per call and had no throttle at all -- an authenticated user could
# loop it for unbounded write volume into the canonical identity store.
_IMPORT_MINUTE_POLICY = RateLimitPolicy("import_companies_minute", limit=5, window_seconds=60)
_IMPORT_HOUR_POLICY = RateLimitPolicy("import_companies_hour", limit=20, window_seconds=3600)


class ImportBody(BaseModel):
    import_id: str = Field(min_length=1, max_length=200)
    rows: List[Dict[str, Any]] = Field(min_length=1, max_length=500)


@router.post("/api/imports/companies")
async def import_companies(request: Request, body: ImportBody):
    user_id = require_authenticated_user(request)
    limited = await enforce_rate_limits(
        f"user:{user_id}:import_companies", [_IMPORT_MINUTE_POLICY, _IMPORT_HOUR_POLICY]
    )
    if limited is not None:
        return limited
    repository = getattr(request.app.state, "identity_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Canonical identity store unavailable")
    try:
        return await CompanyImportService(repository).ingest_rows(
            user_id=user_id, rows=body.rows, import_id=body.import_id
        )
    except ImportRowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
