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

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from fastapi import HTTPException, Request

import env_config
from security.rate_limiter import (
    FixedWindowRateLimiter,
    InMemorySecurityStore,
    RateLimitPolicy,
    rate_limit_exceeded,
)
from security.repository import SecurityRepository
from portfolio.store import PortfolioStore
from portfolio.cost_control import CostController
from utils.storage import Storage
from utils.timeutil import utcnow, ensure_aware
from startup_repository import StartupRepository

logger = logging.getLogger("api.deps")

# --- Rate-limit policies (shared across routers + api) ----------------------
LOOKUP_MINUTE_POLICY = RateLimitPolicy("lookup_minute", limit=5, window_seconds=60)
LOOKUP_DAY_POLICY = RateLimitPolicy("lookup_day", limit=50, window_seconds=86400)
# Candidate resolution is cheap (deterministic, LLM-free) so it gets its own,
# looser bucket — a disambiguation resolve must not eat the queue's lookup budget.
RESOLVE_MINUTE_POLICY = RateLimitPolicy("resolve_minute", limit=30, window_seconds=60)
AGENT_TRIGGER_POLICY = RateLimitPolicy("agent_trigger_minute", limit=1, window_seconds=60)
META_TRIGGER_POLICY = RateLimitPolicy("meta_trigger_hour", limit=1, window_seconds=3600)
SETTINGS_MUTATION_POLICY = RateLimitPolicy("settings_mutation_minute", limit=30, window_seconds=60)
ADMIN_LOGIN_POLICY = RateLimitPolicy("admin_login_minute", limit=10, window_seconds=60)
ADMIN_OVERVIEW_POLICY = RateLimitPolicy("admin_overview_minute", limit=30, window_seconds=60)

# --- Provider-neutral security repository + rate limiting -------------------
_security_repository: Optional[SecurityRepository] = None
_security_compat_store = InMemorySecurityStore()
_security_store = _security_compat_store  # compatibility seam for isolated tests
_security_lock_tokens: Dict[str, str] = {}


def configure_security_repository(pool: Any | None) -> None:
    """Bind API security checks to the shared provider-neutral PostgreSQL pool."""
    global _security_repository
    _security_repository = SecurityRepository(pool) if pool is not None else None
    _security_lock_tokens.clear()


def get_security_store():
    """Return the process-local compatibility store for isolated non-production tests."""
    return _security_store


def _configured_security_repository(pool: Any | None = None) -> Optional[SecurityRepository]:
    if pool is not None:
        return SecurityRepository(pool)
    return _security_repository


async def enforce_rate_limits(
    key: str,
    policies: List[RateLimitPolicy],
    *,
    pool: Any | None = None,
):
    repository = _configured_security_repository(pool)
    if repository is None:
        if env_config.is_production_env():
            raise RuntimeError("security_repository_unavailable")
        limiter = FixedWindowRateLimiter(store=get_security_store())
        for policy in policies:
            decision = limiter.check(key, policy)
            if not decision.allowed:
                return rate_limit_exceeded(retry_after_seconds=decision.retry_after_seconds)
        return None

    now = datetime.now(timezone.utc)
    for policy in policies:
        count, expires_at = await repository.check_rate_limit(
            f"rate:{policy.name}:{key}", window_seconds=policy.window_seconds
        )
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if count > policy.limit:
            retry_after = max(1, int((expires_at - now).total_seconds()))
            return rate_limit_exceeded(retry_after_seconds=retry_after)
    return None


async def acquire_security_lock(
    key: str,
    *,
    ttl_seconds: int,
    pool: Any | None = None,
) -> bool:
    repository = _configured_security_repository(pool)
    storage_key = f"lock:{key}"
    if repository is None:
        if env_config.is_production_env():
            raise RuntimeError("security_repository_unavailable")
        return bool(get_security_store().acquire_lock(storage_key, ttl_seconds=ttl_seconds))
    owner_token = str(uuid4())
    acquired = await repository.acquire_lock(
        storage_key, ttl_seconds=ttl_seconds, owner_token=owner_token
    )
    if acquired:
        _security_lock_tokens[key] = owner_token
    return bool(acquired)


