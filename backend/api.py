"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
Per-user agent pipeline: POST /api/agents/trigger starts or reuses a persistent user loop when Ops/Agents is on.
When Ops/Agents is off, the same endpoint can enqueue a manual one-shot run.
On-demand lookup uses a separate queue/worker so it is not blocked by full scout/reviewer/partner cycles.
"""
import asyncio
import gc
import json
import logging
import os
import re
import time
from uuid import uuid4
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
    else:
        load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from utils.storage import Storage
from security.rate_limiter import (
    FixedWindowRateLimiter,
    RateLimitPolicy,
    build_security_store,
    rate_limit_exceeded,
    security_event_detail,
)
from security.request_guards import require_authenticated_user, validate_route_id
from utils.settings_loader import (
    DEFAULT_SETTINGS,
    fund_config_content_changed,
    fund_config_raw_text,
    fund_config_to_thesis_parsed_json,
    get_settings_path,
    load_settings,
    save_settings,
    get_meta_agent_settings,
    is_cost_budget_enabled,
)
from auth_clerk import verify_clerk_token
from admin_auth import admin_token_ttl_seconds, issue_admin_token, validate_admin_secret, verify_admin_token
from admin_audit import record_admin_audit_event
from admin_service import build_admin_overview
from supabase_client import get_service_client
from supabase_doc_store import list_get_all, list_get_by_id
from supabase_storage import SupabaseStartupsStorage
from memo_generator import MemoGenerator
from meta.agent import MetaAgent  # For manual trigger
from meta.reweighter import load_weights
from meta.calibrator import load_calibration_state
from meta.prompt_gating import (
    VALID_PROMOTE_AGENT_TARGETS,
    REVIEWER_EVAL_AGENT_TARGETS,
    eval_record_fresh,
    get_last_eval_record,
    load_eval_startup_ids,
    load_prompt_active,
    load_prompt_library,
    save_eval_startup_ids,
    save_prompt_active,
    save_prompt_library,
)
from meta.evaluator import run_prompt_evaluation
from reviewer.engine import ReviewerEngine
from reviewer.aethria_view import polish_aethria_view_for_api
from services.scoring.policy_compiler import PolicyValidationError, compile_policy_from_fund_config
from services.scoring.policy_store import publish_policy
from services.scoring.presentation_layer import serialize_scoring_presentation
from portfolio.store import PortfolioStore
from portfolio.rejection import RejectionAnalyzer
from portfolio.cost_control import CostController
from pipeline_runner import (
    _rss_mb as _pipeline_rss_mb,
    reprocess_startups_missing_fund_thesis,
    run_one_pipeline_cycle,
    run_on_demand_lookup,
)
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisMissingError,
    FundThesisQueryError,
    _bootstrap_default_thesis_or_raise,
    compute_thesis_alignment_stats,
    get_active_thesis,
    thesis_has_embeddings,
)
from fund_thesis_ops import (
    activate_fund_thesis_version,
    create_fund_thesis_version_for_user,
    sync_fund_config_to_active_thesis,
)
from models import FundConfig, FundMemory, Startup, UserPreferences
from conviction_state import build_conviction_patch
from core import policy_resolver
from utils.scoring import compute_overall_score, enrich_scores, score_to_label
from utils.score_semantics import rubric_band_for_numeric
from utils.partner_codes import LEGACY_TO_RECOMMENDATION, recommendation_from_legacy

_agent_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_agent_worker_task: Optional[asyncio.Task] = None
_lookup_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_lookup_worker_task: Optional[asyncio.Task] = None
_logger_agents = logging.getLogger("api.agents")
_logger_visible = logging.getLogger("uvicorn.error")
_LOOKUP_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")
_LOOKUP_LEADING_PHRASE_RE = re.compile(
    r"(?i)^\s*(?:find|lookup|look\s+up|search(?:\s+for)?|analy[sz]e|evaluate|check(?:\s+out)?|research)\s+"
)
_LOOKUP_TRAILING_QUALIFIERS = {"company", "startup", "website", "profile"}
_LOOKUP_COMMAND_ONLY_PHRASES = {
    "find",
    "lookup",
    "look up",
    "search",
    "search for",
    "analyze",
    "analyse",
    "evaluate",
    "check",
    "check out",
    "research",
}

# Per-user persistent agent loops: user_id -> asyncio.Task
# Protected by _loops_lock to prevent duplicate tasks per user.
_per_user_loops: Dict[str, asyncio.Task] = {}
_per_user_loop_wake_events: Dict[str, asyncio.Event] = {}
_loops_lock: Optional[asyncio.Lock] = None  # initialised inside lifespan (event loop must exist)
AGENT_LOOP_INTERVAL_SECONDS = int(os.getenv("AGENT_LOOP_INTERVAL_SECONDS", "300"))
# On small Render instances, resuming every user's loop at startup can OOM before the app is healthy.
RESUME_AGENT_LOOPS_ON_STARTUP = os.getenv("RESUME_AGENT_LOOPS_ON_STARTUP", "true").lower() in (
    "1",
    "true",
    "yes",
)
# 0 = no cap; otherwise max persistent loops resumed after restart.
MAX_RESUMED_AGENT_LOOPS = max(0, int(os.getenv("MAX_RESUMED_AGENT_LOOPS", "0")))
_ADMIN_LOGIN_MAX_FAILURES = int(os.getenv("ADMIN_LOGIN_MAX_FAILURES", "5"))
_ADMIN_LOGIN_WINDOW_SECONDS = int(os.getenv("ADMIN_LOGIN_WINDOW_SECONDS", "300"))
_admin_login_attempts: Dict[str, List[float]] = {}
_security_store = None

_LOOKUP_MINUTE_POLICY = RateLimitPolicy("lookup_minute", limit=5, window_seconds=60)
_LOOKUP_DAY_POLICY = RateLimitPolicy("lookup_day", limit=50, window_seconds=86400)
_AGENT_TRIGGER_POLICY = RateLimitPolicy("agent_trigger_minute", limit=1, window_seconds=60)
_META_TRIGGER_POLICY = RateLimitPolicy("meta_trigger_hour", limit=1, window_seconds=3600)
_SETTINGS_MUTATION_POLICY = RateLimitPolicy("settings_mutation_minute", limit=30, window_seconds=60)
_ADMIN_LOGIN_POLICY = RateLimitPolicy("admin_login_minute", limit=10, window_seconds=60)
_ADMIN_OVERVIEW_POLICY = RateLimitPolicy("admin_overview_minute", limit=30, window_seconds=60)

_AGENT_TRIGGER_LOCK_TTL_SECONDS = int(os.getenv("AGENT_TRIGGER_LOCK_TTL_SECONDS", "900"))
_LOOKUP_LOCK_TTL_SECONDS = int(os.getenv("LOOKUP_LOCK_TTL_SECONDS", "900"))
_META_TRIGGER_LOCK_TTL_SECONDS = int(os.getenv("META_TRIGGER_LOCK_TTL_SECONDS", "900"))
DEFAULT_STARTUPS_LIST_LIMIT = max(1, min(int(os.getenv("STARTUPS_LIST_DEFAULT_LIMIT", "250")), 500))
MAX_STARTUPS_LIST_LIMIT = max(
    DEFAULT_STARTUPS_LIST_LIMIT,
    min(int(os.getenv("STARTUPS_LIST_MAX_LIMIT", "500")), 1000),
)


def _safe_table_execute(fn, *, default_data, warn_label: str):
    """Best-effort supabase query wrapper for non-critical API enrichments."""
    try:
        return fn()
    except Exception as e:
        _logger_agents.warning("%s failed; returning fallback: %s", warn_label, e)
        return default_data


def _is_retryable_thesis_transport_error(err: Exception) -> bool:
    if isinstance(err, httpx.HTTPError):
        return True
    if isinstance(err, OSError) and getattr(err, "errno", None) == 11:
        return True
    err_name = type(err).__name__
    return err_name in {
        "ReadError",
        "ConnectError",
        "TimeoutException",
        "HTTPError",
        "RemoteProtocolError",
        "ProtocolError",
        "TransportError",
    }


async def _agent_worker() -> None:
    """Background worker: full scout/reviewer/partner cycles only (not on-demand lookup)."""
    if _agent_queue is None:
        return
    while True:
        try:
            job = await _agent_queue.get()
            user_id = str(job.get("user_id") or "").strip()
            try:
                await run_one_pipeline_cycle(
                    user_id,
                    manual_one_shot=bool(job.get("manual_one_shot")),
                )
            except Exception as e:
                _logger_agents.exception("Pipeline cycle error for user %s: %s", user_id[:12] if user_id else "?", e)
            finally:
                _release_security_lock(str(job.get("lock_key") or "").strip() or None)
                _agent_queue.task_done()
        except asyncio.CancelledError:
            break


async def _lookup_worker() -> None:
    """Dedicated worker for POST /api/startups/lookup — does not wait behind pipeline cycles."""
    if _lookup_queue is None:
        return
    while True:
        try:
            job = await _lookup_queue.get()
            user_id = str(job.get("user_id") or "").strip()
            try:
                await run_on_demand_lookup(
                    user_id,
                    str(job.get("company_name") or ""),
                    website=str(job.get("website") or "").strip() or None,
                    lookup_query=str(job.get("lookup_query") or "").strip() or None,
                    lookup_input_type=str(job.get("lookup_input_type") or "").strip() or None,
                    lookup_id=str(job.get("lookup_id") or "").strip() or None,
                )
            except Exception as e:
                _logger_agents.exception(
                    "On-demand lookup error for user %s: %s",
                    user_id[:12] if user_id else "?",
                    e,
                )
            finally:
                _release_security_lock(str(job.get("lock_key") or "").strip() or None)
                _lookup_queue.task_done()
        except asyncio.CancelledError:
            break


# ---------------------------------------------------------------------------
# Per-user persistent loop helpers
# ---------------------------------------------------------------------------

def _is_user_agents_enabled(user_id: str) -> bool:
    """Sync check — safe to call from inside the async loop (no await)."""
    try:
        s = load_settings(user_id, use_cache=False)
        ac = s.get("agent_config") or {}
        return bool(ac.get("scouts_enabled") or ac.get("reviewers_enabled") or ac.get("partners_enabled"))
    except Exception:
        return False


def _agents_enabled_from_settings(settings: Dict[str, Any]) -> bool:
    ac = settings.get("agent_config") or {}
    return bool(
        ac.get("scouts_enabled", False)
        or ac.get("reviewers_enabled", False)
        or ac.get("partners_enabled", False)
    )


def _is_user_loop_alive(user_id: str) -> bool:
    task = _per_user_loops.get(user_id)
    return task is not None and not task.done()


async def _update_agent_run_status(user_id: str, status: str) -> None:
    """Best-effort: write agents_status (and last_started_at when running) into settings doc."""
    try:
        s = load_settings(user_id)
        ac = s.setdefault("agent_config", {})
        ac["agents_status"] = status
        if status == "running":
            ac["agents_last_started_at"] = datetime.now(timezone.utc).isoformat()
        save_settings(s, user_id)
    except Exception as e:
        _logger_agents.debug("[%s] Could not update agent status: %s", user_id[:12], e)


async def _user_agent_loop(user_id: str) -> None:
    """
    Persistent background loop for a single user.
    Runs until agents are disabled in settings or the task is cancelled.
    """
    _logger_agents.info("[AGENT LOOP] Started persistent loop for user %s", user_id[:12])
    _logger_visible.info("[AGENT LOOP] Started for user %s", user_id[:12])
    try:
        while True:
            # Re-check enabled flag at the top of every iteration (settings can change)
            if not _is_user_agents_enabled(user_id):
                _logger_agents.info("[AGENT LOOP] Stopped because Ops/Agents is OFF for user %s", user_id[:12])
                _logger_visible.info("[AGENT LOOP] Stopped because Ops/Agents is OFF for user %s", user_id[:12])
                await _update_agent_run_status(user_id, "stopped")
                break
            cycle_started_at = time.perf_counter()
            _logger_agents.info(
                "[AGENT LOOP] Cycle started user=%s rss_mb_before=%.1f",
                user_id[:12],
                _pipeline_rss_mb(),
            )
            try:
                await run_one_pipeline_cycle(user_id)
                _logger_agents.info(
                    "[AGENT LOOP] Cycle completed user=%s duration_s=%.2f rss_mb_after=%.1f",
                    user_id[:12],
                    time.perf_counter() - cycle_started_at,
                    _pipeline_rss_mb(),
                )
                await _update_agent_run_status(user_id, "running")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _logger_agents.exception(
                    "[AGENT LOOP] Cycle failed user=%s duration_s=%.2f rss_mb_after=%.1f error=%s",
                    user_id[:12],
                    time.perf_counter() - cycle_started_at,
                    _pipeline_rss_mb(),
                    exc,
                )
                await _update_agent_run_status(user_id, "error")
            finally:
                gc.collect()
                _logger_agents.info(
                    "[AGENT LOOP] Cycle cleanup complete user=%s rss_mb_after_cleanup=%.1f",
                    user_id[:12],
                    _pipeline_rss_mb(),
                )
            if not _is_user_agents_enabled(user_id):
                _logger_agents.info("[AGENT LOOP] Stopped because Ops/Agents is OFF for user %s", user_id[:12])
                _logger_visible.info("[AGENT LOOP] Stopped because Ops/Agents is OFF for user %s", user_id[:12])
                await _update_agent_run_status(user_id, "stopped")
                break
            _logger_agents.info(
                "[AGENT LOOP] Loop sleeping user=%s sleep_seconds=%s",
                user_id[:12],
                AGENT_LOOP_INTERVAL_SECONDS,
            )
            wake_event = _per_user_loop_wake_events.get(user_id)
            if wake_event is None:
                await asyncio.sleep(AGENT_LOOP_INTERVAL_SECONDS)
            else:
                try:
                    await asyncio.wait_for(
                        wake_event.wait(),
                        timeout=AGENT_LOOP_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    pass
                wake_event.clear()
    except asyncio.CancelledError:
        _logger_agents.info("[AGENT LOOP] Cancelled for user %s", user_id[:12])
        raise
    finally:
        # Remove self from registry when done (cancelled or naturally stopped)
        _per_user_loops.pop(user_id, None)
        _per_user_loop_wake_events.pop(user_id, None)
        _logger_agents.info("[AGENT LOOP] Exiting loop for user %s", user_id[:12])


async def _ensure_user_loop(user_id: str) -> bool:
    """Start a persistent loop for user_id if one is not already alive."""
    global _loops_lock
    if _loops_lock is None:
        return False
    async with _loops_lock:
        task = _per_user_loops.get(user_id)
        if task is not None and not task.done():
            _logger_agents.info(
                "[AGENT LOOP] Trigger ignored because loop already running for user %s",
                user_id[:12],
            )
            return False
        t = asyncio.create_task(
            _user_agent_loop(user_id),
            name=f"agent_loop_{user_id[:12]}",
        )
        _per_user_loops[user_id] = t
        _per_user_loop_wake_events[user_id] = asyncio.Event()
        _logger_agents.info("[AGENT LOOP] Registered loop task for user %s", user_id[:12])
        return True


async def _stop_user_loop(user_id: str) -> None:
    """Signal the loop to stop after the active disposable cycle finishes."""
    global _loops_lock
    if _loops_lock is None:
        return
    async with _loops_lock:
        task = _per_user_loops.get(user_id)
        wake_event = _per_user_loop_wake_events.get(user_id)
        if wake_event is not None:
            wake_event.set()
    if task and not task.done():
        _logger_agents.info("[AGENT LOOP] Stop requested for user %s", user_id[:12])
    else:
        _per_user_loops.pop(user_id, None)
        _per_user_loop_wake_events.pop(user_id, None)
        _logger_agents.info("[AGENT LOOP] No live loop to stop for user %s", user_id[:12])


async def _resume_all_user_loops() -> None:
    """
    Called once at server startup.
    Queries Supabase settings for all users with any agent enabled
    and resumes their persistent loops (handles server restarts gracefully).
    """
    if not RESUME_AGENT_LOOPS_ON_STARTUP:
        _logger_agents.info(
            "[AGENT LOOP] Skipping resume on startup (RESUME_AGENT_LOOPS_ON_STARTUP=false)"
        )
        return
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        return
    try:
        client = get_service_client()
        rows_resp = client.table("settings").select("user_id,data").execute()
        rows = getattr(rows_resp, "data", None) or []
        resumed = 0
        for row in rows:
            if MAX_RESUMED_AGENT_LOOPS and resumed >= MAX_RESUMED_AGENT_LOOPS:
                _logger_agents.warning(
                    "[AGENT LOOP] Resume cap reached (%d); remaining users will start loops on next login/trigger",
                    MAX_RESUMED_AGENT_LOOPS,
                )
                break
            uid = (row.get("user_id") or "").strip()
            if not uid:
                continue
            data = row.get("data") or {}
            ac = (data.get("agent_config") or {}) if isinstance(data, dict) else {}
            if ac.get("scouts_enabled") or ac.get("reviewers_enabled") or ac.get("partners_enabled"):
                await _ensure_user_loop(uid)
                resumed += 1
        if resumed:
            _logger_agents.info("[AGENT LOOP] Resumed %d per-user loop(s) on startup", resumed)
            _logger_visible.info("[AGENT LOOP] Resumed %d per-user agent loop(s) after server restart", resumed)
        else:
            _logger_agents.info("[AGENT LOOP] No active users to resume on startup")
    except Exception as exc:
        _logger_agents.warning("[AGENT LOOP] Could not resume user loops on startup: %s", exc)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _agent_queue, _agent_worker_task, _lookup_queue, _lookup_worker_task, _loops_lock
    _loops_lock = asyncio.Lock()
    _agent_queue = asyncio.Queue()
    _lookup_queue = asyncio.Queue()
    _agent_worker_task = asyncio.create_task(_agent_worker())
    _lookup_worker_task = asyncio.create_task(_lookup_worker())
    _logger_agents.info("Pipeline agent worker + on-demand lookup worker started")
    # Resume persistent per-user loops for users that had agents enabled before restart
    await _resume_all_user_loops()
    yield
    # Cancel all per-user loops first
    loop_tasks = list(_per_user_loops.values())
    for t in loop_tasks:
        t.cancel()
    for t in loop_tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass
    # Cancel queue workers
    for t in (_lookup_worker_task, _agent_worker_task):
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    _logger_agents.info("Pipeline agent worker + on-demand lookup worker stopped")


app = FastAPI(title="Aethria API", lifespan=_lifespan)

# CORS: localhost for dev; extend with ALLOWED_ORIGINS (comma-separated) for production domain
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_extra = os.getenv("ALLOWED_ORIGINS", "")
if _extra:
    _cors_origins.extend(o.strip() for o in _extra.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "PATCH", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _get_security_store():
    global _security_store
    if _security_store is None:
        _security_store = build_security_store()
    return _security_store


def _enforce_rate_limits(key: str, policies: List[RateLimitPolicy]):
    limiter = FixedWindowRateLimiter(store=_get_security_store())
    for policy in policies:
        decision = limiter.check(key, policy)
        if not decision.allowed:
            return rate_limit_exceeded(retry_after_seconds=decision.retry_after_seconds)
    return None


def _acquire_security_lock(key: str, *, ttl_seconds: int) -> bool:
    return bool(_get_security_store().acquire_lock(f"lock:{key}", ttl_seconds=ttl_seconds))


def _release_security_lock(key: Optional[str]) -> None:
    if not key:
        return
    try:
        _get_security_store().release_lock(f"lock:{key}")
    except Exception as exc:
        _logger_agents.debug("security lock release failed key=%s error=%s", key, exc)


def _client_host(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return (request.client.host if request.client else "") or "unknown"


def _is_production_env() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("FASTAPI_ENV") or "").lower()
    return env in ("production", "prod")


def _admin_dashboard_enabled() -> bool:
    raw = os.getenv("ADMIN_DASHBOARD_ENABLED")
    if _is_production_env():
        return str(raw or "").lower() in ("1", "true", "yes")
    return str(raw or "true").lower() not in ("0", "false", "no")


# Public paths that skip Clerk JWT auth
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/redoc/", "/openapi.json/"}
_ADMIN_PATH_PREFIX = "/api/admin/"

@app.middleware("http")
async def clerk_auth_middleware(request: Request, call_next):
    """Extract Bearer token, verify Clerk JWT, attach user_id to request.state. Return 401 if invalid."""
    if request.method == "OPTIONS":
        return await call_next(request)
    if (
        _is_production_env()
        and str(os.getenv("PUBLIC_API_DOCS_ENABLED") or "").lower() not in ("1", "true", "yes")
        and (request.url.path in {"/docs", "/openapi.json", "/redoc", "/redoc/", "/openapi.json/"})
    ):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    if (
        request.url.path in _PUBLIC_PATHS
        or request.url.path.rstrip("/") in _PUBLIC_PATHS
        or request.url.path.startswith(_ADMIN_PATH_PREFIX)
    ):
        return await call_next(request)
    auth = request.headers.get("Authorization")
    token = None
    if auth and auth.startswith("Bearer "):
        token = auth[7:].strip()
    user_id = verify_clerk_token(token) if token else None
    if not user_id:
        import logging
        log = logging.getLogger("auth")
        if not token:
            log.info("Auth 401: no Bearer token on %s", request.url.path)
        else:
            log.info("Auth 401: invalid or expired token on %s", request.url.path)
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid authorization token"},
        )
    request.state.user_id = user_id
    request.state.clerk_jwt = token
    return await call_next(request)


def _now_iso() -> str:
    """Return current time as ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _get_root() -> Path:
    return Path(__file__).resolve().parent


