from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ingest.service import CompanyImportService, ImportRowError
from security.request_guards import require_authenticated_user

router = APIRouter(tags=["imports"])


class ImportBody(BaseModel):
    import_id: str = Field(min_length=1, max_length=200)
    rows: List[Dict[str, Any]] = Field(min_length=1, max_length=500)


@router.post("/api/imports/companies")
async def import_companies(request: Request, body: ImportBody):
    user_id = require_authenticated_user(request)
    repository = getattr(request.app.state, "identity_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Canonical identity store unavailable")
    try:
        return await CompanyImportService(repository).ingest_rows(
            user_id=user_id, rows=body.rows, import_id=body.import_id
        )
    except ImportRowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