async def release_security_lock(key: Optional[str], *, pool: Any | None = None) -> None:
    if not key:
        return
    repository = _configured_security_repository(pool)
    try:
        if repository is None:
            if env_config.is_production_env():
                raise RuntimeError("security_repository_unavailable")
            get_security_store().release_lock(f"lock:{key}")
            return
        owner_token = _security_lock_tokens.pop(key, None)
        if owner_token:
            await repository.release_lock(f"lock:{key}", owner_token=owner_token)
    except Exception as exc:
        logger.debug("security lock release failed key=%s error=%s", key, exc)


# --- Request / environment helpers ------------------------------------------
def client_host(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return (request.client.host if request.client else "") or "unknown"


def is_production_env() -> bool:
    return env_config.is_production_env()


def now_iso() -> str:
    """Current time as an ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def get_root() -> Path:
    return Path(__file__).resolve().parent.parent


# --- Storage helpers --------------------------------------------------------
def get_service_client():
    """Load the legacy Supabase client only for compatibility routes."""
    from supabase_client import get_service_client as _get_service_client

    return _get_service_client()


def _supabase_storage_type():
    from supabase_storage import SupabaseStartupsStorage

    return SupabaseStartupsStorage


def _is_supabase_storage(value: Any) -> bool:
    return isinstance(value, _supabase_storage_type())


def get_storage(request: Request) -> Any:
    """Supabase startups storage for the authenticated user (service-role client)."""
    return _supabase_storage_type()(get_service_client(), request.state.user_id)


def get_startup_repository(request: Request) -> StartupRepository:
    """Required PostgreSQL authority for normal startup runtime operations."""
    app_state = getattr(getattr(request, "app", None), "state", None)
    pool = getattr(app_state, "durable_job_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STARTUP_REPOSITORY_UNAVAILABLE",
                "message": "Startup PostgreSQL repository is unavailable.",
            },
        )
    return StartupRepository(pool)


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


# ---------------------------------------------------------------------------
# Read helpers + system-health assembly (shared by settings, escalations, analytics)
# ---------------------------------------------------------------------------
def read_json_list(path: Path) -> List[Dict[str, Any]]:
    """Best-effort JSON list reader. Returns [] on missing/invalid files."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def read_json_dict_file(path: Path, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Best-effort reader from Supabase or file. Returns {} on missing/invalid."""
    if path and "sector_concentration" in str(path):
        from batch1.store import doc_get
        data = doc_get("analytics_sector_concentration", user_id=user_id)
        return data if isinstance(data, dict) else {}
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_pending_escalations(
    storage: Union[Storage, Any],
) -> List[Dict[str, Any]]:
    """
    Return raw startup dicts where partner_info.human_review_required is True
    and no human_resolution has been recorded.
    """
    if _is_supabase_storage(storage):
        return storage.query_pending_escalations_raw()
    raw = storage.get_all()
    pending: List[Dict[str, Any]] = []
    for item in raw:
        partner = item.get("partner_info") or item.get("partner")
        if not partner:
            continue
        if not partner.get("human_review_required"):
            continue
        human_resolution = item.get("human_resolution")
        if human_resolution and human_resolution.get("resolved_at"):
            continue
        pending.append(item)
    return pending


def startup_name_index(storage: Union[Storage, Any]) -> Dict[str, str]:
    """startup_id -> display name without loading full startup JSON when on Supabase."""
    if _is_supabase_storage(storage):
        return storage.get_startup_id_name_map()
    out: Dict[str, str] = {}
    for s in storage.get_all():
        sid = s.get("startup_id") or s.get("id")
        if not sid:
            continue
        name = (s.get("scout_info") or {}).get("name") or (s.get("scout") or {}).get("name") or ""
        out[str(sid)] = name
    return out


def get_system_health(
    storage: Union[Storage, Any, None],
    user_id: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    pending_escalations: Optional[int] = None,
    unreviewed: Optional[int] = None,
    undecided: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Assemble system health object from multiple backend sources.
    Mirrors the shape expected by the front-end SystemHealth type.
    budget_status is only populated when cost_budget.enabled for this user.
    """
    health_errors: List[str] = []
    # Calibration warning from portfolio agent_metrics (Supabase)
    portfolio_store = get_portfolio_store(user_id) if user_id else None
    calibration_warning = None
    metrics_file = portfolio_store.files.get("agent_metrics") if portfolio_store else None
    if portfolio_store and metrics_file is not None:
        metrics = portfolio_store._read_file(metrics_file)
        for m in metrics:
            if m.get("id") == "verdict_distribution":
                calibration_warning = m.get("calibration_warning")
                break

    # Pending escalations based on startups requiring human review
    if pending_escalations is None:
        pending_escalations = len(get_pending_escalations(storage)) if storage is not None else 0

    # Queue depths
    if unreviewed is None:
        try:
            unreviewed = storage.count_unreviewed() if storage is not None else 0
        except Exception:
            unreviewed = 0
            health_errors.append("unreviewed_count_unavailable")
    if undecided is None:
        try:
            undecided = storage.count_undecided() if storage is not None else 0
        except Exception:
            undecided = 0
            health_errors.append("undecided_count_unavailable")
    try:
        watchlist = len(portfolio_store.get_all_watchlist()) if portfolio_store else 0
    except Exception:
        watchlist = 0
        health_errors.append("watchlist_count_unavailable")

    # Budget status only when cost budget enforcement is enabled for this user
    budget_status: List[Dict[str, Any]] = []
    if bool((settings or {}).get("cost_budget", {}).get("enabled", False)):
        cost_controller = CostController(user_id=user_id, settings=settings)
        all_budgets: Dict[str, Any] = getattr(cost_controller, "budgets", {}) or {}
        for agent_type, defaults in cost_controller.default_budgets.items():
            agent_budget = all_budgets.get(agent_type, {})
            calls_today = agent_budget.get("calls_today", 0)
            tokens_today = agent_budget.get("tokens_today", 0)
            last_calls = agent_budget.get("last_call_time") or {}
            if not isinstance(last_calls, dict):
                last_calls = {}
            if not last_calls:
                budget_status.append(
                    {
                        "agent_id": agent_type,
                        "daily_calls_used": calls_today,
                        "daily_calls_limit": defaults.get("calls", 0),
                        "daily_tokens_used": tokens_today,
                        "daily_tokens_limit": defaults.get("tokens", 0),
                        "in_cooldown": False,
                        "cooldown_until": None,
                    }
                )
                continue
            for agent_id, last_call_str in last_calls.items():
                try:
                    last_call_time = ensure_aware(datetime.fromisoformat(last_call_str))
                    cooldown_seconds = cost_controller.cooldowns.get(agent_type, 60)
                    delta = (utcnow() - last_call_time).total_seconds()
                    in_cooldown = delta < cooldown_seconds
                    cooldown_until = (
                        (last_call_time + timedelta(seconds=cooldown_seconds)).isoformat()
                        if in_cooldown
                        else None
                    )
                except Exception:
                    in_cooldown = False
                    cooldown_until = None
                budget_status.append(
                    {
                        "agent_id": str(agent_id),
                        "daily_calls_used": calls_today,
                        "daily_calls_limit": defaults.get("calls", 0),
                        "daily_tokens_used": tokens_today,
                        "daily_tokens_limit": defaults.get("tokens", 0),
                        "in_cooldown": in_cooldown,
                        "cooldown_until": cooldown_until,
                    }
                )

    return {
        "status": "degraded" if health_errors else "ok",
        "errors": health_errors,
        "calibration_warning": calibration_warning,
        "pending_escalations": pending_escalations,
        "queue_depths": {
            "unreviewed": unreviewed,
            "undecided": undecided,
            "watchlist": watchlist,
        },
        "budget_status": budget_status,
    }
