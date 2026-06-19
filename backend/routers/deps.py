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
from datetime import datetime, timezone, timedelta
import json
from portfolio.cost_control import CostController
from utils.settings_loader import is_cost_budget_enabled
from utils.timeutil import utcnow, ensure_aware

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
        from supabase_doc_store import doc_get
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
    storage: Union[Storage, SupabaseStartupsStorage],
) -> List[Dict[str, Any]]:
    """
    Return raw startup dicts where partner_info.human_review_required is True
    and no human_resolution has been recorded.
    """
    if isinstance(storage, SupabaseStartupsStorage):
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


def startup_name_index(storage: Union[Storage, SupabaseStartupsStorage]) -> Dict[str, str]:
    """startup_id -> display name without loading full startup JSON when on Supabase."""
    if isinstance(storage, SupabaseStartupsStorage):
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
    storage: Union[Storage, SupabaseStartupsStorage],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assemble system health object from multiple backend sources.
    Mirrors the shape expected by the front-end SystemHealth type.
    budget_status is only populated when cost_budget.enabled for this user.
    """
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
    pending_escalations = len(get_pending_escalations(storage))

    # Queue depths
    try:
        unreviewed = storage.count_unreviewed()
    except Exception:
        unreviewed = 0
    try:
        undecided = storage.count_undecided()
    except Exception:
        undecided = 0
    try:
        watchlist = len(portfolio_store.get_all_watchlist()) if portfolio_store else 0
    except Exception:
        watchlist = 0

    # Budget status only when cost budget enforcement is enabled for this user
    budget_status: List[Dict[str, Any]] = []
    if is_cost_budget_enabled(user_id):
        cost_controller = CostController(user_id=user_id)
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
                        (last_call_time.replace(tzinfo=timezone.utc) + timedelta(seconds=cooldown_seconds)).isoformat()
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
        "calibration_warning": calibration_warning,
        "pending_escalations": pending_escalations,
        "queue_depths": {
            "unreviewed": unreviewed,
            "undecided": undecided,
            "watchlist": watchlist,
        },
        "budget_status": budget_status,
    }