def _get_portfolio_store(user_id: str) -> PortfolioStore:
    """Return a PortfolioStore for the authenticated tenant (explicit user_id)."""
    root = _get_root()
    return PortfolioStore(data_dir=str(root / "data" / "portfolio"), user_id=user_id)


def _read_json_list(path: Path) -> List[Dict[str, Any]]:
    """Best-effort JSON list reader. Returns [] on missing/invalid files."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _read_json_dict_file(path: Path, user_id: Optional[str] = None) -> Dict[str, Any]:
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


def _get_pending_escalations(
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


def _startup_name_index(storage: Union[Storage, SupabaseStartupsStorage]) -> Dict[str, str]:
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


def _get_system_health(
    storage: Union[Storage, SupabaseStartupsStorage],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assemble system health object from multiple backend sources.
    Mirrors the shape expected by the front-end SystemHealth type.
    budget_status is only populated when cost_budget.enabled for this user.
    """
    # Calibration warning from portfolio agent_metrics (Supabase)
    portfolio_store = _get_portfolio_store(user_id) if user_id else None
    calibration_warning = None
    metrics_file = portfolio_store.files.get("agent_metrics") if portfolio_store else None
    if portfolio_store and metrics_file is not None:
        metrics = portfolio_store._read_file(metrics_file)
        for m in metrics:
            if m.get("id") == "verdict_distribution":
                calibration_warning = m.get("calibration_warning")
                break

    # Pending escalations based on startups requiring human review
    pending_escalations = len(_get_pending_escalations(storage))

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
                    last_call_time = datetime.fromisoformat(last_call_str)
                    cooldown_seconds = cost_controller.cooldowns.get(agent_type, 60)
                    delta = (datetime.now() - last_call_time).total_seconds()
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

def _save_settings(data: dict, user_id: str) -> None:
    save_settings(data, user_id)


def _validate_settings(body: dict) -> list[str]:
    errors = []
    fc = body.get("fund_config")
    if fc is not None:
        if not isinstance(fc, dict):
            errors.append("fund_config must be an object")
        else:
            try:
                FundConfig.model_validate(fc)
            except Exception as exc:
                errors.append(f"fund_config is invalid: {exc}")
    up = body.get("user_preferences")
    if up is not None:
        if not isinstance(up, dict):
            errors.append("user_preferences must be an object")
        else:
            try:
                UserPreferences.model_validate(up)
            except Exception as exc:
                errors.append(f"user_preferences is invalid: {exc}")
    fm = body.get("fund_memory")
    if fm is not None:
        if not isinstance(fm, dict):
            errors.append("fund_memory must be an object")
        else:
            try:
                FundMemory.model_validate(fm)
            except Exception as exc:
                errors.append(f"fund_memory is invalid: {exc}")
    cb = body.get("cost_budget")
    if cb is not None:
        if not isinstance(cb, dict):
            errors.append("cost_budget must be an object")
        else:
            if "enabled" in cb and not isinstance(cb["enabled"], bool):
                errors.append("cost_budget.enabled must be a boolean")
            if "max_tokens_per_run" in cb and (not isinstance(cb["max_tokens_per_run"], (int, float)) or cb["max_tokens_per_run"] < 0):
                errors.append("cost_budget.max_tokens_per_run must be a non-negative number")
            if "daily_cost_ceiling" in cb and (not isinstance(cb["daily_cost_ceiling"], (int, float)) or cb["daily_cost_ceiling"] < 0):
                errors.append("cost_budget.daily_cost_ceiling must be a non-negative number")
            if "weekly_cost_ceiling" in cb and (not isinstance(cb["weekly_cost_ceiling"], (int, float)) or cb["weekly_cost_ceiling"] < 0):
                errors.append("cost_budget.weekly_cost_ceiling must be a non-negative number")
            if "cooldown_seconds" in cb and (not isinstance(cb["cooldown_seconds"], (int, float)) or cb["cooldown_seconds"] < 0):
                errors.append("cost_budget.cooldown_seconds must be a non-negative number")
    ac = body.get("agent_config")
    if ac is not None:
        if not isinstance(ac, dict):
            errors.append("agent_config must be an object")
        else:
            if "scouts_enabled" in ac and not isinstance(ac["scouts_enabled"], bool):
                errors.append("agent_config.scouts_enabled must be a boolean")
            if "reviewers_enabled" in ac and not isinstance(ac["reviewers_enabled"], bool):
                errors.append("agent_config.reviewers_enabled must be a boolean")
            if "partners_enabled" in ac and not isinstance(ac["partners_enabled"], bool):
                errors.append("agent_config.partners_enabled must be a boolean")
            if "max_agents_per_run" in ac and (not isinstance(ac["max_agents_per_run"], (int, float)) or ac["max_agents_per_run"] < 1):
                errors.append("agent_config.max_agents_per_run must be at least 1")
            if "confidence_threshold" in ac:
                v = ac["confidence_threshold"]
                if not isinstance(v, (int, float, str)):
                    errors.append("agent_config.confidence_threshold must be a number or string")
                elif isinstance(v, (int, float)) and (v < 0 or v > 1):
                    errors.append("agent_config.confidence_threshold must be between 0 and 1 when numeric")
            # Scout-specific config
            if "scout_region" in ac:
                if not isinstance(ac["scout_region"], str):
                    errors.append("agent_config.scout_region must be a string")
                elif ac["scout_region"] not in ("europe", "global"):
                    errors.append("agent_config.scout_region must be one of: europe, global")
            if "scout_serp_enabled" in ac and not isinstance(ac["scout_serp_enabled"], bool):
                errors.append("agent_config.scout_serp_enabled must be a boolean")
            if "scout_serp_daily_budget" in ac:
                v = ac["scout_serp_daily_budget"]
                if not isinstance(v, (int, float)) or v < 0:
                    errors.append("agent_config.scout_serp_daily_budget must be a non-negative number")
            if "scout_grounded_citations_enabled" in ac and not isinstance(ac["scout_grounded_citations_enabled"], bool):
                errors.append("agent_config.scout_grounded_citations_enabled must be a boolean")
            if "scout_fail_closed_on_empty_retrieval" in ac and not isinstance(ac["scout_fail_closed_on_empty_retrieval"], bool):
                errors.append("agent_config.scout_fail_closed_on_empty_retrieval must be a boolean")
            if "scout_retrieval_provider" in ac:
                v = ac["scout_retrieval_provider"]
                if not isinstance(v, str) or v not in ("tavily", "serpapi"):
                    errors.append("agent_config.scout_retrieval_provider must be one of: tavily, serpapi")
    fi = body.get("fund_identity")
    if fi is not None:
        if not isinstance(fi, dict):
            errors.append("fund_identity must be an object")
        else:
            for key in ("fund_name", "stage_focus", "geographic_focus", "canonical_website"):
                if key in fi and not isinstance(fi[key], str):
                    errors.append(f"fund_identity.{key} must be a string")
    pf = body.get("portfolio")
    if pf is not None:
        if not isinstance(pf, dict):
            errors.append("portfolio must be an object")
        else:
            if "auto_watchlist" in pf and not isinstance(pf["auto_watchlist"], bool):
                errors.append("portfolio.auto_watchlist must be a boolean")
            if "signal_scan_frequency" in pf and not isinstance(pf["signal_scan_frequency"], str):
                errors.append("portfolio.signal_scan_frequency must be a string")
            if "memo_verbosity" in pf and not isinstance(pf["memo_verbosity"], str):
                errors.append("portfolio.memo_verbosity must be a string")
    return errors


