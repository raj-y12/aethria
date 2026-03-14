"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
Per-user agent pipeline: POST /api/agents/trigger enqueues a run for the authenticated user.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from utils.storage import Storage
from utils.settings_loader import DEFAULT_SETTINGS, get_settings_path, load_settings, save_settings, get_meta_agent_settings, is_cost_budget_enabled
from auth_clerk import verify_clerk_token
from run_context import set_run_user_id
from supabase_client import get_service_client
from supabase_storage import SupabaseStartupsStorage
from memo_generator import MemoGenerator
from meta.agent import MetaAgent  # For manual trigger
from meta.mutator import _PROMPT_LIBRARY_PATH, _read_json_dict, _read_json_list
from meta.reweighter import load_weights
from meta.calibrator import load_calibration_state
from portfolio.store import PortfolioStore
from portfolio.cost_control import CostController
from pipeline_runner import run_one_pipeline_cycle

_agent_queue: Optional[asyncio.Queue[str]] = None
_agent_worker_task: Optional[asyncio.Task] = None
_logger_agents = logging.getLogger("api.agents")


async def _agent_worker() -> None:
    """Background worker: run one pipeline cycle per dequeued user_id."""
    if _agent_queue is None:
        return
    while True:
        try:
            user_id = await _agent_queue.get()
            try:
                await run_one_pipeline_cycle(user_id)
            except Exception as e:
                _logger_agents.exception("Pipeline cycle error for user %s: %s", user_id[:12] if user_id else "?", e)
            finally:
                _agent_queue.task_done()
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _agent_queue, _agent_worker_task
    _agent_queue = asyncio.Queue()
    _agent_worker_task = asyncio.create_task(_agent_worker())
    _logger_agents.info("Per-user agent worker started")
    yield
    if _agent_worker_task:
        _agent_worker_task.cancel()
        try:
            await _agent_worker_task
        except asyncio.CancelledError:
            pass
    _logger_agents.info("Per-user agent worker stopped")


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

# Public paths that skip Clerk JWT auth
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/redoc/", "/openapi.json/"}

@app.middleware("http")
async def clerk_auth_middleware(request: Request, call_next):
    """Extract Bearer token, verify Clerk JWT, attach user_id to request.state. Return 401 if invalid."""
    if request.method == "OPTIONS":
        return await call_next(request)
    if request.url.path in _PUBLIC_PATHS or request.url.path.rstrip("/") in _PUBLIC_PATHS:
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
    set_run_user_id(user_id)  # scope doc/list storage to this user for the request
    return await call_next(request)


