"""Shared infrastructure for the API routers.

``api.py`` used to be a ~3.7k-line monolith holding the app, middleware,
lifespan, queue workers, and every route handler. Routes are now grouped into
``backend/routers/*.py`` modules. To avoid a circular import (``api`` includes
the routers; the routers need ``api``'s helpers), the genuinely shared,
app-wide helpers live here and are imported by both ``api.py`` and the routers.

What stays in ``api.py``: the FastAPI app, CORS + Clerk auth middleware, the
lifespan, the agent/lookup queues + per-user loop machinery, and the route
groups tightly coupled to that stateful machinery (agents, on-demand lookup,
SSE stream). What moves to routers: the self-contained groups (meta, fund
thesis, settings, analytics).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, Request

import env_config
from security.rate_limiter import (
    FixedWindowRateLimiter,
    RateLimitPolicy,
    build_security_store,
    rate_limit_exceeded,
)
from supabase_client import get_service_client
from supabase_storage import SupabaseStartupsStorage
from portfolio.store import PortfolioStore
from utils.storage import Storage

logger = logging.getLogger("api.deps")

# --- Rate-limit policies (shared across routers + api) ----------------------
LOOKUP_MINUTE_POLICY = RateLimitPolicy("lookup_minute", limit=5, window_seconds=60)
LOOKUP_DAY_POLICY = RateLimitPolicy("lookup_day", limit=50, window_seconds=86400)
AGENT_TRIGGER_POLICY = RateLimitPolicy("agent_trigger_minute", limit=1, window_seconds=60)
META_TRIGGER_POLICY = RateLimitPolicy("meta_trigger_hour", limit=1, window_seconds=3600)
SETTINGS_MUTATION_POLICY = RateLimitPolicy("settings_mutation_minute", limit=30, window_seconds=60)
ADMIN_LOGIN_POLICY = RateLimitPolicy("admin_login_minute", limit=10, window_seconds=60)
ADMIN_OVERVIEW_POLICY = RateLimitPolicy("admin_overview_minute", limit=30, window_seconds=60)

# --- Security store + rate limiting -----------------------------------------
_security_store = None


def get_security_store():
    global _security_store
    if _security_store is None:
        _security_store = build_security_store()
    return _security_store


def enforce_rate_limits(key: str, policies: List[RateLimitPolicy]):
    limiter = FixedWindowRateLimiter(store=get_security_store())
    for policy in policies:
        decision = limiter.check(key, policy)
        if not decision.allowed:
            return rate_limit_exceeded(retry_after_seconds=decision.retry_after_seconds)
    return None


def acquire_security_lock(key: str, *, ttl_seconds: int) -> bool:
    return bool(get_security_store().acquire_lock(f"lock:{key}", ttl_seconds=ttl_seconds))


def release_security_lock(key: Optional[str]) -> None:
    if not key:
        return
    try:
        get_security_store().release_lock(f"lock:{key}")
    except Exception as exc:
        logger.debug("security lock release failed key=%s error=%s", key, exc)


# --- Request / environment helpers ------------------------------------------
def client_host(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return (request.client.host if request.client else "") or "unknown"


def is_production_env() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("FASTAPI_ENV") or "").lower()
    return env in ("production", "prod")


def now_iso() -> str:
    """Current time as an ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def get_root() -> Path:
    return Path(__file__).resolve().parent.parent


# --- Storage helpers --------------------------------------------------------
def get_storage(request: Request) -> SupabaseStartupsStorage:
    """Supabase startups storage for the authenticated user (service-role client)."""
    return SupabaseStartupsStorage(get_service_client(), request.state.user_id)


def get_portfolio_store(user_id: str) -> PortfolioStore:
    """PortfolioStore for the authenticated tenant (explicit user_id)."""
    root = get_root()
    return PortfolioStore(data_dir=str(root / "data" / "portfolio"), user_id=user_id)


def require_supabase_for_thesis() -> None:
    if (
        not env_config.use_supabase_storage()
        or not os.getenv("SUPABASE_URL")
        or not os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    ):
        raise HTTPException(status_code=503, detail="Supabase storage is required for fund thesis")


def safe_table_execute(fn, *, default_data, warn_label: str):
    """Best-effort supabase query wrapper for non-critical API enrichments."""
    try:
        return fn()
    except Exception as e:
        logger.warning("%s failed; returning fallback: %s", warn_label, e)
        return default_data