def _to_iso(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v) if v else None


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_after(left: Any, right: Any) -> bool:
    ldt = _parse_iso_datetime(left)
    rdt = _parse_iso_datetime(right)
    if ldt is None or rdt is None:
        return False
    if ldt.tzinfo is None and rdt.tzinfo is not None:
        ldt = ldt.replace(tzinfo=timezone.utc)
    if rdt.tzinfo is None and ldt.tzinfo is not None:
        rdt = rdt.replace(tzinfo=timezone.utc)
    return ldt > rdt


def _startup_has_human_ruling(raw: Dict[str, Any]) -> bool:
    hr = raw.get("human_resolution")
    return isinstance(hr, dict) and bool(hr.get("resolved_at") or hr.get("decision"))


def _default_queue_reason(raw: Dict[str, Any]) -> str:
    partner = raw.get("partner_info") if isinstance(raw.get("partner_info"), dict) else {}
    review = raw.get("review_info") if isinstance(raw.get("review_info"), dict) else None
    if _startup_has_human_ruling(raw):
        return "Human ruling recorded."
    if partner.get("human_review_required"):
        return "Human ruling required."
    if partner.get("recommendation"):
        return f"Partner recommends {str(partner.get('recommendation')).lower()}."
    if review:
        return "Reviewer output ready for partner judgement."
    return "New discovery awaiting review."


def _default_priority_reason(raw: Dict[str, Any]) -> str:
    scout = raw.get("scout_info") if isinstance(raw.get("scout_info"), dict) else {}
    review = raw.get("review_info") if isinstance(raw.get("review_info"), dict) else {}
    sector = (scout.get("sector") or "").split("/")[0].strip()
    score = review.get("overall_score") or review.get("aggregate_score")
    if not isinstance(score, (int, float)):
        nums = [
            review.get("market_score"),
            review.get("product_score"),
            review.get("technical_score"),
            review.get("execution_score"),
        ]
        vals = [float(v) for v in nums if isinstance(v, (int, float))]
        score = (sum(vals) / len(vals) * 10) if vals else None
    elif score <= 10:
        score = score * 10
    parts = [f"Priority {round(float(score))}" if isinstance(score, (int, float)) else "Priority pending"]
    reason = _default_queue_reason(raw).rstrip(".")
    if reason:
        parts.append(reason)
    if sector:
        parts.append(sector)
    return " · ".join(parts)


