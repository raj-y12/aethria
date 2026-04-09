"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
Per-user agent pipeline: POST /api/agents/trigger enqueues a run for the authenticated user.
On-demand lookup uses a separate queue/worker so it is not blocked by full scout/reviewer/partner cycles.
"""
import asyncio
import json
import logging
import os
import re
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

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from utils.storage import Storage
from utils.settings_loader import (
    DEFAULT_SETTINGS,
    get_settings_path,
    load_settings,
    save_settings,
    get_meta_agent_settings,
    is_cost_budget_enabled,
)
from auth_clerk import verify_clerk_token
from supabase_client import get_service_client
from supabase_doc_store import list_get_all, list_get_by_id
from supabase_storage import SupabaseStartupsStorage
from memo_generator import MemoGenerator
from meta.agent import MetaAgent  # For manual trigger
from meta.reweighter import load_weights
from meta.calibrator import load_calibration_state
from portfolio.store import PortfolioStore
from portfolio.rejection import RejectionAnalyzer
from portfolio.cost_control import CostController
from pipeline_runner import (
    reprocess_startups_missing_fund_thesis,
    run_one_pipeline_cycle,
    run_on_demand_lookup,
)
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisMissingError,
    compute_thesis_alignment_stats,
    get_active_thesis,
    thesis_has_embeddings,
)
from fund_thesis_ops import activate_fund_thesis_version, create_fund_thesis_version_for_user
from models import Startup
from core import policy_resolver

_agent_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_agent_worker_task: Optional[asyncio.Task] = None
_lookup_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_lookup_worker_task: Optional[asyncio.Task] = None
_logger_agents = logging.getLogger("api.agents")
_logger_visible = logging.getLogger("uvicorn.error")
_LOOKUP_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")


async def _agent_worker() -> None:
    """Background worker: full scout/reviewer/partner cycles only (not on-demand lookup)."""
    if _agent_queue is None:
        return
    while True:
        try:
            job = await _agent_queue.get()
            user_id = str(job.get("user_id") or "").strip()
            try:
                await run_one_pipeline_cycle(user_id)
            except Exception as e:
                _logger_agents.exception("Pipeline cycle error for user %s: %s", user_id[:12] if user_id else "?", e)
            finally:
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
                _lookup_queue.task_done()
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _agent_queue, _agent_worker_task, _lookup_queue, _lookup_worker_task
    _agent_queue = asyncio.Queue()
    _lookup_queue = asyncio.Queue()
    _agent_worker_task = asyncio.create_task(_agent_worker())
    _lookup_worker_task = asyncio.create_task(_lookup_worker())
    _logger_agents.info("Pipeline agent worker + on-demand lookup worker started")
    yield
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
            "primary_thesis": scout.get("primary_thesis"),
            "key_assumptions": scout.get("key_assumptions") or None,
            "biggest_unknown": scout.get("biggest_unknown"),
            "funding_stage": scout.get("funding_stage"),
            "est_tam": scout.get("est_tam"),
            "references": scout.get("references") or [],
            "origin_type": scout.get("origin_type"),
            "lookup_input_type": scout.get("lookup_input_type"),
            "lookup_query": scout.get("lookup_query"),
            "lookup_website": scout.get("lookup_website"),
            "lookup_id": scout.get("lookup_id"),
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
            "consensus_verdict": review.get("consensus_verdict"),
            "reviewer_disagreement": review.get("reviewer_disagreement"),
            "score_variance": review.get("score_variance"),
            "fund_thesis_version_id": review.get("fund_thesis_version_id"),
            "thesis_alignment_score": review.get("thesis_alignment_score"),
            "thesis_matches_fund": review.get("thesis_matches_fund"),
            "thesis_fit_points": review.get("thesis_fit_points") or None,
            "thesis_deviation_points": review.get("thesis_deviation_points") or None,
            "thesis_alignment_confidence": review.get("thesis_alignment_confidence"),
            "fund_thesis_alignment_score": review.get("fund_thesis_alignment_score"),
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
            "llm_fallback_reason": partner.get("llm_fallback_reason"),
            "memo_at_decision": partner.get("memo_at_decision"),
            "portfolio_context_at_decision": partner.get("portfolio_context_at_decision"),
            "prompt_version": partner.get("prompt_version"),
        }
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
    }


def _list_projection_to_frontend(row: Dict[str, Any]) -> Dict[str, Any]:
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
    }
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
        },
        "timestamps": timestamps,
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
        }
    else:
        out["review"] = None
    if row.get("partner_decision"):
        out["partner"] = {
            "decision": row.get("partner_decision"),
            "human_review_required": bool(row.get("partner_human_review_required")),
        }
    else:
        out["partner"] = None
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
        thin_rev = {
            "verdict": rev.get("verdict"),
            "consensus_verdict": rev.get("consensus_verdict") or rev.get("verdict"),
            "overall_summary": (rev.get("overall_summary") or "")[:400],
            "reviewer_disagreement": rev.get("reviewer_disagreement"),
            "aggregate_score": None,
        }
        scores = [rev.get("market_score"), rev.get("product_score"), rev.get("technical_score"), rev.get("execution_score")]
        if all(isinstance(x, (int, float)) for x in scores):
            thin_rev["aggregate_score"] = sum(scores) / 4.0  # type: ignore[arg-type]
    part = obj.get("partner") or {}
    thin_part: Optional[Dict[str, Any]] = None
    if part:
        thin_part = {
            "decision": part.get("decision"),
            "human_review_required": part.get("human_review_required", False),
        }
    return {**obj, "scout": scout, "review": thin_rev, "partner": thin_part}


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
    if isinstance(storage, SupabaseStartupsStorage):
        rows = storage.get_list_projection_rows()
        if rows is not None:
            return [_list_projection_to_frontend(r) for r in rows]
        raw_list = storage.get_all()
        full = [_backend_to_frontend(r) for r in raw_list]
        return [_thin_list_from_full_frontend(x) for x in full]
    raw_list = storage.get_all()
    full = [_backend_to_frontend(r) for r in raw_list]
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
    storage = _get_storage(request)
    raw = storage.get_by_id(startup_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Startup not found")
    return _backend_to_frontend(raw)


@app.get("/api/startups/{startup_id}/memo")
def get_startup_memo(request: Request, startup_id: str):
    """
    Memo readiness + optional persisted markdown (Supabase).
    Never blocks on memo generation.
    Response: { status, memo, partial?, pipeline_run_id, error }.
    """
    from pipeline_state import get_pipeline_state_row

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

        return {
            "status": "generating",
            "memo": None,
            "partial": None,
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
def patch_settings(request: Request, body: dict):
    """Update current user's settings. Validates server-side; returns 422 on validation errors."""
    errors = _validate_settings(body)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Validation failed", "errors": errors})
    user_id = request.state.user_id
    current = load_settings(user_id)
    for section in ("fund_identity", "cost_budget", "agent_config", "portfolio"):
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
    from supabase_doc_store import doc_get

    library = doc_get("meta_prompt_library", user_id=request.state.user_id)
    if not isinstance(library, dict):
        return {}
    return library


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
        except FundThesisIncompleteError:
            thesis_error = "incomplete"
        except Exception as e:
            thesis_error = type(e).__name__
    return {
        "worker_ready": _agent_queue is not None,
        "supabase_configured": supabase_configured,
        "openai_configured": openai_configured,
        "agents_will_run": supabase_configured and openai_configured and _agent_queue is not None,
        "thesis_ready": thesis_ready,
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
            raise HTTPException(status_code=404, detail="No fund thesis yet. POST /api/fund-thesis/versions with raw_text.")
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=503, detail=str(e))

    vr = (
        client.table("fund_thesis_versions")
        .select("id,version_number,is_active,created_at")
        .eq("user_id", uid)
        .eq("thesis_id", active.thesis_id)
        .order("version_number", desc=True)
        .limit(50)
        .execute()
    )
    versions = getattr(vr, "data", None) or []

    er = (
        client.table("fund_thesis_embeddings")
        .select("model,created_at")
        .eq("version_id", active.version_id)
        .eq("user_id", uid)
        .limit(1)
        .execute()
    )
    erows = getattr(er, "data", None) or []
    emb_row = erows[0] if erows else {}

    lr = (
        client.table("fund_thesis_pipeline_link")
        .select("id,thesis_version_id,pipeline_run_id,affected_startups_count,created_at")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
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
        "recent_pipeline_links": getattr(lr, "data", None) or [],
    }