def _now_iso() -> str:
    """Return current time as ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _get_root() -> Path:
    return Path(__file__).resolve().parent


def _get_portfolio_store() -> PortfolioStore:
    """Return a PortfolioStore rooted at data/portfolio."""
    root = _get_root()
    return PortfolioStore(data_dir=str(root / "data" / "portfolio"))


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
    portfolio_store = _get_portfolio_store()
    calibration_warning = None
    metrics_file = portfolio_store.files.get("agent_metrics")
    if metrics_file is not None:
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
        watchlist = len(portfolio_store.get_all_watchlist())
    except Exception:
        watchlist = 0

    # Budget status only when cost budget enforcement is enabled for this user
    budget_status: List[Dict[str, Any]] = []
    if is_cost_budget_enabled(user_id):
        cost_controller = CostController()
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


def _backend_to_frontend(raw: dict) -> dict:
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
            "funding_stage": scout.get("funding_stage"),
            "est_tam": scout.get("est_tam"),
            "references": scout.get("references") or [],
        },
        "timestamps": timestamps,
    }

    if review:
        out["review"] = {
            "market_score": review.get("market_score"),
            "product_score": review.get("product_score"),
            "technical_score": review.get("technical_score"),
            "execution_score": review.get("execution_score"),
            "defensibility_score": review.get("defensibility_score"),
            "overall_summary": review.get("overall_summary"),
            "key_risks": review.get("key_risks") or [],
            "verdict": review.get("verdict"),
            "score_reasoning": review.get("score_reasoning") or None,
            "diligence_red_flags": review.get("diligence_red_flags") or [],
            "assumption_feedback": review.get("assumption_feedback") or [],
            "team_analysis": review.get("team_analysis") or None,
            "competition_analysis": review.get("competition_analysis") or None,
            "business_model_analysis": review.get("business_model_analysis") or None,
            "investment_thesis": review.get("investment_thesis") or None,
            "risk_mitigation": review.get("risk_mitigation") or None,
        }
    else:
        out["review"] = None

    if partner:
        out["partner"] = {
            "decision": partner.get("decision", "NO"),
            "confidence": partner.get("conviction_level"),
            "rationale": partner.get("rationale"),
            "next_action": partner.get("next_action"),
            "human_review_required": partner.get("human_review_required", False),
        }
    else:
        out["partner"] = None

    return out


def _get_storage(request: Request):
    """Return Supabase startups storage for the authenticated user.
    Uses service-role client and Clerk-derived user_id; we never send Clerk JWT to Supabase.
    """
    return SupabaseStartupsStorage(
        get_service_client(),
        request.state.user_id,
    )


@app.get("/api/startups")
def get_startups(request: Request):
    storage = _get_storage(request)
    raw_list = storage.get_all()
    return [_backend_to_frontend(r) for r in raw_list]


@app.get("/api/startups/{startup_id}/memo")
def get_startup_memo(request: Request, startup_id: str):
    """Return full investment memo (markdown) for a startup from MemoGenerator."""
    storage = _get_storage(request)
    startup = storage.get_startup(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    memo = MemoGenerator().generate_memo(startup, for_display=True)
    return {"memo": memo}


@app.get("/health")
def health():
    """Lightweight health check (public; no auth). Pending escalations require auth via /api/settings."""
    return {"status": "ok"}


@app.get("/api/me")
def get_me(request: Request):
    """Return the current user's id (Clerk JWT sub). Used for multi-user: API uses this per request; agents use AETHRIA_DEFAULT_USER_ID when running in background."""
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
def patch_settings(request: Request, body: dict):
    """Update current user's settings. Validates server-side; returns 422 on validation errors."""
    errors = _validate_settings(body)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Validation failed", "errors": errors})
    user_id = request.state.user_id
    current = load_settings(user_id)
    for section in ("cost_budget", "agent_config", "portfolio"):
        if section in body and isinstance(body[section], dict):
            if section not in current:
                current[section] = {}
            for k, v in body[section].items():
                current[section][k] = v
    _save_settings(current, user_id)
    # Meta-Agent settings are derived from environment; PATCH does not
    # persist or validate them, but we still include the live view.
    meta_agent = get_meta_agent_settings()
    meta_agent["model"] = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
    current["meta_agent"] = meta_agent
    return current


@app.get("/api/meta/reports")
def get_meta_reports():
    """
    Return the last 10 Meta-Agent cycle reports.
    """
    reports = _read_json_list(_PROMPT_LIBRARY_PATH.parent / "meta_reports.json")
    if not isinstance(reports, list):
        return []
    # Return most recent first
    return list(reversed(reports[-10:]))


@app.get("/api/meta/prompt-library")
def get_meta_prompt_library():
    """
    Return the full prompt library used by the Meta-Agent.
    """
    library = _read_json_dict(_PROMPT_LIBRARY_PATH)
    if not isinstance(library, dict):
        return {}
    return library


@app.get("/api/meta/weights")
def get_meta_weights():
    """
    Return current scout weights used by the Meta-Agent reweighter.
    """
    return load_weights()


@app.get("/api/meta/calibration")
def get_meta_calibration():
    """
    Return current calibration state for reviewer thresholds.
    """
    state = load_calibration_state()
    if not isinstance(state, dict):
        return {}
    return state


@app.get("/api/agents/status")
async def agents_status():
    """
    Return whether the server is configured for agents (for debugging deployment).
    Does not expose secrets; use to see why agents might be skipped on e.g. Render.
    """
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    supabase_configured = bool(
        use_supabase
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    openai_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    return {
        "worker_ready": _agent_queue is not None,
        "supabase_configured": supabase_configured,
        "openai_configured": openai_configured,
        "agents_will_run": supabase_configured and openai_configured and _agent_queue is not None,
    }


@app.post("/api/agents/trigger")
async def trigger_agents(request: Request):
    """
    Enqueue a pipeline run for the current user (per-user agents).
    When the user has agents enabled in settings, one scout/reviewer/partner
    cycle is queued and run in the background. Multiple users get independent runs.
    """
    user_id = request.state.user_id
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "supabase_required"},
        )
    settings = load_settings(user_id)
    ac = settings.get("agent_config") or {}
    if not (ac.get("scouts_enabled", True) or ac.get("reviewers_enabled", True) or ac.get("partners_enabled", True)):
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "agents_disabled"},
        )
    if _agent_queue is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "worker_not_ready"},
        )
    await _agent_queue.put(user_id)
    return JSONResponse(
        status_code=202,
        content={"status": "queued", "user_id": user_id},
    )