def _get_user_last_seen_at(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    try:
        row = (
            get_service_client()
            .table("user_state")
            .select("last_seen_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return (row.data or {}).get("last_seen_at")
    except Exception as e:
        logging.getLogger("api").debug("Could not load user_state last_seen_at: %s", e)
        return None


def _partner_recommendation_from_stored(
    partner_doc: Any,
    legacy_decision: Optional[str] = None,
) -> Optional[str]:
    """Resolve INVEST/PASS/MONITOR from partner JSON and/or legacy YES/NO/MAYBE."""
    pi = partner_doc if isinstance(partner_doc, dict) else {}
    rec = pi.get("recommendation") if isinstance(pi, dict) else None
    if rec:
        return rec
    ld = legacy_decision if legacy_decision is not None else pi.get("decision")
    return recommendation_from_legacy((ld or "").strip() or None, default_if_unknown=None)


def _partner_dict_for_frontend(partner: dict) -> dict:
    """Stable partner slice for app-front-end (preserves all existing keys)."""
    raw_rec = _partner_recommendation_from_stored(partner, partner.get("decision"))
    raw_conf = partner.get("confidence")
    if raw_conf is None and partner.get("conviction_level") is not None:
        raw_conf = (partner["conviction_level"] or 0) / 10.0
    return {
        "recommendation": raw_rec,
        "confidence": raw_conf,
        "decision_rationale": partner.get("decision_rationale") or partner.get("rationale"),
        "thesis": partner.get("thesis"),
        "why_this_matters": partner.get("why_this_matters"),
        "snapshot": partner.get("snapshot"),
        "market_insight": partner.get("market_insight"),
        "product_edge": partner.get("product_edge"),
        "traction_signals": partner.get("traction_signals"),
        "risks": partner.get("risks"),
        "next_action": partner.get("next_action"),
        "human_review_required": partner.get("human_review_required", False),
        "llm_fallback_reason": partner.get("llm_fallback_reason"),
        "prompt_version": partner.get("prompt_version"),
        "decision_drivers": partner.get("decision_drivers") or [],
    }


def _enrich_review_for_api_payload(review: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pipeline writes enriched review payloads via adapters and reviewer engine.
    Set SKIP_READ_ENRICH_SCORES=1 to skip redundant enrich_scores() on GET when rows
    already carry overall_score and at least one overall label/band field.
    """
    if os.getenv("SKIP_READ_ENRICH_SCORES", "").strip().lower() in ("1", "true", "yes"):
        if review.get("overall_score") is not None and (
            review.get("overall_label") is not None or review.get("overall_rubric_band") is not None
        ):
            return dict(review)
    return enrich_scores(review)


def _mirror_structured_scoring_aliases(review: Dict[str, Any]) -> None:
    """Ensure scoring / structured_scoring / score_breakdown reference the same object when any is set."""
    sc = review.get("structured_scoring") or review.get("scoring") or review.get("score_breakdown")
    if sc is None:
        return
    review["structured_scoring"] = sc
    review["scoring"] = sc
    review["score_breakdown"] = sc


def _build_scoring_presentation(
    structured_scoring: Dict[str, Any] | None,
    *,
    scout: Dict[str, Any] | None = None,
    review: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """Build the investor-facing presentation DTO from raw scoring data."""
    if not structured_scoring or not isinstance(structured_scoring, dict):
        return None
    if "overall_score" not in structured_scoring:
        return None
    try:
        ctx: Dict[str, Any] = {}
        if scout:
            ctx["scout"] = scout
        if review:
            ctx["reviewer_output"] = review
        return serialize_scoring_presentation(
            structured_scoring,
            startup_context=ctx or None,
        )
    except Exception:
        return None


def _backend_to_frontend(raw: dict, *, last_seen_at: Optional[str] = None) -> dict:
    """Transform backend startup dict to app-front-end Startup shape."""
    sid = raw.get("startup_id", "")
    scout = raw.get("scout_info") or {}
    review = raw.get("review_info")
    partner = raw.get("partner_info")

    timestamps = {}
    if scout.get("discovered_at"):
        timestamps["discovered_at"] = _to_iso(scout["discovered_at"])
    if review and review.get("reviewed_at"):
        timestamps["reviewed_at"] = _to_iso(review["reviewed_at"])
    if partner and partner.get("partnered_at"):
        timestamps["partnered_at"] = _to_iso(partner["partnered_at"])
    if raw.get("unresolved_at"):
        timestamps["unresolved_at"] = _to_iso(raw.get("unresolved_at"))
    first_seen_at = _to_iso(raw.get("first_seen_at") or raw.get("created_at") or scout.get("discovered_at"))
    timestamps["first_seen_at"] = first_seen_at
    timestamps["last_seen_by_user_at"] = _to_iso(raw.get("last_seen_by_user_at"))
    timestamps["acknowledged_at"] = _to_iso(raw.get("acknowledged_at"))

    out = {
        "id": sid,
        "scout": {
            "id": sid,
            "scout_type": scout.get("scout_type", "market_driven"),
            "name": scout.get("name", ""),
            "one_line": scout.get("one_line", ""),
            "sector": scout.get("sector", ""),
            "problem": scout.get("problem"),
            "solution": scout.get("solution"),
            "target_users": scout.get("target_users"),
            "why_now": scout.get("why_now", ""),
            "confidence": scout.get("confidence_score", 0.5),
            "primary_thesis": scout.get("primary_thesis"),
            "key_assumptions": scout.get("key_assumptions") or None,
            "biggest_unknown": scout.get("biggest_unknown"),
            "funding_stage": scout.get("funding_stage"),
            "est_tam": scout.get("est_tam"),
            "references": scout.get("references") or [],
            "source_evidence": scout.get("source_evidence") or [],
            "origin_type": scout.get("origin_type"),
            "lookup_input_type": scout.get("lookup_input_type"),
            "lookup_query": scout.get("lookup_query"),
            "lookup_website": scout.get("lookup_website"),
            "lookup_id": scout.get("lookup_id"),
            "field_provenance": scout.get("field_provenance")
            if isinstance(scout.get("field_provenance"), dict)
            else None,
        },
        "timestamps": timestamps,
        "human_resolution": raw.get("human_resolution"),
        "conviction_state": raw.get("conviction_state"),
        "financials": raw.get("financials") if isinstance(raw.get("financials"), dict) else None,
        "agent_trace": raw.get("agent_trace"),
        "unresolved_at": _to_iso(raw.get("unresolved_at")),
        "is_new_to_user": raw.get("acknowledged_at") is None and not _startup_has_human_ruling(raw),
        "changed_since_last_visit": _is_after(raw.get("updated_at"), last_seen_at),
        "queue_reason": raw.get("queue_reason") or _default_queue_reason(raw),
        "priority_reason": raw.get("priority_reason") or _default_priority_reason(raw),
    }

    if review:
        review_enriched = _enrich_review_for_api_payload(review)
        _raw_aethria = review_enriched.get("aethria_view")
        _polished_aethria = (
            polish_aethria_view_for_api(
                _raw_aethria, review_enriched, str(scout.get("name") or "")
            )
            if _raw_aethria is not None
            else None
        )
        _aethria_for_fe = (
            _polished_aethria if _polished_aethria is not None else _raw_aethria
        )
        out["review"] = {
            "market_score": review_enriched.get("market_score"),
            "product_score": review_enriched.get("product_score"),
            "technical_score": review_enriched.get("technical_score"),
            "execution_score": review_enriched.get("execution_score"),
            "defensibility_score": review_enriched.get("defensibility_score"),
            "market_score_label": review_enriched.get("market_score_label"),
            "product_score_label": review_enriched.get("product_score_label"),
            "technical_score_label": review_enriched.get("technical_score_label"),
            "execution_score_label": review_enriched.get("execution_score_label"),
            "defensibility_score_label": review_enriched.get("defensibility_score_label"),
            "overall_score": review_enriched.get("overall_score"),
            "overall_label": review_enriched.get("overall_label"),
            "overall_rubric_band": review_enriched.get("overall_rubric_band"),
            "market_rubric_band": review_enriched.get("market_rubric_band"),
            "product_rubric_band": review_enriched.get("product_rubric_band"),
            "technical_rubric_band": review_enriched.get("technical_rubric_band"),
            "execution_rubric_band": review_enriched.get("execution_rubric_band"),
            "defensibility_rubric_band": review_enriched.get("defensibility_rubric_band"),
            "overall_summary": review_enriched.get("overall_summary"),
            "key_risks": review_enriched.get("key_risks") or [],
            "verdict": review_enriched.get("verdict"),
            "derived_verdict": review_enriched.get("derived_verdict"),
            "score_reasoning": review_enriched.get("score_reasoning") or None,
            "score_source": review_enriched.get("score_source"),
            "improvement_to_9": review_enriched.get("improvement_to_9") or [],
            "market_reasoning": review_enriched.get("market_reasoning") or [],
            "market_weaknesses": review_enriched.get("market_weaknesses") or [],
            "market_confidence": review_enriched.get("market_confidence"),
            "product_reasoning": review_enriched.get("product_reasoning") or [],
            "product_weaknesses": review_enriched.get("product_weaknesses") or [],
            "product_confidence": review_enriched.get("product_confidence"),
            "technical_reasoning": review_enriched.get("technical_reasoning") or [],
            "technical_weaknesses": review_enriched.get("technical_weaknesses") or [],
            "technical_confidence": review_enriched.get("technical_confidence"),
            "execution_reasoning": review_enriched.get("execution_reasoning") or [],
            "execution_weaknesses": review_enriched.get("execution_weaknesses") or [],
            "execution_confidence": review_enriched.get("execution_confidence"),
            "defensibility_reasoning": review_enriched.get("defensibility_reasoning") or [],
            "defensibility_weaknesses": review_enriched.get("defensibility_weaknesses") or [],
            "defensibility_confidence": review_enriched.get("defensibility_confidence"),
            "diligence_red_flags": review_enriched.get("diligence_red_flags") or [],
            "assumption_feedback": review_enriched.get("assumption_feedback") or [],
            "team_analysis": review_enriched.get("team_analysis") or None,
            "competition_analysis": review_enriched.get("competition_analysis") or None,
            "business_model_analysis": review_enriched.get("business_model_analysis") or None,
            "investment_thesis": review_enriched.get("investment_thesis") or None,
            "risk_mitigation": review_enriched.get("risk_mitigation") or None,
            "consensus_verdict": review_enriched.get("consensus_verdict"),
            "reviewer_disagreement": review_enriched.get("reviewer_disagreement"),
            "score_variance": review_enriched.get("score_variance"),
            "fund_thesis_version_id": review_enriched.get("fund_thesis_version_id"),
            "thesis_alignment_score": review_enriched.get("thesis_alignment_score"),
            "thesis_matches_fund": review_enriched.get("thesis_matches_fund"),
            "thesis_fit_points": review_enriched.get("thesis_fit_points") or None,
            "thesis_deviation_points": review_enriched.get("thesis_deviation_points") or None,
            "thesis_alignment_confidence": review_enriched.get("thesis_alignment_confidence"),
            "fund_thesis_alignment_score": review_enriched.get("fund_thesis_alignment_score"),
            "confidence_adjusted_score": review_enriched.get("confidence_adjusted_score"),
            "structured_scoring": review_enriched.get("structured_scoring"),
            "scoring_presentation": _build_scoring_presentation(
                review_enriched.get("structured_scoring"),
                scout=scout,
                review=review_enriched,
            ),
            "structured_signals": review_enriched.get("structured_signals"),
            "resolution_notes": review_enriched.get("resolution_notes"),
            "disagreement_summary": review_enriched.get("disagreement_summary"),
            "aethria_view": _aethria_for_fe,
            "reviews": review_enriched.get("reviews") or None,
        }
        _mirror_structured_scoring_aliases(out["review"])
    else:
        out["review"] = None

    if partner:
        out["partner"] = _partner_dict_for_frontend(partner)
    else:
        out["partner"] = None

    return out


def _memo_partial_payload(startup: Startup) -> Dict[str, Any]:
    """Scout/review/partner slices for progressive memo UX (frontend Startup shape)."""
    raw = startup.model_dump(mode="json")
    fe = _backend_to_frontend(raw)
    return {
        "scout": fe["scout"],
        "review": fe.get("review"),
        "partner": fe.get("partner"),
        "financials": fe.get("financials"),
        "agent_trace": fe.get("agent_trace"),
    }


def _list_projection_to_frontend(
    row: Dict[str, Any],
    *,
    last_seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Map DB list-projection row to frontend Startup-like payload (no memo, no heavy scout blobs)."""
    sid = str(row.get("startup_id") or "")
    conf = row.get("list_confidence")
    try:
        conf_f = float(conf) if conf is not None else 0.5
    except (TypeError, ValueError):
        conf_f = 0.5
    timestamps: Dict[str, Any] = {
        "discovered_at": _to_iso(row.get("created_at")),
        "reviewed_at": _to_iso(row.get("list_reviewed_at")) if row.get("list_reviewed_at") else None,
        "partnered_at": _to_iso(row.get("list_partnered_at")) if row.get("list_partnered_at") else None,
        "unresolved_at": _to_iso(row.get("unresolved_at")) if row.get("unresolved_at") else None,
        "first_seen_at": _to_iso(row.get("first_seen_at") or row.get("created_at")),
        "last_seen_by_user_at": _to_iso(row.get("last_seen_by_user_at")),
        "acknowledged_at": _to_iso(row.get("acknowledged_at")),
    }
    has_human_ruling = isinstance(row.get("human_resolution"), dict) and bool(
        row.get("human_resolution", {}).get("resolved_at") or row.get("human_resolution", {}).get("decision")
    )
    out: Dict[str, Any] = {
        "id": sid,
        "scout": {
            "id": sid,
            "scout_type": row.get("list_scout_type") or "market_driven",
            "name": row.get("display_name") or "",
            "one_line": row.get("list_one_line") or "",
            "sector": row.get("list_sector") or "",
            "why_now": "",
            "confidence": conf_f,
            "origin_type": row.get("list_origin_type"),
            "lookup_id": row.get("list_lookup_id"),
            "lookup_query": row.get("list_lookup_query"),
            "lookup_website": row.get("list_lookup_website"),
            "source_evidence": [],
        },
        "timestamps": timestamps,
        "human_resolution": row.get("human_resolution"),
        "conviction_state": row.get("conviction_state"),
        "unresolved_at": _to_iso(row.get("unresolved_at")) if row.get("unresolved_at") else None,
        "is_new_to_user": row.get("acknowledged_at") is None and not has_human_ruling,
        "changed_since_last_visit": _is_after(row.get("updated_at"), last_seen_at),
        "queue_reason": row.get("queue_reason") or "",
        "priority_reason": row.get("priority_reason") or "",
    }
    if row.get("list_verdict") or row.get("list_score") is not None or row.get("short_summary"):
        score = row.get("list_score")
        try:
            agg = float(score) if score is not None else None
        except (TypeError, ValueError):
            agg = None
        out["review"] = {
            "verdict": row.get("list_verdict"),
            "consensus_verdict": row.get("list_consensus_verdict") or row.get("list_verdict"),
            "overall_summary": row.get("short_summary") or "",
            "reviewer_disagreement": bool(row.get("list_reviewer_disagreement")),
            "aggregate_score": agg,
            "overall_score": agg,
            "overall_label": score_to_label(agg) if isinstance(agg, (int, float)) else None,
            "overall_rubric_band": rubric_band_for_numeric(float(agg))
            if isinstance(agg, (int, float))
            else None,
        }
    else:
        out["review"] = None
    # partner_info JSON has 'recommendation' (new schema); partner_decision column has YES/NO/MAYBE (legacy)
    pi = row.get("partner_info") or {}
    raw_rec = _partner_recommendation_from_stored(pi, row.get("partner_decision"))
    if raw_rec:
        out["partner"] = {
            "recommendation": raw_rec,
            "human_review_required": bool(row.get("partner_human_review_required") or (
                pi.get("human_review_required", False) if isinstance(pi, dict) else False
            )),
        }
    else:
        out["partner"] = None
    raw_for_reason = {
        "startup_id": sid,
        "scout_info": out["scout"],
        "review_info": out.get("review"),
        "partner_info": out.get("partner"),
        "human_resolution": row.get("human_resolution"),
    }
    if not out["queue_reason"]:
        out["queue_reason"] = _default_queue_reason(raw_for_reason)
    if not out["priority_reason"]:
        out["priority_reason"] = _default_priority_reason(raw_for_reason)
    return out


def _thin_list_from_full_frontend(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback when list projection columns are unavailable: strip heavy fields from full map."""
    scout = dict(obj.get("scout") or {})
    for k in (
        "problem",
        "solution",
        "target_users",
        "references",
        "primary_thesis",
        "key_assumptions",
        "biggest_unknown",
        "funding_stage",
        "est_tam",
        "lookup_input_type",
        "prompt_version",
    ):
        scout.pop(k, None)
    rev = obj.get("review") or {}
    thin_rev: Optional[Dict[str, Any]] = None
    if rev:
        overall = rev.get("overall_score")
        if not isinstance(overall, (int, float)):
            overall = compute_overall_score(rev)
        thin_rev = {
            "verdict": rev.get("verdict"),
            "consensus_verdict": rev.get("consensus_verdict") or rev.get("verdict"),
            "overall_summary": (rev.get("overall_summary") or "")[:400],
            "reviewer_disagreement": rev.get("reviewer_disagreement"),
            "aggregate_score": overall,
            "overall_score": overall,
            "overall_label": score_to_label(float(overall)) if isinstance(overall, (int, float)) else None,
            "overall_rubric_band": rev.get("overall_rubric_band")
            if rev.get("overall_rubric_band") is not None
            else (
                rubric_band_for_numeric(float(overall)) if isinstance(overall, (int, float)) else None
            ),
        }
    part = obj.get("partner") or {}
    thin_part: Optional[Dict[str, Any]] = None
    if part:
        thin_part = {
            "recommendation": part.get("recommendation"),
            "human_review_required": part.get("human_review_required", False),
        }
    return {**obj, "scout": scout, "review": thin_rev, "partner": thin_part}


def _aggregate_activity_totals(
    activity_rows: List[Dict[str, Any]],
    *,
    human_reviewed: int = 0,
    open_in_progress: int = 0,
) -> Dict[str, int]:
    totals = {
        "found": 0,
        "reviewed": 0,
        "decided": 0,
        "agent_decided": 0,
        "human_reviewed": max(0, int(human_reviewed or 0)),
        "open_in_progress": max(0, int(open_in_progress or 0)),
        "escalations": 0,
    }
    for r in activity_rows:
        totals["found"] += int(r.get("startups_found", 0) or 0)
        totals["reviewed"] += int(r.get("reviewed_count", 0) or 0)
        totals["agent_decided"] += int(r.get("decisions_made", 0) or 0)
        totals["escalations"] += int(r.get("escalations_count", 0) or 0)
    totals["decided"] = totals["agent_decided"]
    return totals


def _get_storage(request: Request):
    """Return Supabase startups storage for the authenticated user.
    Uses service-role client and Clerk-derived user_id; we never send Clerk JWT to Supabase.
    """
    return SupabaseStartupsStorage(
        get_service_client(),
        request.state.user_id,
    )


@app.get("/api/startups")
def get_startups(
    request: Request,
    limit: int = DEFAULT_STARTUPS_LIST_LIMIT,
    offset: int = 0,
):
    limit = max(1, min(int(limit or DEFAULT_STARTUPS_LIST_LIMIT), MAX_STARTUPS_LIST_LIMIT))
    offset = max(0, int(offset or 0))
    storage = _get_storage(request)
    last_seen_at = _get_user_last_seen_at(getattr(request.state, "user_id", None))
    if isinstance(storage, SupabaseStartupsStorage):
        rows = storage.get_list_projection_rows(limit=limit, offset=offset)
        if rows is not None:
            return [_list_projection_to_frontend(r, last_seen_at=last_seen_at) for r in rows]
        raw_list, _next_offset = storage.get_startups_paginated(limit=limit, offset=offset)
        full = [_backend_to_frontend(r, last_seen_at=last_seen_at) for r in raw_list]
        return [_thin_list_from_full_frontend(x) for x in full]
    raw_list = storage.get_all()
    full = [_backend_to_frontend(r, last_seen_at=last_seen_at) for r in raw_list]
    return [_thin_list_from_full_frontend(x) for x in full]


@app.get("/api/startups/lookup-status")
async def lookup_job_status(request: Request, lookup_id: str = ""):
    """
    Poll after POST /api/startups/lookup: if the worker recorded a failure, returns failed=true and message.
    """
    uid = request.state.user_id
    raw = (lookup_id or "").strip()
    if not raw or not _LOOKUP_ID_RE.match(raw):
        raise HTTPException(
            status_code=422,
            detail="lookup_id query parameter must be 8-128 characters [a-zA-Z0-9_-]",
        )
    if os.getenv("USE_SUPABASE_STORAGE", "").lower() not in ("1", "true", "yes"):
        return {"lookup_id": raw, "failed": False}
    row = list_get_by_id("lookup_job_outcomes", raw, user_id=uid)
    if not row or row.get("status") != "failed":
        return {"lookup_id": raw, "failed": False}
    return {
        "lookup_id": raw,
        "failed": True,
        "message": str(row.get("message") or "Lookup failed."),
    }


@app.get("/api/startups/{startup_id}")
def get_startup_detail(request: Request, startup_id: str):
    """Full scout/review/partner JSON for one startup (on-demand; not used for grid polling)."""
    validate_route_id(startup_id, field_name="startup_id")
    storage = _get_storage(request)
    raw = storage.get_by_id(startup_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Startup not found")
    return _backend_to_frontend(raw, last_seen_at=_get_user_last_seen_at(getattr(request.state, "user_id", None)))


@app.post("/api/startups/{startup_id}/acknowledge")
async def acknowledge_startup(request: Request, startup_id: str):
    """Mark a startup as seen by the current user when they open the memo."""
    validate_route_id(startup_id, field_name="startup_id")
    storage = _get_storage(request)
    existing = storage.get_by_id(startup_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Startup not found")
    seen_at = _now_iso()
    ok = storage.update_startup_partial(
        startup_id,
        {
            "acknowledged_at": seen_at,
            "last_seen_by_user_at": seen_at,
        },
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Startup not found")
    updated = storage.get_by_id(startup_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Startup not found")
    return _backend_to_frontend(
        updated,
        last_seen_at=_get_user_last_seen_at(getattr(request.state, "user_id", None)),
    )


@app.get("/api/startups/{startup_id}/memo")
def get_startup_memo(request: Request, startup_id: str):
    """
    Memo readiness + optional persisted markdown (Supabase).
    Never blocks on memo generation.
    Response: { status, memo, partial?, pipeline_run_id, error }.
    """
    from pipeline_state import get_pipeline_state_row

    validate_route_id(startup_id, field_name="startup_id")
    storage = _get_storage(request)
    uid = request.state.user_id
    if isinstance(storage, SupabaseStartupsStorage):
        startup = storage.get_startup_for_memo(startup_id)
    else:
        startup = storage.get_startup(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")

    if isinstance(storage, SupabaseStartupsStorage):
        row = get_pipeline_state_row(storage._client, user_id=uid, startup_id=startup_id)
        state_status = row.get("status") if row else None
        pr_from_row = row.get("pipeline_run_id") if row else None
        err_from_row = row.get("error") if row else None

        md = (startup.investment_memo_markdown or "").strip()
        pr_str = str(pr_from_row) if pr_from_row else None

        if state_status == "failed":
            partial = _memo_partial_payload(startup)
            return {
                "status": "failed",
                "memo": None,
                "partial": partial,
                "pipeline_run_id": pr_str,
                "error": err_from_row,
            }

        if md:
            return {
                "status": "ready",
                "memo": md,
                "partial": None,
                "pipeline_run_id": pr_str,
                "error": None,
            }

        # Partner decision exists or pipeline explicitly marked ready → no markdown needed
        if state_status == "ready" or startup.partner_info is not None:
            partial = _memo_partial_payload(startup)
            return {
                "status": "ready",
                "memo": None,
                "partial": partial,
                "pipeline_run_id": pr_str,
                "error": None,
            }

        return {
            "status": "generating",
            "memo": None,
            "partial": _memo_partial_payload(startup) if startup.scout_info else None,
            "pipeline_run_id": pr_str,
            "error": None,
        }

    memo = MemoGenerator().generate_memo(
        startup,
        for_display=True,
        tenant_user_id=uid,
    )
    return {
        "status": "ready",
        "memo": memo,
        "partial": None,
        "pipeline_run_id": None,
        "error": None,
    }


@app.get("/health")
def health():
    """Lightweight health check (public; no auth). Pending escalations require auth via /api/settings."""
    return {"status": "ok"}


def _admin_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin authorization token")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing admin authorization token")
    return token


def _require_admin_claims(request: Request) -> Dict[str, Any]:
    try:
        return verify_admin_token(_admin_bearer_token(request))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _admin_login_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _admin_login_failures_for_key(key: str, *, now: float) -> List[float]:
    cutoff = now - _ADMIN_LOGIN_WINDOW_SECONDS
    failures = [ts for ts in _admin_login_attempts.get(key, []) if ts >= cutoff]
    _admin_login_attempts[key] = failures
    return failures


def _record_admin_login_failure(request: Request) -> None:
    now = datetime.now(timezone.utc).timestamp()
    key = _admin_login_key(request)
    failures = _admin_login_failures_for_key(key, now=now)
    failures.append(now)
    _admin_login_attempts[key] = failures


def _admin_login_is_limited(request: Request) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    key = _admin_login_key(request)
    return len(_admin_login_failures_for_key(key, now=now)) >= _ADMIN_LOGIN_MAX_FAILURES


def _clear_admin_login_failures(request: Request) -> None:
    _admin_login_attempts.pop(_admin_login_key(request), None)


@app.post("/api/admin/login")
def admin_login(request: Request, body: dict):
    """Exchange the configured master admin secret for a short-lived admin token."""
    if not _admin_dashboard_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    limited = _enforce_rate_limits(f"admin_login:ip:{_client_host(request)}", [_ADMIN_LOGIN_POLICY])
    if limited is not None:
        record_admin_audit_event(
            event="admin_login",
            success=False,
            client_host=_admin_login_key(request),
            detail=security_event_detail(reason="rate_limited"),
        )
        return limited
    if _admin_login_is_limited(request):
        record_admin_audit_event(
            event="admin_login",
            success=False,
            client_host=_admin_login_key(request),
            detail=security_event_detail(reason="failed_secret_rate_limited"),
        )
        raise HTTPException(status_code=429, detail="Too many failed admin login attempts")
    secret = str(body.get("secret") or "")
    if not validate_admin_secret(secret):
        _record_admin_login_failure(request)
        record_admin_audit_event(
            event="admin_login",
            success=False,
            client_host=_admin_login_key(request),
            detail=security_event_detail(reason="invalid_secret"),
        )
        raise HTTPException(status_code=401, detail="Invalid admin secret")
    _clear_admin_login_failures(request)
    record_admin_audit_event(
        event="admin_login",
        success=True,
        client_host=_admin_login_key(request),
        detail={},
    )
    return {
        "token": issue_admin_token(),
        "token_type": "bearer",
        "expires_in_seconds": admin_token_ttl_seconds(),
    }


@app.get("/api/admin/overview")
def admin_overview(request: Request):
    """Cross-tenant admin overview. Guarded by the separate admin token."""
    if not _admin_dashboard_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    claims = _require_admin_claims(request)
    rate_key = f"admin_overview:token:{claims.get('jti') or _client_host(request)}"
    limited = _enforce_rate_limits(rate_key, [_ADMIN_OVERVIEW_POLICY])
    if limited is not None:
        record_admin_audit_event(
            event="admin_overview",
            success=False,
            client_host=_admin_login_key(request),
            detail=security_event_detail(reason="rate_limited", jti=claims.get("jti")),
        )
        return limited
    record_admin_audit_event(
        event="admin_overview",
        success=True,
        client_host=_admin_login_key(request),
        detail=security_event_detail(jti=claims.get("jti")),
    )
    loop_status_by_user = {
        user_id: task is not None and not task.done()
        for user_id, task in _per_user_loops.items()
    }
    return build_admin_overview(loop_status_by_user=loop_status_by_user)


@app.get("/api/me")
def get_me(request: Request):
    """Return the current user's id (Clerk JWT sub). Background agents receive user_id only via the job queue."""
    return {"user_id": request.state.user_id}


@app.get("/api/settings")
def get_settings(request: Request):
    """Return current user's settings (control plane)."""
    user_id = request.state.user_id
    settings = load_settings(user_id)
    # Surface Meta-Agent configuration derived from environment variables
    # so the front-end can display current meta-control knobs.
    meta_agent = get_meta_agent_settings()
    meta_agent["model"] = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
    settings["meta_agent"] = meta_agent

    # Embed latest system health snapshot inline so the front-end can avoid extra calls.
    storage = _get_storage(request)
    settings["system_health"] = _get_system_health(storage, user_id=user_id)
    return settings


@app.patch("/api/settings")
async def patch_settings(request: Request, body: dict):
    """Update current user's settings. Validates server-side; returns 422 on validation errors."""
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    errors = _validate_settings(body)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Validation failed", "errors": errors})
    current = load_settings(user_id)
    for section in ("fund_config", "user_preferences", "fund_memory", "fund_identity", "cost_budget", "agent_config", "portfolio"):
        if section in body and isinstance(body[section], dict):
            if section not in current:
                current[section] = {}
            if section == "fund_config":
                next_config = dict(body[section])
                prev = current.get("fund_config") if isinstance(current.get("fund_config"), dict) else {}
                prev_version = int(prev.get("version") or 1) if isinstance(prev, dict) else 1
                content_changed = fund_config_content_changed(prev, next_config)
                if content_changed:
                    next_version = prev_version + 1
                    next_config["version"] = next_version
                    next_config["versionLabel"] = f"Fund Thesis v{next_version}"
                    next_config["lastSavedAt"] = _now_iso()
                else:
                    next_config["version"] = prev_version
                    next_config["versionLabel"] = str(
                        prev.get("versionLabel") or f"Fund Thesis v{prev_version}"
                    )
                    next_config["lastSavedAt"] = prev.get("lastSavedAt")
                current[section] = next_config
            elif section in ("user_preferences", "fund_memory"):
                current[section] = body[section]
            else:
                for k, v in body[section].items():
                    current[section][k] = v
    _save_settings(current, user_id)

    if isinstance(body.get("fund_config"), dict):
        fc = current.get("fund_config") if isinstance(current.get("fund_config"), dict) else {}
        if fund_config_raw_text(fc).strip():
            try:
                api_key = os.getenv("OPENAI_API_KEY", "").strip()
                sync_out = sync_fund_config_to_active_thesis(
                    get_service_client(),
                    user_id=user_id,
                    fund_config=fc,
                    api_key=api_key,
                )
                if sync_out.get("skipped"):
                    _logger_agents.debug(
                        "[%s] fund_config thesis sync skipped (unchanged)",
                        user_id[:12],
                    )
                else:
                    _logger_agents.info(
                        "[%s] Synced fund_config to fund thesis v%s",
                        user_id[:12],
                        sync_out.get("version_number"),
                    )
            except Exception as e:
                _logger_agents.warning("[%s] fund_config thesis sync failed: %s", user_id[:12], e)

    # If any agents are enabled after the patch, ensure the persistent background loop is running.
    # This covers the case where the user toggles agents in the UI and clicks "Save".
    ac = current.get("agent_config") or {}
    if ac.get("scouts_enabled") or ac.get("reviewers_enabled") or ac.get("partners_enabled"):
        await _ensure_user_loop(user_id)
    else:
        # If all agents were just turned off, make sure the loop is stopped.
        await _stop_user_loop(user_id)

    # Meta-Agent settings are derived from environment; PATCH does not
    # persist or validate them, but we still include the live view.
    meta_agent = get_meta_agent_settings()
    meta_agent["model"] = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
    current["meta_agent"] = meta_agent
    return current


@app.post("/api/settings/policy/preview")
def preview_settings_policy(request: Request, body: dict | None = None):
    """Compile the current or supplied fund_config draft without persisting it."""
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    payload = body if isinstance(body, dict) else {}
    if isinstance(payload.get("fund_config"), dict):
        fund_config = payload["fund_config"]
    else:
        settings = load_settings(user_id, use_cache=False)
        fund_config = settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {}
    policy = compile_policy_from_fund_config(fund_config)
    return {"policy": policy, "warnings": policy.get("warnings", [])}


@app.post("/api/settings/policy/publish")
def publish_settings_policy(request: Request, body: dict | None = None):
    """Publish the current or supplied fund_config draft as an immutable scoring policy version."""
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    payload = body if isinstance(body, dict) else {}
    fund_config = payload.get("fund_config") if isinstance(payload.get("fund_config"), dict) else None
    try:
        policy = publish_policy(user_id, fund_config=fund_config)
    except PolicyValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy validation failed", "errors": exc.errors},
        ) from exc
    return {"policy": policy}


@app.get("/api/policy/active")
def get_policy_active(request: Request):
    """Return resources/config/active.json (version pointers; authenticated)."""
    return policy_resolver.read_active_json_from_disk()


@app.post("/api/policy/reload")
def post_policy_reload(request: Request):
    """
    Reload active.json and all versioned policy JSON into the process cache (no restart).
    """
    policy_resolver.reload()
    return {
        "ok": True,
        "active": policy_resolver.get_active_meta_snapshot(),
    }


@app.get("/api/meta/reports")
def get_meta_reports(request: Request):
    """
    Return the last 10 Meta-Agent cycle reports for the authenticated user (Supabase meta_reports).
    """
    uid = request.state.user_id
    reports = list_get_all("meta_reports", user_id=uid)
    if not isinstance(reports, list):
        return []
    reports = sorted(
        reports,
        key=lambda x: (x.get("ran_at") or "", int(x.get("cycle_number") or 0)),
        reverse=True,
    )
    return reports[:10]


@app.get("/api/meta/insights")
def get_meta_insights(request: Request):
    """
    Latest meta cycle: what changed (mutations, weights, calibration) and why (no_action_reasons).
    """
    uid = request.state.user_id
    reports = list_get_all("meta_reports", user_id=uid)
    if not isinstance(reports, list) or not reports:
        return {
            "latest": None,
            "what_changed": None,
            "why": [],
        }
    latest = max(
        reports,
        key=lambda x: (x.get("ran_at") or "", int(x.get("cycle_number") or 0)),
    )
    return {
        "latest": {
            "cycle_number": latest.get("cycle_number"),
            "ran_at": latest.get("ran_at"),
            "next_cycle_at": latest.get("next_cycle_at"),
        },
        "what_changed": {
            "mutations_applied": latest.get("mutations_applied") or [],
            "prompt_proposals": latest.get("prompt_proposals")
            or latest.get("mutations_applied")
            or [],
            "weight_updates": latest.get("weight_updates") or [],
            "calibration_changes": latest.get("calibration_changes") or [],
        },
        "why": latest.get("no_action_reasons") or [],
        "signal_summary": latest.get("signal_summary"),
    }


@app.get("/api/meta/prompt-library")
def get_meta_prompt_library(request: Request):
    """
    Return the full prompt library used by the Meta-Agent (Supabase meta_prompt_library).
    """
    lib = load_prompt_library(request.state.user_id)
    return lib if isinstance(lib, dict) else {}


def _summarize_library_entry(
    library_key: str,
    entry: Dict[str, Any],
    *,
    include_prompt_body: bool,
) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {"library_key": library_key, "error": "invalid_entry"}
    prompt = entry.get("prompt")
    out: Dict[str, Any] = {
        "library_key": library_key,
        "created_at": entry.get("created_at"),
        "cycle_number": entry.get("cycle_number"),
        "reasoning": (str(entry.get("reasoning") or ""))[:500],
        "promotion_status": entry.get("promotion_status"),
        "previous_hash": entry.get("previous_hash"),
        "prompt_char_count": len(str(prompt)) if prompt else 0,
    }
    if include_prompt_body and prompt is not None:
        out["prompt"] = str(prompt)
    return out


@app.get("/api/meta/prompt-state")
def get_meta_prompt_state(
    request: Request,
    include_prompt: Optional[str] = Query(
        default=None,
        description="If set, include full prompt text only for this library_key",
    ),
):
    """
    Active and pending meta prompt proposals (metadata only; full text for one key via include_prompt).
    """
    uid = request.state.user_id
    library = load_prompt_library(uid)
    active = load_prompt_active(uid)
    if not isinstance(library, dict):
        library = {}

    active_detail: Dict[str, Any] = {}
    for agent, lib_key in sorted(active.items()):
        ent = library.get(lib_key)
        if isinstance(ent, dict):
            active_detail[agent] = _summarize_library_entry(
                lib_key,
                ent,
                include_prompt_body=bool(include_prompt and include_prompt == lib_key),
            )
        else:
            active_detail[agent] = {
                "library_key": lib_key,
                "warning": "missing_from_library",
            }

    active_keys = set(active.values())
    pending: List[Dict[str, Any]] = []
    for key, ent in library.items():
        if not isinstance(key, str) or ":" not in key:
            continue
        agent_tgt, _ = key.split(":", 1)
        if agent_tgt not in VALID_PROMOTE_AGENT_TARGETS:
            continue
        if key in active_keys:
            continue
        if not isinstance(ent, dict):
            continue
        st = ent.get("promotion_status")
        if st == "superseded":
            continue
        if st not in (None, "pending"):
            continue
        pending.append(
            _summarize_library_entry(
                key,
                ent,
                include_prompt_body=bool(include_prompt and include_prompt == key),
            )
        )
    pending.sort(key=lambda x: (x.get("created_at") or "", x.get("library_key") or ""), reverse=True)

    return {
        "active": active,
        "active_detail": active_detail,
        "pending": pending[:80],
        "restart_note": "Promoted prompts apply after workers restart unless META_AGENT_PROMPT_AUTO_APPLY ran in-process.",
    }


@app.post("/api/meta/prompts/promote")
async def post_meta_prompt_promote(request: Request):
    """Promote a pending library_key to the active prompt for an agent."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    library_key = str(body.get("library_key") or "").strip()
    if not agent_target or not library_key:
        raise HTTPException(status_code=400, detail="agent_target and library_key required")
    if agent_target not in VALID_PROMOTE_AGENT_TARGETS:
        raise HTTPException(status_code=400, detail="invalid agent_target")
    if not library_key.startswith(f"{agent_target}:"):
        raise HTTPException(status_code=400, detail="library_key does not match agent_target")

    library = load_prompt_library(uid)
    if not isinstance(library, dict) or library_key not in library:
        raise HTTPException(status_code=404, detail="library_key not found")
    ent = library[library_key]
    if not isinstance(ent, dict) or not str(ent.get("prompt") or "").strip():
        raise HTTPException(status_code=400, detail="library entry has no prompt")

    if agent_target in REVIEWER_EVAL_AGENT_TARGETS and os.getenv(
        "META_PROMPT_REQUIRE_EVAL_PASS", ""
    ).lower() in ("1", "true", "yes"):
        rec = get_last_eval_record(uid, library_key)
        if not rec or not rec.get("passed"):
            raise HTTPException(
                status_code=400,
                detail="Evaluation required: POST /api/meta/prompts/evaluate must pass for this library_key",
            )
        try:
            ttl_h = int(os.getenv("META_PROMPT_EVAL_PASS_TTL_HOURS", "24"))
        except ValueError:
            ttl_h = 24
        if not eval_record_fresh(rec, ttl_h):
            raise HTTPException(
                status_code=400,
                detail="Evaluation stale; run POST /api/meta/prompts/evaluate again",
            )

    active = load_prompt_active(uid)
    prev_key = active.get(agent_target)
    if prev_key and prev_key in library and isinstance(library[prev_key], dict):
        library[prev_key] = dict(library[prev_key])
        library[prev_key]["promotion_status"] = "superseded"

    library[library_key] = dict(ent)
    library[library_key]["promotion_status"] = "promoted"
    active = dict(active)
    active[agent_target] = library_key

    save_prompt_library(uid, library)
    save_prompt_active(uid, active)

    try:
        from supabase_doc_store import list_append_only

        list_append_only(
            "meta_mutation_log",
            {
                "type": "prompt_promoted",
                "agent_target": agent_target,
                "library_key": library_key,
                "previous_library_key": prev_key,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
            user_id=uid,
        )
    except Exception:
        pass

    return {"ok": True, "active": active, "promoted": library_key}


@app.post("/api/meta/prompts/reset")
async def post_meta_prompt_reset(request: Request):
    """Remove active prompt for an agent (revert to codebase default on next load)."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    if not agent_target or agent_target not in VALID_PROMOTE_AGENT_TARGETS:
        raise HTTPException(status_code=400, detail="invalid agent_target")

    active = load_prompt_active(uid)
    prev_key = active.get(agent_target)
    if not prev_key:
        return {"ok": True, "active": active, "message": "no active prompt for agent"}

    library = load_prompt_library(uid)
    if isinstance(library, dict) and prev_key in library and isinstance(library[prev_key], dict):
        library = dict(library)
        library[prev_key] = dict(library[prev_key])
        library[prev_key]["promotion_status"] = "superseded"
        save_prompt_library(uid, library)

    active = dict(active)
    del active[agent_target]
    save_prompt_active(uid, active)

    try:
        from supabase_doc_store import list_append_only

        list_append_only(
            "meta_mutation_log",
            {
                "type": "prompt_reset",
                "agent_target": agent_target,
                "previous_library_key": prev_key,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
            user_id=uid,
        )
    except Exception:
        pass

    return {"ok": True, "active": active}


@app.get("/api/meta/eval-set")
def get_meta_eval_set(request: Request):
    """Fixed startup ids used for reviewer prompt shadow evaluation."""
    uid = request.state.user_id
    ids = load_eval_startup_ids(uid)
    try:
        max_n = int(os.getenv("META_PROMPT_EVAL_SET_MAX", "50"))
    except ValueError:
        max_n = 50
    return {"startup_ids": ids, "count": len(ids), "max": max_n}


@app.put("/api/meta/eval-set")
async def put_meta_eval_set(request: Request):
    """Replace eval startup id list (validated against tenant storage)."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = body.get("startup_ids")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="startup_ids array required")
    try:
        max_n = int(os.getenv("META_PROMPT_EVAL_SET_MAX", "50"))
    except ValueError:
        max_n = 50
    storage = _get_storage(request)
    validated: List[str] = []
    missing: List[str] = []
    seen: set[str] = set()
    for x in raw:
        sid = str(x).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if len(validated) >= max_n:
            break
        if storage.get_startup(sid):
            validated.append(sid)
        else:
            missing.append(sid)
    payload = save_eval_startup_ids(uid, validated, max_n=max_n)
    return {"ok": True, **payload, "missing_startup_ids": missing[:30]}


@app.post("/api/meta/prompts/evaluate")
async def post_meta_prompt_evaluate(request: Request):
    """
    Shadow-run a pending reviewer prompt against the eval set (or startup_ids override).
    Persists pass/fail summary for optional META_PROMPT_REQUIRE_EVAL_PASS promote gate.
    """
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    library_key = str(body.get("library_key") or "").strip()
    if not agent_target or not library_key:
        raise HTTPException(status_code=400, detail="agent_target and library_key required")
    if agent_target not in REVIEWER_EVAL_AGENT_TARGETS:
        raise HTTPException(
            status_code=400,
            detail="agent_target must be DefaultReviewer, SkepticalReviewer, or OpportunistReviewer",
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY required for evaluation")

    storage = _get_storage(request)
    client = get_service_client()
    try:
        active = get_active_thesis(client, uid)
        if active is None:
            _bootstrap_default_thesis_or_raise(client, uid)
            active = get_active_thesis(client, uid)
        thesis_ctx = active.as_engine_context() if active else None
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=400, detail=str(e) or "fund thesis incomplete")

    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-5-nano")
    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        tenant_user_id=uid,
        model=reviewer_model,
        active_thesis=thesis_ctx,
    )
    override_ids = body.get("startup_ids")
    sid_list: Optional[List[str]] = None
    if isinstance(override_ids, list):
        sid_list = [str(x).strip() for x in override_ids if str(x).strip()]

    result = await run_prompt_evaluation(
        user_id=uid,
        agent_target=agent_target,
        library_key=library_key,
        storage=storage,
        reviewer_engine=reviewer_engine,
        startup_ids=sid_list,
    )
    return result


@app.get("/api/meta/weights")
def get_meta_weights(request: Request):
    """
    Return current scout weights used by the Meta-Agent reweighter.
    """
    return load_weights(request.state.user_id)


@app.get("/api/meta/calibration")
def get_meta_calibration(request: Request):
    """
    Return current calibration state for reviewer thresholds.
    """
    state = load_calibration_state(request.state.user_id)
    if not isinstance(state, dict):
        return {}
    return state


@app.get("/api/agents/status")
async def agents_status(request: Request):
    """
    Return whether the server is configured for agents (for debugging deployment).
    Does not expose secrets; use to see why agents might be skipped on e.g. Render.
    Includes fund thesis readiness for the authenticated user.
    """
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    supabase_configured = bool(
        use_supabase
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    openai_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    thesis_ready = False
    mandate_published = False
    active_thesis_version_id: Optional[str] = None
    thesis_error: Optional[str] = None
    if supabase_configured:
        try:
            t = get_active_thesis(get_service_client(), request.state.user_id)
            if t is None:
                thesis_error = "missing"
            else:
                thesis_ready = True
                active_thesis_version_id = t.version_id
                # The bootstrap default mandate carries is_default=True. A fund has
                # only "published" once it has deliberately replaced that default.
                mandate_published = not bool((t.parsed_json or {}).get("is_default"))
        except FundThesisIncompleteError:
            thesis_error = "incomplete"
        except Exception as e:
            thesis_error = type(e).__name__
    # Check user-level agent toggles so the status field reflects actual intent.
    user_id = request.state.user_id
    user_agents_enabled = False
    try:
        user_settings = load_settings(user_id)
        ac = user_settings.get("agent_config") or {}
        user_agents_enabled = bool(
            ac.get("scouts_enabled", False)
            or ac.get("reviewers_enabled", False)
            or ac.get("partners_enabled", False)
        )
    except Exception:
        pass
    return {
        "worker_ready": _agent_queue is not None,
        "lookup_worker_ready": _lookup_queue is not None,
        "agent_queue_size": _agent_queue.qsize() if _agent_queue is not None else None,
        "lookup_queue_size": _lookup_queue.qsize() if _lookup_queue is not None else None,
        "supabase_configured": supabase_configured,
        "openai_configured": openai_configured,
        "user_agents_enabled": user_agents_enabled,
        "agents_will_run": (
            supabase_configured
            and openai_configured
            and _agent_queue is not None
            and user_agents_enabled
            and thesis_ready
        ),
        "lookup_will_run": (
            supabase_configured
            and openai_configured
            and _lookup_queue is not None
        ),
        "thesis_ready": thesis_ready,
        "mandate_published": mandate_published,
        "active_thesis_version_id": active_thesis_version_id,
        "thesis_error": thesis_error,
    }


def _require_supabase_for_thesis() -> None:
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase or not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        raise HTTPException(status_code=503, detail="Supabase storage is required for fund thesis")


@app.get("/api/fund-thesis")
def api_get_fund_thesis(request: Request):
    """Active thesis, version list metadata, embedding status, recent pipeline links."""
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()
    try:
        active = get_active_thesis(client, uid)
        if active is None:
            _bootstrap_default_thesis_or_raise(client, uid)
            active = get_active_thesis(client, uid)
        if active is None:
            raise HTTPException(status_code=404, detail="No fund thesis yet. POST /api/fund-thesis/versions with raw_text.")
    except FundThesisQueryError as e:
        # Transient DB error — surface as 503 so callers can retry. Do NOT bootstrap
        # here, as doing so on query errors is what causes spurious version creation.
        raise HTTPException(status_code=503, detail=f"Thesis query failed: {e}")
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=503, detail=str(e))

    vr_rows = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_versions")
            .select("id,version_number,is_active,created_at")
            .eq("user_id", uid)
            .eq("thesis_id", active.thesis_id)
            .order("version_number", desc=True)
            .limit(50)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis versions query",
    )
    versions = getattr(vr_rows, "data", None) or []

    er_resp = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_embeddings")
            .select("model,created_at")
            .eq("version_id", active.version_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis embeddings query",
    )
    erows = getattr(er_resp, "data", None) or []
    emb_row = erows[0] if erows else {}

    lr_resp = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_pipeline_link")
            .select("id,thesis_version_id,pipeline_run_id,affected_startups_count,created_at")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis pipeline links query",
    )

    has_emb = thesis_has_embeddings(active)
    emb_status = "ready" if has_emb else "pending"
    emb_model = active.embedding_model if has_emb else "none"
    dim = len(active.embedding)
    return {
        "thesis_id": active.thesis_id,
        "active_version_id": active.version_id,
        "active_version_number": active.version_number,
        "parsed_json": active.parsed_json,
        "raw_text": active.raw_text[:50000],
        "mode": "embedding" if has_emb else "rule_based",
        "embedding": {
            "status": emb_status,
            "model": emb_model,
            "dimension": dim,
            "dimensions": dim,
            "created_at": emb_row.get("created_at"),
        },
        "versions": versions,
        "recent_pipeline_links": getattr(lr_resp, "data", None) or [],
    }


@app.get("/api/fund-thesis/runtime")
def get_fund_thesis_runtime(request: Request):
    """Lightweight thesis runtime (mode / embeddings) for System panel; alignment extras without parsed_json."""
    try:
        return _get_fund_thesis_runtime_impl(request)
    except FundThesisQueryError:
        raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from None
    except OSError as e:
        # EAGAIN under memory/socket pressure on small hosts (e.g. Render OOM edge).
        if getattr(e, "errno", None) == 11:
            raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from e
        raise
    except Exception as e:
        if _is_retryable_thesis_transport_error(e):
            raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from e
        raise


def _get_fund_thesis_runtime_impl(request: Request):
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()
    try:
        active = get_active_thesis(client, uid)
        if active is None:
            return JSONResponse(
                status_code=200,
                content={
                    "mode": "missing",
                    "embedding_status": "pending",
                    "has_embeddings": False,
                },
            )
    except FundThesisQueryError:
        raise HTTPException(status_code=503, detail="Thesis query failed; please retry")
    except FundThesisIncompleteError as e:
        return JSONResponse(
            status_code=200,
            content={
                "mode": "missing",
                "embedding_status": "pending",
                "has_embeddings": False,
                "thesis_ready": False,
                "error": "incomplete",
                "detail": str(e),
                "alignment_stats": {},
            },
        )

    has_emb = thesis_has_embeddings(active)
    mode = "embedding" if has_emb else "rule_based"
    embedding_status = "ready" if has_emb else "pending"
    emb_model = (
        (active.embedding_model or "").strip()
        if has_emb
        else "none"
    )
    if has_emb and not emb_model:
        emb_model = "none"

    prev_id: Optional[str] = None
    if active.version_number > 1:
        pr = (
            client.table("fund_thesis_versions")
            .select("id")
            .eq("user_id", uid)
            .eq("thesis_id", active.thesis_id)
            .eq("version_number", active.version_number - 1)
            .limit(1)
            .execute()
        )
        prow = getattr(pr, "data", None) or []
        if prow:
            prev_id = str(prow[0].get("id") or "")

    stats = compute_thesis_alignment_stats(
        client,
        uid,
        active_version_id=active.version_id,
        previous_version_id=prev_id,
        row_limit=int(os.getenv("FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT", "500")),
    )

    tr = (
        client.table("fund_thesis")
        .select("updated_at,active_version_id")
        .eq("user_id", uid)
        .limit(1)
        .execute()
    )
    trow = (getattr(tr, "data", None) or [{}])[0]

    tl_r = (
        client.table("fund_thesis_versions")
        .select("id,version_number,is_active,created_at")
        .eq("user_id", uid)
        .eq("thesis_id", active.thesis_id)
        .order("version_number", desc=True)
        .limit(15)
        .execute()
    )
    version_timeline = getattr(tl_r, "data", None) or []

    dim = len(active.embedding)
    payload: Dict[str, Any] = {
        "thesis_version_id": active.version_id,
        "mode": mode,
        "embedding_status": embedding_status,
        "embedding_model": emb_model,
        "has_embeddings": has_emb,
        # Backward-compatible fields for SystemIntelligence / clients
        "thesis_ready": True,
        "active_version_id": active.version_id,
        "active_version_number": active.version_number,
        "fund_thesis_updated_at": trow.get("updated_at"),
        "thesis_mode": mode,
        "embedding": {
            "status": embedding_status,
            "model": emb_model,
            "dimension": dim,
        },
        "embedding_dimensions": dim,
        "alignment_stats": stats,
        "version_timeline": version_timeline,
        "parsed_json": active.parsed_json,
    }
    return JSONResponse(status_code=200, content=payload)


@app.post("/api/fund-thesis/versions")
async def api_post_fund_thesis_version(request: Request):
    """Create a new thesis version (parse + embed + activate). Optional skip_embedding + parsed_json avoids OpenAI."""
    _require_supabase_for_thesis()
    body = await request.json()
    raw_text = str(body.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="raw_text is required")
    parsed_override = body.get("parsed_json")
    pipeline_run_id = str(body.get("pipeline_run_id") or "").strip() or None
    skip_embedding = bool(body.get("skip_embedding"))
    po = parsed_override if isinstance(parsed_override, dict) else None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key and not (po and skip_embedding):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY required unless both parsed_json and skip_embedding are set",
        )
    uid = request.state.user_id
    try:
        out = create_fund_thesis_version_for_user(
            get_service_client(),
            user_id=uid,
            raw_text=raw_text,
            api_key=api_key,
            parsed_json_override=po,
            pipeline_run_id=pipeline_run_id,
            skip_embedding=skip_embedding,
            skip_if_unchanged=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    status = "unchanged" if out.get("skipped") else "created"
    return {"status": status, **out}


@app.patch("/api/fund-thesis/active")
async def api_patch_fund_thesis_active(request: Request):
    """Activate an existing version (embeddings optional)."""
    _require_supabase_for_thesis()
    body = await request.json()
    version_id = str(body.get("version_id") or "").strip()
    if not version_id:
        raise HTTPException(status_code=422, detail="version_id is required")
    pipeline_run_id = str(body.get("pipeline_run_id") or "").strip() or None
    uid = request.state.user_id
    try:
        activate_fund_thesis_version(
            get_service_client(),
            user_id=uid,
            version_id=version_id,
            pipeline_run_id=pipeline_run_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": "ok", "active_version_id": version_id}


@app.post("/api/fund-thesis/reprocess-missing")
async def api_post_fund_thesis_reprocess_missing(
    request: Request,
    dry_run: bool = Query(False, description="If true, return eligible count only (no OpenAI calls)"),
):
    """
    Re-run reviewer + partner for startups that have reviews but no fund_thesis_version_id
    on review_info. Does not run scout or create new startups.
    """
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()

    if not dry_run:
        try:
            thesis = get_active_thesis(client, uid)
            if thesis is None:
                raise HTTPException(status_code=400, detail="No active thesis")
        except FundThesisIncompleteError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY required for thesis reprocessing",
            )

    try:
        result = await reprocess_startups_missing_fund_thesis(uid, dry_run=dry_run)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@app.post("/api/agents/trigger")
async def trigger_agents(request: Request):
    """
    Trigger agent execution for the current user.
    When Ops/Agents is on, start or reuse the user's persistent loop.
    When Ops/Agents is off, enqueue a manual one-shot cycle.
    """
    user_id = require_authenticated_user(request)
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        _logger_agents.info(
            "trigger_agents skipped user=%s reason=supabase_required",
            user_id[:12],
        )
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "supabase_required"},
        )
    try:
        settings = load_settings(user_id)
    except Exception as e:
        _logger_agents.warning(
            "trigger_agents skipped user=%s reason=settings_unavailable error=%s",
            user_id[:12],
            e,
        )
        # Fail closed: without real agent_config we cannot honor "all agents off" and
        # empty dict would default every gate to True (unexpected new discoveries).
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "settings_unavailable"},
        )
    agents_enabled = _agents_enabled_from_settings(settings)
    if agents_enabled and _is_user_loop_alive(user_id):
        _logger_agents.info(
            "trigger_agents ignored user=%s reason=loop_already_running",
            user_id[:12],
        )
        _logger_visible.info("[AGENT LOOP] Trigger ignored because loop already running for user %s", user_id[:12])
        return JSONResponse(
            status_code=202,
            content={"status": "loop_running", "user_id": user_id},
        )
    if agents_enabled and _loops_lock is None:
        _logger_agents.warning(
            "trigger_agents unavailable user=%s reason=loop_registry_not_ready",
            user_id[:12],
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "loop_registry_not_ready"},
        )
    if not agents_enabled and _agent_queue is None:
        _logger_agents.warning(
            "trigger_agents unavailable user=%s reason=worker_not_ready",
            user_id[:12],
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "worker_not_ready"},
        )
    lock_key = f"user:{user_id}:agent_trigger"
    if not _acquire_security_lock(lock_key, ttl_seconds=_AGENT_TRIGGER_LOCK_TTL_SECONDS):
        return JSONResponse(
            status_code=202,
            content={"status": "already_queued", "user_id": user_id},
        )
    limited = _enforce_rate_limits(f"user:{user_id}:agent_trigger", [_AGENT_TRIGGER_POLICY])
    if limited is not None:
        _release_security_lock(lock_key)
        return limited
    try:
        svc = get_service_client()
        thesis = get_active_thesis(svc, user_id)
        if thesis is None:
            _bootstrap_default_thesis_or_raise(svc, user_id)
            thesis = get_active_thesis(svc, user_id)
        if thesis is None:
            _logger_agents.info(
                "trigger_agents skipped user=%s reason=thesis_required",
                user_id[:12],
            )
            _release_security_lock(lock_key)
            return JSONResponse(
                status_code=200,
                content={"status": "skipped", "reason": "thesis_required"},
            )
    except FundThesisIncompleteError:
        _logger_agents.info(
            "trigger_agents skipped user=%s reason=thesis_required_incomplete",
            user_id[:12],
        )
        _release_security_lock(lock_key)
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "thesis_required"},
        )
    except Exception:
        _release_security_lock(lock_key)
        raise
    if agents_enabled:
        _release_security_lock(lock_key)
        started = await _ensure_user_loop(user_id)
        status = "loop_started" if started else "loop_running"
        _logger_agents.info("trigger_agents %s user=%s", status, user_id[:12])
        return JSONResponse(
            status_code=202,
            content={"status": status, "user_id": user_id},
        )

    await _agent_queue.put(
        {
            "type": "cycle",
            "user_id": user_id,
            "lock_key": lock_key,
            "manual_one_shot": True,
        }
    )
    _logger_agents.info("trigger_agents queued manual one-shot user=%s", user_id[:12])
    _logger_visible.info("trigger_agents queued manual one-shot user=%s", user_id[:12])
    return JSONResponse(
        status_code=202,
        content={"status": "queued", "user_id": user_id},
    )


@app.post("/api/agents/toggle")
async def toggle_agents(request: Request):
    """
    Enable or disable the persistent background loop for the current user.

    Body: { "enabled": true | false }

    When enabled=true:
      - Starts the loop if not already alive.
      - Does NOT override individual scouts/reviewers/partners toggles.

    When enabled=false:
      - Disables all three individual agent toggles (scouts, reviewers, partners).
      - Loop naturally stops after the active cycle finishes or the sleep is woken.
    """
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited

    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass

    enabled = bool(body.get("enabled", False))

    try:
        s = load_settings(user_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not load settings: {e}") from e

    ac = s.setdefault("agent_config", {})
    if enabled:
        # Mark status; individual toggles already saved by PATCH /api/settings
        ac["agents_status"] = "running"
        ac["agents_last_started_at"] = datetime.now(timezone.utc).isoformat()
    else:
        # Turn off all individual agent stages
        ac["scouts_enabled"] = False
        ac["reviewers_enabled"] = False
        ac["partners_enabled"] = False
        ac["agents_status"] = "stopped"

    try:
        save_settings(s, user_id)
    except Exception as e:
        _logger_agents.warning("toggle_agents: could not save settings for user %s: %s", user_id[:12], e)

    if enabled:
        await _ensure_user_loop(user_id)
        _logger_agents.info("toggle_agents enabled user=%s", user_id[:12])
        _logger_visible.info("[AGENT LOOP] Enabled by user %s — loop is active", user_id[:12])
    else:
        await _stop_user_loop(user_id)
        _logger_agents.info("toggle_agents disabled user=%s", user_id[:12])
        _logger_visible.info("[AGENT LOOP] Disabled by user %s — loop stopped", user_id[:12])

    return {"ok": True, "enabled": enabled, "user_id": user_id}


@app.get("/api/agents/loop-status")
async def get_loop_status(request: Request):
    """
    Return the live persistent-loop state for the current user.
    Used by the frontend to show accurate 'agents running' state.
    """
    user_id = request.state.user_id
    task = _per_user_loops.get(user_id)
    loop_alive = task is not None and not task.done()

    try:
        s = load_settings(user_id)
        ac = s.get("agent_config") or {}
    except Exception:
        ac = {}

    return {
        "loop_alive": loop_alive,
        "agents_enabled": bool(
            ac.get("scouts_enabled") or ac.get("reviewers_enabled") or ac.get("partners_enabled")
        ),
        "agents_status": ac.get("agents_status", "stopped"),
        "agents_last_started_at": ac.get("agents_last_started_at"),
    }



def _coerce_lookup_id(raw: Any) -> str:
    """
    Stable correlation id for on-demand lookup (queue → scout row → UI).
    Prefer client-generated UUID; otherwise allocate one here for API clients that omit it.
    """
    if raw is not None and str(raw).strip():
        s = str(raw).strip()
        if not _LOOKUP_ID_RE.match(s):
            raise HTTPException(
                status_code=422,
                detail="lookup_id must be 8-128 characters [a-zA-Z0-9_-]",
            )
        return s
    return str(uuid4())


def _parse_lookup_input(lookup_input: str) -> Dict[str, Optional[str]]:
    raw = (lookup_input or "").strip()
    lowered = raw.lower()
    website: Optional[str] = None
    company_name = _normalize_lookup_company_phrase(raw)
    input_type = "context_query"
    domain_like = re.match(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}([/:?#].*)?$", lowered)
    embedded_url_or_domain = re.search(
        r"(?i)\b((?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?#][^\s]*)?)\b",
        raw,
    )

    if domain_like:
        parsed = urlparse(raw if lowered.startswith(("http://", "https://")) else f"https://{raw}")
        host = (parsed.netloc or parsed.path or "").lower().strip()
        host = host[4:] if host.startswith("www.") else host
        website = host or None
        if website:
            label = website.split(".")[0].replace("-", " ").strip()
            company_name = label.title() if label else raw
            input_type = "website"
    else:
        if embedded_url_or_domain:
            token = embedded_url_or_domain.group(1).strip()
            parsed = urlparse(token if token.lower().startswith(("http://", "https://")) else f"https://{token}")
            host = (parsed.netloc or parsed.path or "").lower().strip()
            host = host[4:] if host.startswith("www.") else host
            website = host or None
            # Strip the detected website token so company_name remains clean.
            candidate_name = re.sub(re.escape(token), " ", raw, flags=re.IGNORECASE).strip(" ,|-")
            candidate_name = _normalize_lookup_company_phrase(candidate_name)
            if candidate_name and not _is_lookup_command_only(candidate_name):
                company_name = candidate_name
                input_type = "context_query" if len(candidate_name.split()) > 3 else "company_name"
            elif website:
                label = website.split(".")[0].replace("-", " ").strip()
                company_name = label.title() if label else raw
                input_type = "website"
        else:
            token_count = len([t for t in re.split(r"\s+", raw) if t])
            input_type = "company_name" if token_count <= 3 else "context_query"

    return {
        "company_name": company_name.strip() if company_name else raw,
        "website": website,
        "lookup_query": raw,
        "lookup_input_type": input_type,
    }


def _normalize_lookup_company_phrase(raw: str) -> str:
    """
    Keep on-demand lookup focused on the intended company when users type
    natural commands instead of only the brand name.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    value = _LOOKUP_LEADING_PHRASE_RE.sub("", value).strip(" ,:;-")
    value = re.sub(r"(?i)^(?:company|startup)\s+(?:named|called)\s+", "", value).strip(" ,:;-")
    tokens = [t for t in re.split(r"\s+", value) if t]
    if len(tokens) > 2:
        last = re.sub(r"[^a-z0-9]", "", tokens[-1].lower())
        starts_with_the = tokens[0].lower() == "the"
        if last in _LOOKUP_TRAILING_QUALIFIERS and not (last == "company" and starts_with_the):
            value = " ".join(tokens[:-1]).strip(" ,:;-")
    return value or raw.strip()


def _is_lookup_command_only(value: str) -> bool:
    normalized = re.sub(r"[^a-z ]+", " ", (value or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized in _LOOKUP_COMMAND_ONLY_PHRASES


@app.post("/api/startups/lookup")
async def lookup_startup(request: Request, body: Dict[str, Any]):
    """
    Enqueue on-demand company lookup on the dedicated lookup worker (not the main pipeline queue).
    Body: {"lookup_input": "...", "lookup_id": optional stable id (recommended; else server-generated)}.
    Backward compatible with {"company_name": "..."}.
    """
    lookup_input = str(body.get("lookup_input") or body.get("company_name") or "").strip()
    if not lookup_input:
        raise HTTPException(status_code=422, detail="lookup_input is required")
    if len(lookup_input) > 300:
        raise HTTPException(status_code=422, detail="lookup_input is too long")
    user_id = require_authenticated_user(request)
    lookup_id = _coerce_lookup_id(body.get("lookup_id"))
    parsed = _parse_lookup_input(lookup_input)
    company_name = str(parsed.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Could not derive company name from lookup_input")
    if _lookup_queue is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "lookup_worker_not_ready"},
        )
    lock_key = f"user:{user_id}:lookup:{lookup_id}"
    if not _acquire_security_lock(lock_key, ttl_seconds=_LOOKUP_LOCK_TTL_SECONDS):
        return JSONResponse(
            status_code=202,
            content={
                "status": "already_queued",
                "user_id": user_id,
                "lookup_id": lookup_id,
                "mode": "on_demand_lookup",
            },
        )
    limited = _enforce_rate_limits(f"user:{user_id}:lookup", [_LOOKUP_MINUTE_POLICY, _LOOKUP_DAY_POLICY])
    if limited is not None:
        _release_security_lock(lock_key)
        return limited
    await _lookup_queue.put(
        {
            "user_id": user_id,
            "company_name": company_name,
            "website": parsed.get("website"),
            "lookup_query": parsed.get("lookup_query"),
            "lookup_input_type": parsed.get("lookup_input_type"),
            "lookup_id": lookup_id,
            "lock_key": lock_key,
        }
    )
    return JSONResponse(
        status_code=202,
        content={
            "status": "queued",
            "user_id": user_id,
            "lookup_id": lookup_id,
            "lookup_input": lookup_input,
            "company_name": company_name,
            "website": parsed.get("website"),
            "lookup_input_type": parsed.get("lookup_input_type"),
            "mode": "on_demand_lookup",
        },
    )


@app.post("/api/meta/trigger")
async def trigger_meta_cycle(request: Request):
    """
    Manually trigger a Meta-Agent cycle.

    Returns a lightweight status object with the cycle number. When the
    Meta-Agent is disabled or returns no report, we surface a no-op
    status so the UI can display a graceful message.
    """
    uid = require_authenticated_user(request)
    lock_key = f"user:{uid}:meta_trigger"
    if not _acquire_security_lock(lock_key, ttl_seconds=_META_TRIGGER_LOCK_TTL_SECONDS):
        return JSONResponse(status_code=202, content={"status": "already_running", "cycle_number": 0})
    limited = _enforce_rate_limits(f"user:{uid}:meta_trigger", [_META_TRIGGER_POLICY])
    if limited is not None:
        _release_security_lock(lock_key)
        return limited
    try:
        agent = MetaAgent(user_id=uid)
        report = await agent.run_cycle()
        if not report:
            return {"status": "no-op", "cycle_number": 0}
        cycle_number = int(report.get("cycle_number", 0))
        return {"status": "ok", "cycle_number": cycle_number}
    finally:
        _release_security_lock(lock_key)


@app.get("/api/escalations")
async def get_escalations(request: Request):
    """
    Returns all startups where human_review_required=True and human_resolution is None.
    Shapes each result as EscalationItem (frontend type) with nested scout/review/partner.
    """
    storage = _get_storage(request)
    pending_raw = _get_pending_escalations(storage)
    items: List[Dict[str, Any]] = []
    for item in pending_raw:
        fe = _backend_to_frontend(item)
        startup_id = fe["id"]
        items.append(
            {
                "id": startup_id,
                "startup_id": startup_id,
                "startup_name": fe["scout"].get("name", ""),
                "scout": fe["scout"],
                "review": fe.get("review"),
                "partner": fe.get("partner"),
                "created_at": fe["timestamps"].get("partnered_at"),
                "human_resolution": item.get("human_resolution"),
            }
        )
    return items


@app.post("/api/escalations/{startup_id}/resolve")
async def resolve_escalation(request: Request, startup_id: str, body: Dict[str, Any]):
    """
    Resolve an escalation by writing human_resolution to the startup record.
    Body: {decision: "YES"|"NO"|"MAYBE", notes: str}
    """
    validate_route_id(startup_id, field_name="startup_id")
    uid = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{uid}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    decision = str(body.get("decision", "")).upper()
    notes = body.get("notes") or ""
    risk_acknowledged = bool(body.get("risk_acknowledged", False))
    # A mandate exception only applies to an affirmative ruling on a held deal.
    mandate_exception = bool(body.get("mandate_exception", False)) and decision == "YES"
    if decision not in ("YES", "NO", "MAYBE"):
        raise HTTPException(status_code=422, detail="decision must be YES, NO, or MAYBE")

    storage = _get_storage(request)
    existing = storage.get_by_id(startup_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Startup not found")
    settings = load_settings(request.state.user_id)
    fund_config = settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {}
    config_version = fund_config.get("versionLabel")
    if fund_config.get("version") is not None:
        config_version = f"{config_version or 'Fund Config'} v{fund_config.get('version')}"
    resolved_at = _now_iso()
    patch = build_conviction_patch(
        startup_id,
        existing,
        decision=decision,
        rationale=str(notes),
        resolved_at=resolved_at,
        risk_acknowledged=risk_acknowledged,
        mandate_exception=mandate_exception,
        config_version=str(config_version) if config_version else None,
    )
    patch["unresolved_at"] = None
    try:
        ok = storage.update_startup_partial(startup_id, patch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve escalation: {e}") from e

    if not ok:
        raise HTTPException(status_code=404, detail="Startup not found")

    # Feed analyst decisions into meta-agent signal (mutation log; type human_decision)
    try:
        from supabase_doc_store import list_append_only

        ai_rec = None
        try:
            st = storage.get_startup(startup_id)
            if st and st.partner_info is not None:
                ai_rec = st.partner_info.recommendation
        except Exception:
            pass
        list_append_only(
            "meta_mutation_log",
            {
                "type": "human_decision",
                "startup_id": startup_id,
                "human_decision": decision,
                "ai_recommendation_at_resolve": ai_rec,
                "disagreed_with_ai": bool(
                    ai_rec
                    and LEGACY_TO_RECOMMENDATION.get(decision)
                    and ai_rec != LEGACY_TO_RECOMMENDATION.get(decision)
                ),
                "notes": str(notes)[:4000],
                "mandate_exception": mandate_exception,
                "resolved_at": resolved_at,
            },
            user_id=request.state.user_id,
        )
    except Exception:
        pass

    try:
        current = load_settings(request.state.user_id)
        fund_memory = current.setdefault("fund_memory", {})
        historical = fund_memory.setdefault("historical_decisions", [])
        history = (patch.get("conviction_state") or {}).get("decision_history") or []
        if history:
            latest = dict(history[-1])
            latest["company_name"] = ((existing.get("scout_info") or {}).get("name") or "").strip()
            latest["sector"] = ((existing.get("scout_info") or {}).get("sector") or "").strip()
            latest["funding_stage"] = (existing.get("scout_info") or {}).get("funding_stage")
            historical.append(latest)
            fund_memory["historical_decisions"] = historical[-200:]
            save_settings(current, request.state.user_id)
    except Exception:
        pass

    return {"status": "ok"}


@app.get("/api/signals")
async def get_signals(request: Request):
    """
    Return the last 50 portfolio signals sorted by detected_at descending.
    Startup names come from request-scoped storage (Supabase) so they are user-correct.
    """
    store = _get_portfolio_store(request.state.user_id)
    signals_file = store.files.get("signals")
    records = store._read_file(signals_file) if signals_file is not None else []
    # Attach startup names from request-scoped storage (user's startups)
    storage = _get_storage(request)
    startups_index = _startup_name_index(storage)
    for r in records:
        if "startup_name" not in r:
            r["startup_name"] = startups_index.get(r.get("startup_id") or "", "")
    records.sort(key=lambda r: r.get("detected_at", ""), reverse=True)
    return records[:50]


@app.get("/api/analytics/rejections")
async def get_rejection_analytics(request: Request):
    """
    Return rejection analytics summarising red flags, sectors, and scores (tenant-scoped).
    """
    root = _get_root()
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    uid = request.state.user_id
    analyzer = RejectionAnalyzer(
        data_dir=str(root / "data" / "portfolio"),
        user_id=uid if use_supabase else None,
    )
    patterns = analyzer.get_patterns()
    if not patterns:
        return {
            "most_common_red_flags": [],
            "rejection_by_sector": {},
            "avg_scores_at_rejection": {},
            "most_common_fail_dimensions": [],
        }

    # Red flags as-is from analyzer
    red_flags = patterns.get("most_common_red_flags") or []
    if not isinstance(red_flags, list):
        red_flags = []

    # Rejection by sector: add pct_of_total
    by_sector_raw = patterns.get("rejection_by_sector") or {}
    if not isinstance(by_sector_raw, dict):
        by_sector_raw = {}
    total_rejections = patterns.get("_rejection_count", 0) or 0
    rejection_by_sector: Dict[str, Any] = {}
    for sector, count in by_sector_raw.items():
        try:
            c = int(count)
        except Exception:
            continue
        pct = (c / total_rejections * 100.0) if total_rejections > 0 else 0.0
        rejection_by_sector[sector] = {"count": c, "pct_of_total": round(pct, 2)}

    avg_scores = patterns.get("avg_scores_at_rejection") or {}
    if not isinstance(avg_scores, dict):
        avg_scores = {}

    fail_dims_raw = patterns.get("most_common_fail_dimensions") or []
    if isinstance(fail_dims_raw, list) and fail_dims_raw and isinstance(fail_dims_raw[0], dict):
        most_common_fail_dimensions = [d.get("dimension", "") for d in fail_dims_raw if d.get("dimension")]
    elif isinstance(fail_dims_raw, list):
        most_common_fail_dimensions = [str(d) for d in fail_dims_raw]
    else:
        most_common_fail_dimensions = []

    return {
        "most_common_red_flags": red_flags,
        "rejection_by_sector": rejection_by_sector,
        "avg_scores_at_rejection": avg_scores,
        "most_common_fail_dimensions": most_common_fail_dimensions,
    }


@app.get("/api/analytics/watchlist")
async def get_watchlist_analytics(request: Request):
    """
    Return watchlist health analytics: total, stale, average days, and per-entry stats.
    Startup names come from request-scoped storage so they are user-correct.
    """
    store = _get_portfolio_store(request.state.user_id)
    try:
        watchlist = store.get_all_watchlist()
    except Exception:
        watchlist = []

    total = len(watchlist)
    if total == 0:
        return {"total": 0, "stale": 0, "avg_days": 0, "entries": []}

    now = datetime.now(timezone.utc)
    # Build signal index (Supabase)
    signals_file = store.files.get("signals")
    signals = store._read_file(signals_file) if signals_file is not None else []
    signal_counts: Dict[str, int] = {}
    for s in signals:
        sid = s.get("startup_id")
        if not sid:
            continue
        signal_counts[sid] = signal_counts.get(sid, 0) + 1

    # Startup names from request-scoped storage (user's startups)
    storage = _get_storage(request)
    startups_index = _startup_name_index(storage)

    stale = 0
    days_total = 0
    entries: List[Dict[str, Any]] = []

    for entry in watchlist:
        sid = entry.get("startup_id")
        name = startups_index.get(sid or "", "")
        added_at_str = entry.get("added_at")
        days_on_watchlist = 0
        try:
            if added_at_str:
                dt = datetime.fromisoformat(added_at_str)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_on_watchlist = (now - dt).days
        except Exception:
            days_on_watchlist = 0
        days_total += days_on_watchlist
        stale_flag = bool(entry.get("stale_warning", False))
        if stale_flag:
            stale += 1
        entries.append(
            {
                "startup_id": sid,
                "startup_name": name,
                "days_on_watchlist": days_on_watchlist,
                "stale_warning": stale_flag,
                "signal_count": signal_counts.get(sid or "", 0),
            }
        )

    avg_days = days_total / total if total > 0 else 0.0
    return {"total": total, "stale": stale, "avg_days": avg_days, "entries": entries}


@app.get("/api/analytics/concentration")
async def get_concentration_analytics(request: Request):
    """
    Return sector concentration analytics from data/analytics/sector_concentration.json.
    """
    root = _get_root()
    path = root / "data" / "analytics" / "sector_concentration.json"
    user_id = getattr(request.state, "user_id", None)
    data = _read_json_dict_file(path, user_id=user_id)
    if not data:
        return {
            "by_sector": {},
            "most_concentrated_sector": "",
            "most_concentrated_theme": "",
            "last_updated": "",
        }
    return data


@app.get("/api/analytics/system-health")
async def get_system_health(request: Request):
    """
    Aggregate system health metrics (calibration, queues, budgets, escalations).
    """
    storage = _get_storage(request)
    user_id = getattr(request.state, "user_id", None)
    return _get_system_health(storage, user_id=user_id)


@app.get("/api/activity/summary")
async def get_activity_summary(request: Request):
    """
    Return aggregated pipeline activity since the user's last visit.
    Does NOT update last_seen_at — that only happens on POST /api/activity/seen (dismiss).
    """
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    svc = get_service_client()

    # 1. Read last_seen_at
    try:
        state_row = (
            svc.table("user_state")
            .select("last_seen_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        last_seen_at = (state_row.data or {}).get("last_seen_at")
    except Exception:
        last_seen_at = None

    if not last_seen_at:
        # First visit — include all historical pipeline activity
        last_seen_at = "1970-01-01T00:00:00Z"

    # 2. Query pipeline_activity since last_seen_at
    try:
        rows = (
            svc.table("pipeline_activity")
            .select("startups_found,reviewed_count,decisions_made,escalations_count")
            .eq("user_id", user_id)
            .gt("timestamp", last_seen_at)
            .execute()
        )
        activity_rows = rows.data or []
    except Exception:
        activity_rows = []

    # 3. Aggregate totals. "decided" is retained as a backwards-compatible
    # alias for agent_decided; human decisions are counted separately.
    human_reviewed = 0
    open_in_progress = 0

    try:
        human_rows = (
            svc.table("startups")
            .select("startup_id", count="exact")
            .eq("user_id", user_id)
            .gt("human_resolution->>resolved_at", last_seen_at)
            .execute()
        )
        human_reviewed = int(getattr(human_rows, "count", None) or 0)
    except Exception as e:
        logging.getLogger("api").warning("activity human decision aggregation failed: %s", e)

    try:
        open_rows = (
            svc.table("startups")
            .select("startup_id", count="exact")
            .eq("user_id", user_id)
            .not_.is_("unresolved_at", "null")
            .execute()
        )
        open_in_progress = int(getattr(open_rows, "count", None) or 0)
    except Exception as e:
        logging.getLogger("api").warning("activity open aggregation failed: %s", e)

    totals = _aggregate_activity_totals(
        activity_rows,
        human_reviewed=human_reviewed,
        open_in_progress=open_in_progress,
    )

    logging.getLogger("api").info(
        "activity_summary user_id=%s since=%s agent_decided=%s human_reviewed=%s open_in_progress=%s",
        user_id[:24],
        last_seen_at,
        totals["agent_decided"],
        totals["human_reviewed"],
        totals["open_in_progress"],
    )

    # last_seen_at is NOT updated here — only updated when the user explicitly
    # dismisses the modal via POST /api/activity/seen
    return JSONResponse(content=totals)


@app.post("/api/activity/seen")
async def mark_activity_seen(request: Request):
    """Mark the current time as last_seen_at. Called when the user dismisses the summary modal."""
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    svc = get_service_client()
    try:
        svc.table("user_state").upsert(
            {
                "user_id": user_id,
                "last_seen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            on_conflict="user_id",
        ).execute()
    except Exception as e:
        logging.getLogger("api").warning("Could not update user_state last_seen_at: %s", e)
    return JSONResponse(content={"ok": True})