@app.get("/api/fund-thesis/runtime")
def get_fund_thesis_runtime(request: Request):
    """Lightweight thesis runtime (mode / embeddings) for System panel; alignment extras without parsed_json."""
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
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "created", **out}


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
    Enqueue a pipeline run for the current user (per-user agents).
    When the user has agents enabled in settings, one scout/reviewer/partner
    cycle is queued and run in the background. Multiple users get independent runs.
    """
    user_id = request.state.user_id
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
    ac = settings.get("agent_config") or {}
    if not (ac.get("scouts_enabled", True) or ac.get("reviewers_enabled", True) or ac.get("partners_enabled", True)):
        _logger_agents.info(
            "trigger_agents skipped user=%s reason=agents_disabled",
            user_id[:12],
        )
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "agents_disabled"},
        )
    if _agent_queue is None:
        _logger_agents.warning(
            "trigger_agents unavailable user=%s reason=worker_not_ready",
            user_id[:12],
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "worker_not_ready"},
        )
    try:
        thesis = get_active_thesis(get_service_client(), user_id)
        if thesis is None:
            _logger_agents.info(
                "trigger_agents skipped user=%s reason=thesis_required",
                user_id[:12],
            )
            return JSONResponse(
                status_code=200,
                content={"status": "skipped", "reason": "thesis_required"},
            )
    except FundThesisIncompleteError:
        _logger_agents.info(
            "trigger_agents skipped user=%s reason=thesis_required_incomplete",
            user_id[:12],
        )
        return JSONResponse(
            status_code=200,
            content={"status": "skipped", "reason": "thesis_required"},
        )
    await _agent_queue.put({"type": "cycle", "user_id": user_id})
    _logger_agents.info("trigger_agents queued user=%s", user_id[:12])
    _logger_visible.info("trigger_agents queued user=%s", user_id[:12])
    return JSONResponse(
        status_code=202,
        content={"status": "queued", "user_id": user_id},
    )



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
    company_name = raw
    input_type = "context_query"

    domain_like = re.match(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}([/:?#].*)?$", lowered)
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
        token_count = len([t for t in re.split(r"\s+", raw) if t])
        input_type = "company_name" if token_count <= 3 else "context_query"

    return {
        "company_name": company_name.strip() if company_name else raw,
        "website": website,
        "lookup_query": raw,
        "lookup_input_type": input_type,
    }


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
    user_id = request.state.user_id
    await _lookup_queue.put(
        {
            "user_id": user_id,
            "company_name": company_name,
            "website": parsed.get("website"),
            "lookup_query": parsed.get("lookup_query"),
            "lookup_input_type": parsed.get("lookup_input_type"),
            "lookup_id": lookup_id,
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
    agent = MetaAgent(user_id=request.state.user_id)
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
    hr = {
        "decision": decision,
        "notes": notes,
        "resolved_at": _now_iso(),
    }
    try:
        ok = storage.update_startup_partial(startup_id, {"human_resolution": hr})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve escalation: {e}") from e

    if not ok:
        raise HTTPException(status_code=404, detail="Startup not found")

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