@app.post("/api/meta/trigger")
async def trigger_meta_cycle():
    """
    Manually trigger a Meta-Agent cycle.

    Returns a lightweight status object with the cycle number. When the
    Meta-Agent is disabled or returns no report, we surface a no-op
    status so the UI can display a graceful message.
    """
    agent = MetaAgent()
    report = await agent.run_cycle()
    if not report:
        return {"status": "no-op", "cycle_number": 0}
    cycle_number = int(report.get("cycle_number", 0))
    return {"status": "ok", "cycle_number": cycle_number}


@app.get("/api/escalations")
async def get_escalations(request: Request):
    """
    Returns all startups where human_review_required=True and human_resolution is None.
    Shapes each result as an escalation summary for the System Intelligence panel.
    """
    storage = _get_storage(request)
    pending_raw = _get_pending_escalations(storage)
    items: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for item in pending_raw:
        scout = item.get("scout_info") or {}
        partner = item.get("partner_info") or {}
        startup_id = item.get("startup_id") or scout.get("startup_id") or item.get("id")
        name = scout.get("name", "")
        sector = scout.get("sector", "")
        decision = partner.get("decision")
        conviction = partner.get("conviction_level") or partner.get("confidence")
        rationale = partner.get("rationale")
        llm_reason = partner.get("llm_fallback_reason")
        human_required = bool(partner.get("human_review_required", False))
        partnered_at = partner.get("partnered_at")
        days_pending = None
        escalated_at = None
        try:
            if partnered_at:
                dt = datetime.fromisoformat(str(partnered_at))
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                escalated_at = dt.isoformat()
                days_pending = (now - dt).days
        except Exception:
            days_pending = None
            escalated_at = None

        items.append(
            {
                "startup_id": startup_id,
                "startup_name": name,
                "sector": sector,
                "partner_decision": decision,
                "conviction_level": conviction,
                "rationale": rationale,
                "llm_fallback_reason": llm_reason,
                "human_review_required": human_required,
                "escalated_at": escalated_at,
                "days_pending": days_pending,
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
    decision = str(body.get("decision", "")).upper()
    notes = body.get("notes") or ""
    if decision not in ("YES", "NO", "MAYBE"):
        raise HTTPException(status_code=422, detail="decision must be YES, NO, or MAYBE")

    storage = _get_storage(request)
    found = {"value": False}

    def _updater(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for i, item in enumerate(data):
            if item.get("startup_id") == startup_id:
                hr = {
                    "decision": decision,
                    "notes": notes,
                    "resolved_at": _now_iso(),
                }
                new_item = dict(item)
                new_item["human_resolution"] = hr
                data[i] = new_item
                found["value"] = True
                break
        return data

    try:
        storage._atomic_update(_updater)  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve escalation: {e}")

    if not found["value"]:
        raise HTTPException(status_code=404, detail="Startup not found")

    return {"status": "ok"}


@app.get("/api/signals")
async def get_signals():
    """
    Return the last 50 portfolio signals sorted by detected_at descending.
    """
    store = _get_portfolio_store()
    signals_file = store.files.get("signals")
    records = store._read_file(signals_file) if signals_file is not None else []
    # Attach startup names where possible
    startups_index = {s.get("id"): s for s in store.get_all_startups()}
    for r in records:
        sid = r.get("startup_id")
        startup = startups_index.get(sid or "")
        if startup and "startup_name" not in r:
            r["startup_name"] = startup.get("name")
    records.sort(key=lambda r: r.get("detected_at", ""), reverse=True)
    return records[:50]


@app.get("/api/analytics/rejections")
async def get_rejection_analytics():
    """
    Return rejection analytics summarising red flags, sectors, and scores.
    """
    root = _get_root()
    patterns_path = root / "data" / "portfolio" / "rejection_patterns.json"
    patterns = _read_json_dict_file(patterns_path)
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
async def get_watchlist_analytics():
    """
    Return watchlist health analytics: total, stale, average days, and per-entry stats.
    """
    store = _get_portfolio_store()
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

    startups_index = {s.get("id"): s for s in store.get_all_startups()}

    stale = 0
    days_total = 0
    entries: List[Dict[str, Any]] = []

    for entry in watchlist:
        sid = entry.get("startup_id")
        startup = startups_index.get(sid or "")
        name = startup.get("name") if startup else ""
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
