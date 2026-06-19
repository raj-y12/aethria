"""Shared request guard helpers for authenticated, tenant-scoped routes."""

from __future__ import annotations

import os
import env_config
import re
from typing import Any

from fastapi import HTTPException, Request

_ROUTE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def require_authenticated_user(request: Request | Any) -> str:
    """Return Clerk user_id from request.state or raise 401."""
    user_id = str(getattr(getattr(request, "state", None), "user_id", "") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def validate_route_id(value: Any, *, field_name: str = "id") -> str:
    """Validate path/query identifiers used for tenant-scoped records."""
    raw = str(value or "").strip()
    if not raw or not (_ROUTE_ID_RE.match(raw) or _UUID_RE.match(raw)):
        raise HTTPException(status_code=422, detail=f"{field_name} has invalid format")
    return raw


def require_supabase_enabled_for_pipeline() -> None:
    if not env_config.use_supabase_storage():
        raise HTTPException(status_code=503, detail="Supabase storage is required for this operation")


def require_openai_enabled_for_ai_route() -> None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for this operation")
