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
import env_config
import re
import time
from collections import OrderedDict
from uuid import uuid4
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from utils.timeutil import utcnow, ensure_aware
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
from fastapi.responses import JSONResponse, StreamingResponse

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
import event_bus
import metrics
from routers.deps import (
    enforce_rate_limits as _enforce_rate_limits,
    acquire_security_lock as _acquire_security_lock,
    release_security_lock as _release_security_lock,
    get_security_store as _get_security_store,
    client_host as _client_host,
    is_production_env as _is_production_env,
    now_iso as _now_iso,
    get_root as _get_root,
    get_portfolio_store as _get_portfolio_store,
    get_storage as _get_storage,
    require_supabase_for_thesis as _require_supabase_for_thesis,
    safe_table_execute as _safe_table_execute,
    read_json_list as _read_json_list,
    read_json_dict_file as _read_json_dict_file,
    get_pending_escalations as _get_pending_escalations,
    startup_name_index as _startup_name_index,
    get_system_health as _get_system_health,
    LOOKUP_MINUTE_POLICY as _LOOKUP_MINUTE_POLICY,
    LOOKUP_DAY_POLICY as _LOOKUP_DAY_POLICY,
    RESOLVE_MINUTE_POLICY as _RESOLVE_MINUTE_POLICY,
    AGENT_TRIGGER_POLICY as _AGENT_TRIGGER_POLICY,
    META_TRIGGER_POLICY as _META_TRIGGER_POLICY,
    SETTINGS_MUTATION_POLICY as _SETTINGS_MUTATION_POLICY,
    ADMIN_LOGIN_POLICY as _ADMIN_LOGIN_POLICY,
    ADMIN_OVERVIEW_POLICY as _ADMIN_OVERVIEW_POLICY,
)
from admin_auth import admin_token_ttl_seconds, issue_admin_token, validate_admin_secret, verify_admin_token
from admin_audit import record_admin_audit_event
from admin_service import build_admin_overview
from supabase_client import get_service_client
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
from services.scoring.presentation_layer import serialize_scoring_presentation
from portfolio.store import PortfolioStore
from portfolio.rejection import RejectionAnalyzer
from portfolio.cost_control import CostController
from jobs.handlers import build_handlers
from jobs.lookup_outcomes import (
    LookupAttemptOutcome,
    LookupOutcomeCorrupt,
    LookupOutcomeStoreUnavailable,
    latest_lookup_attempt,
    record_lookup_attempt,
)
from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    JobCancellationDisposition,
    JobType,
    PipelineCyclePayload,
)
from jobs.outbox import OutboxPublisher
from jobs.postgres import create_pool as create_durable_job_pool
from jobs.repository import DurableJobRepository
from jobs.worker import DurableJobWorker
from identity.repository import IdentityRepository
from evidence.repository import EvidenceRepository
from evaluation_v2.repository import EvaluationRepository
from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from decisions.repository import DecisionRepository
from monitoring.repository import MonitoringRepository
from fund_intelligence.repository import FundIntelligenceRepository
from outcomes.repository import ChannelOutcomeRepository
from pipeline_runner import (
    _rss_mb as _pipeline_rss_mb,
    reprocess_startups_missing_fund_thesis,
    run_one_pipeline_cycle,
    run_on_demand_lookup,
)
from pipeline_execution import LookupExecutionStatus, PipelineExecutionResult, PipelineExecutionState
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisMissingError,
    FundThesisQueryError,
    _bootstrap_default_thesis_or_raise,
    compute_thesis_alignment_stats,
    get_active_thesis,
    get_active_thesis_metadata,
    thesis_has_embeddings,
)
from fund_thesis_ops import sync_fund_config_to_active_thesis
from models import FundConfig, FundMemory, Startup, UserPreferences
from conviction_state import build_conviction_patch
from core import policy_resolver
from utils.scoring import compute_overall_score, enrich_scores, score_to_label
from utils.score_semantics import rubric_band_for_numeric
from utils.partner_codes import LEGACY_TO_RECOMMENDATION, recommendation_from_legacy

_agent_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_agent_worker_task: Optional[asyncio.Task] = None
_lookup_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
_lookup_worker_tasks: List[asyncio.Task] = []
_durable_job_pool: Any = None
_durable_job_repository: Optional[DurableJobRepository] = None
_durable_job_worker: Optional[DurableJobWorker] = None
_durable_outbox_publisher: Optional[OutboxPublisher] = None
_durable_job_error: Optional[str] = None
_durable_depth_snapshot: Dict[str, int] = {}
_durable_depth_sampler_task: Optional[asyncio.Task] = None
_cancelled_lookup_ids: OrderedDict[str, None] = OrderedDict()
_logger_agents = logging.getLogger("api.agents")
_logger_visible = logging.getLogger("uvicorn.error")

# SSE (GET /api/stream): keepalive cadence and a hard cap on concurrent streams
# per process so a flood of connections can't exhaust a small instance. When the
# cap is hit the client gets 503 and falls back to its polling cadence.
_SSE_KEEPALIVE_SECONDS = max(5, int(os.getenv("SSE_KEEPALIVE_SECONDS", "20") or "20"))
_SSE_MAX_CONNECTIONS = max(1, int(os.getenv("SSE_MAX_CONNECTIONS", "200") or "200"))

_LOOKUP_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,128}$")
# Lookup-input parsing lives in utils.lookup_input (pure, unit-tested). Re-exported
# here under the historical private names used by call sites and tests.
from utils.lookup_input import (  # noqa: E402
    parse_lookup_input as _parse_lookup_input,
    normalize_lookup_company_phrase as _normalize_lookup_company_phrase,
    is_lookup_command_only as _is_lookup_command_only,
)


def _lookup_cancel_key(user_id: str, lookup_id: str) -> str:
    return f"{user_id.strip()}:{lookup_id.strip()}"


def _is_lookup_cancelled(user_id: str, lookup_id: Optional[str]) -> bool:
    lid = (lookup_id or "").strip()
    return bool(user_id.strip() and lid and _lookup_cancel_key(user_id, lid) in _cancelled_lookup_ids)


def _mark_lookup_cancelled(user_id: str, lookup_id: str) -> None:
    key = _lookup_cancel_key(user_id, lookup_id)
    if isinstance(_cancelled_lookup_ids, OrderedDict):
        if key in _cancelled_lookup_ids:
            _cancelled_lookup_ids.move_to_end(key)
            return
        while len(_cancelled_lookup_ids) >= _CANCELLED_LOOKUP_MAX:
            _cancelled_lookup_ids.popitem(last=False)
        _cancelled_lookup_ids[key] = None
        return

    # Compatibility for tests or older in-process state initialized as a set.
    while len(_cancelled_lookup_ids) >= _CANCELLED_LOOKUP_MAX:
        _cancelled_lookup_ids.remove(next(iter(_cancelled_lookup_ids)))
    _cancelled_lookup_ids.add(key)


def _durable_jobs_required() -> bool:
    """Production storage accepts work only after PostgreSQL commits the job."""
    return env_config.use_supabase_storage()


def _durable_store_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "reason": "durable_job_store_unavailable",
        },
    )


def _job_response_fields(job: AgentJob) -> Dict[str, Any]:
    return {
        "status": "accepted",
        "job_id": job.job_id,
        "accepted_at": job.accepted_at.isoformat(),
        "pipeline_run_id": job.pipeline_run_id,
    }


def _lookup_idempotency_key(user_id: str, lookup_id: str) -> str:
    return f"lookup:{user_id}:{lookup_id}"


def _cycle_idempotency_key(user_id: str) -> str:
    interval = max(1, AGENT_LOOP_INTERVAL_SECONDS)
    return f"pipeline-cycle:{user_id}:{int(time.time() // interval)}"


async def _enqueue_pipeline_cycle(
    user_id: str,
    *,
    manual_one_shot: bool,
    source: str,
) -> AgentJob:
    repository = _durable_job_repository
    if repository is None:
        raise RuntimeError("durable_job_store_unavailable")
    job = AgentJob(
        user_id=user_id,
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key=_cycle_idempotency_key(user_id),
        payload=PipelineCyclePayload(
            user_id=user_id,
            manual_one_shot=manual_one_shot,
            source=source,
        ),
    )
    accepted = await repository.enqueue(job)
    if _durable_job_worker is not None:
        _durable_job_worker.notify()
    return accepted


async def _enqueue_company_lookup(
    user_id: str,
    *,
    company_name: str,
    website: Optional[str],
    lookup_query: Optional[str],
    lookup_input_type: Optional[str],
    lookup_id: str,
    additional_context: Optional[str],
    replace_startup_id: Optional[str] = None,
    resolution: Any = None,
) -> AgentJob:
    repository = _durable_job_repository
    if repository is None:
        raise RuntimeError("durable_job_store_unavailable")
    if resolution is None:
        serialized_resolution = None
    elif hasattr(resolution, "model_dump"):
        serialized_resolution = resolution.model_dump(mode="json")
    else:
        serialized_resolution = dict(resolution)
    job = AgentJob(
        user_id=user_id,
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key=_lookup_idempotency_key(user_id, lookup_id),
        payload=CompanyLookupPayload(
            user_id=user_id,
            company_name=company_name,
            website=website,
            lookup_query=lookup_query,
            lookup_input_type=lookup_input_type,
            lookup_id=lookup_id,
            additional_context=additional_context,
            replace_startup_id=replace_startup_id,
            resolution=serialized_resolution,
        ),
    )
    accepted = await repository.enqueue(job)
    if _durable_job_worker is not None:
        _durable_job_worker.notify()
    return accepted

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
# Always-on memory sampler (independent of agents). Logs process RSS on an interval so
# small-instance OOMs can be diagnosed: flat-but-high RSS => baseline/plan problem;
# steadily climbing RSS => leak in the request path. 0 disables.
RSS_SAMPLER_INTERVAL_SECONDS = max(0, int(os.getenv("RSS_SAMPLER_INTERVAL_SECONDS", "60")))
_rss_sampler_task: Optional[asyncio.Task] = None
# Event-loop lag sampler: measures asyncio scheduling delay so a blocked serving
# loop (sync I/O on the pipeline path) is visible in /metrics and logs. 0 disables.
LOOP_LAG_SAMPLER_INTERVAL_SECONDS = max(0, int(os.getenv("LOOP_LAG_SAMPLER_INTERVAL_SECONDS", "5")))
LOOP_LAG_WARN_SECONDS = float(os.getenv("LOOP_LAG_WARN_SECONDS", "0.25"))
_loop_lag_sampler_task: Optional[asyncio.Task] = None

# Cap glibc malloc arenas before the request threadpool grows, so freed JSON buffers
# aren't retained per-thread (primary driver of climb-and-plateau RSS). No-op off glibc.
from utils.malloc_tuning import cap_malloc_arenas, trim_malloc  # noqa: E402

cap_malloc_arenas()
_ADMIN_LOGIN_MAX_FAILURES = int(os.getenv("ADMIN_LOGIN_MAX_FAILURES", "5"))
_ADMIN_LOGIN_WINDOW_SECONDS = int(os.getenv("ADMIN_LOGIN_WINDOW_SECONDS", "300"))
_admin_login_attempts: Dict[str, List[float]] = {}

# Rate-limit policies + shared security/storage helpers now live in routers/deps.py

_AGENT_TRIGGER_LOCK_TTL_SECONDS = int(os.getenv("AGENT_TRIGGER_LOCK_TTL_SECONDS", "900"))
_LOOKUP_LOCK_TTL_SECONDS = int(os.getenv("LOOKUP_LOCK_TTL_SECONDS", "900"))
_CANCELLED_LOOKUP_MAX = max(1, int(os.getenv("CANCELLED_LOOKUP_MAX", "1000")))
_META_TRIGGER_LOCK_TTL_SECONDS = int(os.getenv("META_TRIGGER_LOCK_TTL_SECONDS", "900"))
_LOOKUP_RESOLUTION_TTL_SECONDS = max(
    30, min(int(os.getenv("LOOKUP_RESOLUTION_TTL_SECONDS", "300")), 900)
)
_LOOKUP_RESOLUTION_CACHE_MAX = max(
    16, min(int(os.getenv("LOOKUP_RESOLUTION_CACHE_MAX", "512")), 4096)
)
_lookup_resolution_cache: OrderedDict[str, tuple[str, float, Any]] = OrderedDict()
DEFAULT_STARTUPS_LIST_LIMIT = max(1, min(int(os.getenv("STARTUPS_LIST_DEFAULT_LIMIT", "250")), 500))
MAX_STARTUPS_LIST_LIMIT = max(
    DEFAULT_STARTUPS_LIST_LIMIT,
    min(int(os.getenv("STARTUPS_LIST_MAX_LIMIT", "500")), 1000),
)


def _prune_lookup_resolution_cache(now: Optional[float] = None) -> None:
    current = time.monotonic() if now is None else now
    expired = [
        token
        for token, (_, expires_at, _) in _lookup_resolution_cache.items()
        if expires_at <= current
    ]
    for token in expired:
        _lookup_resolution_cache.pop(token, None)
    while len(_lookup_resolution_cache) > _LOOKUP_RESOLUTION_CACHE_MAX:
        _lookup_resolution_cache.popitem(last=False)


def _cache_lookup_resolution(user_id: str, resolution: Any) -> str:
    _prune_lookup_resolution_cache()
    token = str(uuid4())
    _lookup_resolution_cache[token] = (
        user_id.strip(),
        time.monotonic() + _LOOKUP_RESOLUTION_TTL_SECONDS,
        resolution,
    )
    _prune_lookup_resolution_cache()
    return token


def _consume_lookup_resolution(user_id: str, token: Optional[str]) -> Any:
    normalized = (token or "").strip()
    if not normalized:
        return None
    _prune_lookup_resolution_cache()
    cached = _lookup_resolution_cache.get(normalized)
    if cached is None or cached[0] != user_id.strip():
        return None
    _lookup_resolution_cache.pop(normalized, None)
    return cached[2]


def _agent_status_for_execution(result: PipelineExecutionResult) -> str:
    if result.state in {
        PipelineExecutionState.BLOCKED,
        PipelineExecutionState.FAILED_STAGE,
    }:
        return "error"
    if result.state is PipelineExecutionState.SKIPPED:
        return "stopped"
    return "running"


async def _agent_worker() -> None:
    """Background worker: full scout/reviewer/partner cycles only (not on-demand lookup)."""
    if _agent_queue is None:
        return
    while True:
        try:
            job = await _agent_queue.get()
            user_id = str(job.get("user_id") or "").strip()
            try:
                result = await run_one_pipeline_cycle(
                    user_id,
                    manual_one_shot=bool(job.get("manual_one_shot")),
                    identity_repository=getattr(
                        app.state, "identity_repository", None
                    ),
                    fund_intelligence_repository=getattr(
                        app.state, "fund_intelligence_repository", None
                    ),
                )
                if not isinstance(result, PipelineExecutionResult):
                    raise RuntimeError("Pipeline runner returned an invalid execution result")
                await _update_agent_run_status(
                    user_id,
                    _agent_status_for_execution(result),
                    execution_result=result,
                )
            except Exception as e:
                _logger_agents.exception("Pipeline cycle error for user %s: %s", user_id[:12] if user_id else "?", e)
                await _update_agent_run_status(user_id, "error")
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
            lookup_id = str(job.get("lookup_id") or "").strip() or None
            legacy_job: Optional[AgentJob] = None
            try:
                resolution = job.get("resolution")
                if resolution is not None and hasattr(resolution, "model_dump"):
                    resolution = resolution.model_dump(mode="json")
                legacy_job_id = str(job.get("job_id") or uuid4())
                legacy_job = AgentJob(
                    job_id=legacy_job_id,
                    user_id=user_id,
                    job_type=JobType.COMPANY_LOOKUP,
                    idempotency_key=_lookup_idempotency_key(
                        user_id, lookup_id or legacy_job_id
                    ),
                    payload=CompanyLookupPayload(
                        user_id=user_id,
                        company_name=str(job.get("company_name") or "").strip(),
                        website=str(job.get("website") or "").strip() or None,
                        lookup_query=str(job.get("lookup_query") or "").strip() or None,
                        lookup_input_type=str(job.get("lookup_input_type") or "").strip() or None,
                        lookup_id=lookup_id,
                        additional_context=str(job.get("additional_context") or "").strip() or None,
                        replace_startup_id=str(job.get("replace_startup_id") or "").strip() or None,
                        resolution=resolution,
                    ),
                    status="running",
                    attempts=max(1, int(job.get("attempt") or 1)),
                    pipeline_run_id=str(job.get("pipeline_run_id") or uuid4()),
                )
                await _persist_legacy_lookup_attempt(
                    LookupAttemptOutcome.accepted_for_job(legacy_job)
                )
                if _is_lookup_cancelled(user_id, lookup_id):
                    await _persist_legacy_lookup_attempt(
                        LookupAttemptOutcome.cancelled_for_job(
                            legacy_job,
                            detail="The lookup was cancelled before execution started.",
                        )
                    )
                    _logger_agents.info(
                        "On-demand lookup skipped after cancellation for user %s lookup_id=%s",
                        user_id[:12] if user_id else "?",
                        lookup_id,
                    )
                    continue
                result = await run_on_demand_lookup(
                    user_id,
                    str(job.get("company_name") or ""),
                    website=str(job.get("website") or "").strip() or None,
                    lookup_query=str(job.get("lookup_query") or "").strip() or None,
                    lookup_input_type=str(job.get("lookup_input_type") or "").strip() or None,
                    lookup_id=lookup_id,
                    is_cancelled=lambda user_id=user_id, lookup_id=lookup_id: _is_lookup_cancelled(user_id, lookup_id),
                    additional_context=str(job.get("additional_context") or "").strip() or None,
                    replace_startup_id=str(job.get("replace_startup_id") or "").strip() or None,
                    resolution=job.get("resolution"),
                    pipeline_run_id=legacy_job.pipeline_run_id,
                    fund_intelligence_repository=getattr(
                        app.state, "fund_intelligence_repository", None
                    ),
                )
                if not isinstance(result, PipelineExecutionResult):
                    raise RuntimeError("Lookup runner returned an invalid execution result")
                await _persist_legacy_lookup_attempt(
                    LookupAttemptOutcome.from_pipeline_result(legacy_job, result)
                )
                if result.state is not PipelineExecutionState.COMPLETED:
                    _logger_agents.warning(
                        "On-demand lookup finished state=%s code=%s user=%s lookup_id=%s",
                        result.state.value,
                        result.code,
                        user_id[:12] if user_id else "?",
                        lookup_id,
                    )
            except Exception as e:
                _logger_agents.exception(
                    "On-demand lookup error for user %s: %s",
                    user_id[:12] if user_id else "?",
                    e,
                )
                if legacy_job is not None and not isinstance(e, LookupOutcomeStoreUnavailable):
                    try:
                        await _persist_legacy_lookup_attempt(
                            LookupAttemptOutcome.failed_for_job(
                                legacy_job,
                                detail="Lookup worker failed unexpectedly.",
                                recovery_action="Check worker availability and retry the lookup.",
                            )
                        )
                    except LookupOutcomeStoreUnavailable:
                        _logger_agents.exception(
                            "Lookup outcome store unavailable for user %s lookup_id=%s",
                            user_id[:12] if user_id else "?",
                            lookup_id,
                        )
            finally:
                _release_security_lock(str(job.get("lock_key") or "").strip() or None)
                _lookup_queue.task_done()
        except asyncio.CancelledError:
            break


async def _persist_legacy_lookup_attempt(
    outcome: LookupAttemptOutcome,
) -> LookupAttemptOutcome:
    """Central outcome service adapter for the compatibility queue worker."""
    return await asyncio.to_thread(record_lookup_attempt, outcome)


def _lookup_worker_count() -> int:
    """Match queue consumers to the lookup concurrency limit."""
    from pipeline_concurrency import max_concurrent_lookups

    return max_concurrent_lookups()


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


async def _update_agent_run_status(
    user_id: str,
    status: str,
    *,
    execution_result: Optional[PipelineExecutionResult] = None,
) -> None:
    """Best-effort: write agents_status (and last_started_at when running) into settings doc."""
    try:
        s = load_settings(user_id)
        ac = s.setdefault("agent_config", {})
        ac["agents_status"] = status
        if execution_result is not None:
            ac["agents_last_execution"] = execution_result.model_dump(
                mode="json", exclude_none=True
            )
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
                if _durable_jobs_required():
                    accepted_job = await _enqueue_pipeline_cycle(
                        user_id,
                        manual_one_shot=False,
                        source="scheduled_loop",
                    )
                    _logger_agents.info(
                        "[AGENT LOOP] Durable cycle accepted user=%s job_id=%s",
                        user_id[:12],
                        accepted_job.job_id,
                    )
                else:
                    # Local-only development seam. Production/Supabase execution
                    # is always committed to the durable repository first.
                    result = await run_one_pipeline_cycle(
                        user_id,
                        identity_repository=getattr(
                            app.state, "identity_repository", None
                        ),
                        fund_intelligence_repository=getattr(
                            app.state, "fund_intelligence_repository", None
                        ),
                    )
                    if not isinstance(result, PipelineExecutionResult):
                        raise RuntimeError(
                            "Pipeline runner returned an invalid execution result"
                        )
                    status = _agent_status_for_execution(result)
                    if status == "error":
                        await _update_agent_run_status(
                            user_id, "error", execution_result=result
                        )
                        _logger_agents.warning(
                            "[AGENT LOOP] Cycle state=%s code=%s user=%s",
                            result.state.value,
                            result.code,
                            user_id[:12],
                        )
                    else:
                        await _update_agent_run_status(
                            user_id, status, execution_result=result
                        )
                _logger_agents.info(
                    "[AGENT LOOP] Cycle dispatched user=%s duration_s=%.2f rss_mb_after=%.1f",
                    user_id[:12],
                    time.perf_counter() - cycle_started_at,
                    _pipeline_rss_mb(),
                )
                if _durable_jobs_required():
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


async def _rss_sampler() -> None:
    """
    Always-on background sampler: logs process RSS on a fixed interval, regardless of
    whether any agent loop is running. Lets us see the real memory curve on small Render
    instances where OOMs happen with agents off. Also logs active per-user loop count so a
    spike can be attributed to (or ruled out as) agent activity.
    """
    interval = RSS_SAMPLER_INTERVAL_SECONDS
    if interval <= 0:
        return
    # Baseline at boot — compare against the plan limit (e.g. 512 MB Starter).
    _logger_visible.info("[MEM] baseline rss_mb=%.1f at startup", _pipeline_rss_mb())
    try:
        while True:
            await asyncio.sleep(interval)
            active_loops = sum(1 for t in _per_user_loops.values() if not t.done())
            # Return free heap pages to the OS so RSS reflects live working set, not
            # retained arenas from transient JSON spikes.
            trim_malloc()
            _logger_visible.info(
                "[MEM] rss_mb=%.1f active_agent_loops=%d", _pipeline_rss_mb(), active_loops
            )
    except asyncio.CancelledError:
        raise


async def _event_loop_lag_sampler() -> None:
    """
    Samples asyncio scheduling delay: sleep(interval) should wake ~interval later;
    any excess is time the loop spent blocked (sync I/O, long computation). Exported
    as aethria_event_loop_lag_seconds and logged loudly above LOOP_LAG_WARN_SECONDS.
    """
    interval = LOOP_LAG_SAMPLER_INTERVAL_SECONDS
    if interval <= 0:
        return
    try:
        while True:
            expected = asyncio.get_running_loop().time() + interval
            await asyncio.sleep(interval)
            lag = asyncio.get_running_loop().time() - expected
            metrics.set_event_loop_lag(lag)
            if lag >= LOOP_LAG_WARN_SECONDS:
                _logger_visible.warning(
                    "[LOOP] event-loop lag %.3fs — sync I/O is blocking the serving loop",
                    lag,
                )
    except asyncio.CancelledError:
        raise


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
    use_supabase = env_config.use_supabase_storage()
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

async def _durable_depth_sampler() -> None:
    global _durable_depth_snapshot
    while True:
        try:
            if _durable_job_repository is not None:
                _durable_depth_snapshot = await _durable_job_repository.global_queue_depths()
                metrics.set_durable_depths(_durable_depth_snapshot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _logger_agents.warning("Durable job depth sampling failed: %s", type(exc).__name__)
        await asyncio.sleep(5)


async def _start_durable_job_services(app: FastAPI) -> None:
    global _durable_job_pool, _durable_job_repository, _durable_job_worker
    global _durable_outbox_publisher, _durable_job_error, _durable_depth_sampler_task

    try:
        _durable_job_pool = await create_durable_job_pool()
        _durable_job_repository = DurableJobRepository(_durable_job_pool)
        _durable_job_worker = DurableJobWorker(
            _durable_job_repository,
            handlers=build_handlers(_durable_job_repository),
            worker_id=f"api-{os.getpid()}-{uuid4().hex[:8]}",
            poll_interval_seconds=float(os.getenv("DURABLE_JOB_POLL_SECONDS", "2")),
            lease_seconds=int(os.getenv("DURABLE_JOB_LEASE_SECONDS", "90")),
            heartbeat_seconds=float(os.getenv("DURABLE_JOB_HEARTBEAT_SECONDS", "20")),
            global_concurrency=int(os.getenv("DURABLE_JOB_GLOBAL_CONCURRENCY", "2")),
            per_tenant_concurrency=int(os.getenv("DURABLE_JOB_TENANT_CONCURRENCY", "1")),
        )
        _durable_outbox_publisher = OutboxPublisher(
            _durable_job_repository,
            poll_interval_seconds=float(os.getenv("DURABLE_OUTBOX_POLL_SECONDS", "2")),
        )
        await _durable_job_worker.start()
        await _durable_outbox_publisher.start()
        _durable_depth_sampler_task = asyncio.create_task(_durable_depth_sampler())
        _durable_job_error = None
        _logger_agents.info("Durable agent job worker and outbox publisher started")
    except Exception as exc:
        error_name = type(exc).__name__
        _logger_agents.error(
            "Durable job store unavailable; accepted-work endpoints will fail closed: %s",
            error_name,
        )
        try:
            await _stop_durable_job_services(app)
        except Exception as cleanup_exc:
            _logger_agents.warning(
                "Partial durable service cleanup failed: %s",
                type(cleanup_exc).__name__,
            )
        _durable_job_error = error_name
    app.state.durable_job_repository = _durable_job_repository
    app.state.durable_job_error = _durable_job_error
    app.state.identity_repository = (
        IdentityRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.evidence_repository = (
        EvidenceRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.evaluation_repository = (
        EvaluationRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.decision_repository = (
        DecisionRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.monitoring_repository = (
        MonitoringRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.fund_intelligence_repository = (
        FundIntelligenceRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )
    app.state.channel_outcome_repository = (
        ChannelOutcomeRepository(_durable_job_pool) if _durable_job_pool is not None else None
    )


async def _stop_durable_job_services(app: FastAPI) -> None:
    global _durable_job_pool, _durable_job_repository, _durable_job_worker
    global _durable_outbox_publisher, _durable_depth_sampler_task

    if _durable_depth_sampler_task is not None:
        _durable_depth_sampler_task.cancel()
        try:
            await _durable_depth_sampler_task
        except asyncio.CancelledError:
            pass
        _durable_depth_sampler_task = None
    if _durable_job_worker is not None:
        await _durable_job_worker.stop()
    if _durable_outbox_publisher is not None:
        await _durable_outbox_publisher.stop()
    if _durable_job_pool is not None:
        await _durable_job_pool.close()
    _durable_job_pool = None
    _durable_job_repository = None
    _durable_job_worker = None
    _durable_outbox_publisher = None
    app.state.durable_job_repository = None
    app.state.identity_repository = None
    app.state.evidence_repository = None
    app.state.evaluation_repository = None
    app.state.decision_repository = None
    app.state.monitoring_repository = None
    app.state.fund_intelligence_repository = None
    app.state.channel_outcome_repository = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _agent_queue, _agent_worker_task, _lookup_queue, _lookup_worker_tasks, _loops_lock
    global _rss_sampler_task
    _loops_lock = asyncio.Lock()
    if _durable_jobs_required():
        _agent_queue = None
        _lookup_queue = None
        _agent_worker_task = None
        _lookup_worker_tasks = []
    else:
        _agent_queue = asyncio.Queue()
        _lookup_queue = asyncio.Queue()
        _agent_worker_task = asyncio.create_task(_agent_worker())
        _lookup_worker_tasks = [
            asyncio.create_task(_lookup_worker()) for _ in range(_lookup_worker_count())
        ]
    _rss_sampler_task = asyncio.create_task(_rss_sampler())
    global _loop_lag_sampler_task
    _loop_lag_sampler_task = asyncio.create_task(_event_loop_lag_sampler())
    if _lookup_worker_tasks:
        _logger_agents.info(
            "Local development agent worker + %d lookup workers started",
            len(_lookup_worker_tasks),
        )
    # Surface unapplied migrations loudly at startup. The storage write path
    # tolerates missing columns by dropping fields and retrying — convenient, but
    # it hides drift. This makes it a single visible signal instead.
    if os.getenv("USE_SUPABASE_STORAGE") == "1":
        try:
            from supabase_client import get_service_client
            from supabase_storage import detect_schema_drift

            drift = detect_schema_drift(get_service_client())
            if drift:
                _logger_agents.warning(
                    "SCHEMA DRIFT: startups table missing column(s) %s — apply pending "
                    "migrations in supabase/migrations/; affected fields are silently "
                    "dropped on write until applied.",
                    ", ".join(drift),
                )
        except Exception as e:  # pragma: no cover - never block startup
            _logger_agents.warning("schema drift check skipped: %s", e)
    # Multi-instance safety: production must explicitly choose a shared event
    # backplane, or explicitly acknowledge a single-instance deployment.
    production = _is_production_env()
    allow_process_local = os.getenv("ALLOW_PROCESS_LOCAL_STATE", "false").lower() in ("1", "true", "yes")
    if production and not event_bus.backplane_enabled() and not allow_process_local:
        raise RuntimeError(
            "Production requires EVENT_BUS_BACKPLANE=postgres with a database DSN, "
            "or ALLOW_PROCESS_LOCAL_STATE=true for a documented single-instance deployment"
        )
    # Opt-in multi-instance SSE backplane.
    if event_bus.backplane_enabled():
        try:
            active = await event_bus.start_backplane()
            if production and not active and not allow_process_local:
                raise RuntimeError("Postgres event backplane could not start in production")
        except Exception as e:  # pragma: no cover - never block startup
            if production and not allow_process_local:
                raise
            _logger_agents.warning("event_bus backplane failed to start: %s", e)
    if _durable_jobs_required():
        await _start_durable_job_services(app)
    else:
        app.state.durable_job_repository = None
        app.state.durable_job_error = None
        app.state.identity_repository = None
        app.state.evidence_repository = None
        app.state.evaluation_repository = None
        app.state.decision_repository = None
        app.state.monitoring_repository = None
        app.state.fund_intelligence_repository = None
        app.state.channel_outcome_repository = None
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
    await _stop_durable_job_services(app)
    await event_bus.stop_backplane()
    # Cancel queue workers + memory/loop-lag samplers
    for t in (*_lookup_worker_tasks, _agent_worker_task, _rss_sampler_task, _loop_lag_sampler_task):
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    _logger_agents.info("Pipeline job services stopped")


app = FastAPI(title="Aethria API", lifespan=_lifespan)


@app.middleware("http")
async def request_metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # Route templates are available after routing; fall back to a bounded
        # endpoint family so startup IDs do not create unbounded metric labels.
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        path = re.sub(r"\{[^}]*id[^}]*\}", ":id", str(path), flags=re.IGNORECASE)
        path = re.sub(r"/[0-9a-fA-F-]{16,}", "/:id", str(path))
        metrics.observe_api_request(
            request.method,
            path,
            status,
            time.perf_counter() - started,
        )

# Routers split out of this module (see routers/). The Clerk auth middleware
# below is app-level and applies to these routes too.
from routers import meta as _meta_router  # noqa: E402

app.include_router(_meta_router.router)
from routers import fund_thesis as _fund_thesis_router  # noqa: E402

app.include_router(_fund_thesis_router.router)
from routers import analytics as _analytics_router  # noqa: E402

app.include_router(_analytics_router.router)
from routers import jobs as _jobs_router  # noqa: E402

app.include_router(_jobs_router.router)
from routers import identity as _identity_router  # noqa: E402

app.include_router(_identity_router.router)
from routers import evidence as _evidence_router  # noqa: E402

app.include_router(_evidence_router.router)
from routers import evaluations as _evaluations_router  # noqa: E402

app.include_router(_evaluations_router.router)
from routers import decisions as _decisions_router  # noqa: E402

app.include_router(_decisions_router.router)
from routers import monitoring as _monitoring_router  # noqa: E402

app.include_router(_monitoring_router.router)
from routers import fund_intelligence as _fund_intelligence_router  # noqa: E402

app.include_router(_fund_intelligence_router.router)
from routers import channels_outcomes as _channels_outcomes_router  # noqa: E402

app.include_router(_channels_outcomes_router.router)

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


def _admin_dashboard_enabled() -> bool:
    raw = os.getenv("ADMIN_DASHBOARD_ENABLED")
    if _is_production_env():
        return str(raw or "").lower() in ("1", "true", "yes")
    return str(raw or "true").lower() not in ("0", "false", "no")


# Public paths that skip Clerk JWT auth
_PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/redoc/", "/openapi.json/"}
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
    # verify_clerk_token can do a blocking JWKS HTTP fetch on a cold key
    # cache — keep it off the serving event loop.
    user_id = await asyncio.to_thread(verify_clerk_token, token) if token else None
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
            if "scout_grounded_citations_enabled" in ac and not isinstance(ac["scout_grounded_citations_enabled"], bool):
                errors.append("agent_config.scout_grounded_citations_enabled must be a boolean")
            if "scout_fail_closed_on_empty_retrieval" in ac and not isinstance(ac["scout_fail_closed_on_empty_retrieval"], bool):
                errors.append("agent_config.scout_fail_closed_on_empty_retrieval must be a boolean")
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
            "location": scout.get("location"),
            "est_tam": scout.get("est_tam"),
            "founder_names": scout.get("founder_names") or [],
            "references": scout.get("references") or [],
            "source_evidence": scout.get("source_evidence") or [],
            "operator_context": scout.get("operator_context"),
            "origin_type": scout.get("origin_type"),
            "lookup_input_type": scout.get("lookup_input_type"),
            "lookup_query": scout.get("lookup_query"),
            "lookup_website": scout.get("lookup_website"),
            "lookup_id": scout.get("lookup_id"),
            "resolution_status": scout.get("resolution_status"),
            "company_resolution": scout.get("company_resolution")
            if isinstance(scout.get("company_resolution"), dict)
            else None,
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
            "location": row.get("list_location") or "",
            "why_now": "",
            "confidence": conf_f,
            "origin_type": row.get("list_origin_type"),
            "lookup_id": row.get("list_lookup_id"),
            "lookup_query": row.get("list_lookup_query"),
            "lookup_website": row.get("list_lookup_website"),
            "resolution_status": row.get("list_resolution_status"),
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
        # Heavy resolver payload stays out of the list view; resolution_status remains.
        "company_resolution",
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
        # Projection returned None -> the query failed (e.g. transient EAGAIN). Do NOT
        # fall back to a full-row select("*") fetch: this endpoint is polled heavily
        # (~1/s during a lookup), and pulling full memo/review/scout/partner JSON for
        # every row on each poll spikes egress and RSS until the instance OOMs. Signal a
        # transient failure so the client keeps its last data and retries the next poll.
        raise HTTPException(
            status_code=503,
            detail="Startup list temporarily unavailable; retry shortly.",
            headers={"Retry-After": "2"},
        )
    raw_list = storage.get_all()
    full = [_backend_to_frontend(r, last_seen_at=last_seen_at) for r in raw_list]
    return [_thin_list_from_full_frontend(x) for x in full]


async def _sse_event_source(queue, *, keepalive_seconds, on_close=None):
    """Yield SSE frames for one subscriber queue.

    Emits a ``: connected`` comment first (flushes headers / primes proxies),
    then an immediate ``startups_changed`` "hello" nudge so the client refetches
    the moment the stream goes healthy. The bus does not replay events published
    before ``subscribe()``, and the client relaxes its poll to a slow backstop
    once connected — so without this nudge any write that lands in the
    connect-gap (e.g. the first pipeline batch right after login) wouldn't be
    seen until that backstop fires. The hello nudge closes that race and also
    covers every reconnect. After it, a ``data:`` frame is emitted per published
    event, with a ``: keepalive`` comment whenever the connection sits idle
    longer than ``keepalive_seconds``. The keepalive doubles as disconnect
    detection: once the client is gone the yield raises, the generator is closed,
    and ``on_close`` (unsubscribe) runs.
    """
    try:
        yield ": connected\n\n"
        # Hello nudge: reconcile anything written before this subscription
        # (the bus has no replay) and any missed event since the last connect.
        yield f"data: {json.dumps({'type': 'startups_changed', 'reason': 'stream_connected'})}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        if on_close is not None:
            on_close()


@app.get("/api/stream")
async def event_stream(request: Request):
    """
    Server-Sent Events: push lightweight "startups_changed" nudges so the
    frontend can refetch the deal-flow the moment a pipeline stage writes new
    data, instead of waiting for its next poll tick.

    The payload is intentionally tiny (a nudge, not the data) — the client
    reacts by invalidating its TanStack query and refetching through the normal
    typed REST client, so this stream never duplicates startup serialization.

    Auth uses the standard Clerk path: the frontend consumes this with `fetch`
    (not the native EventSource), so it sends the usual `Authorization: Bearer`
    header and `clerk_auth_middleware` has already set `request.state.user_id`.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        # Should be unreachable behind the auth middleware, but never leak a
        # stream without a tenant.
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token")

    if event_bus.total_subscribers() >= _SSE_MAX_CONNECTIONS:
        raise HTTPException(
            status_code=503,
            detail="Too many active streams; retry shortly (polling continues meanwhile).",
            headers={"Retry-After": "30"},
        )

    queue = event_bus.subscribe(user_id)
    source = _sse_event_source(
        queue,
        keepalive_seconds=_SSE_KEEPALIVE_SECONDS,
        on_close=lambda: event_bus.unsubscribe(user_id, queue),
    )
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        # Disable nginx-style proxy buffering so events flush immediately.
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(source, media_type="text/event-stream", headers=headers)


@app.get("/api/startups/lookup-status")
def lookup_job_status(request: Request, lookup_id: str = ""):
    """
    Return the lossless lookup execution state and actionable terminal metadata.
    """
    uid = request.state.user_id
    raw = (lookup_id or "").strip()
    if not raw or not _LOOKUP_ID_RE.match(raw):
        raise HTTPException(
            status_code=422,
            detail="lookup_id query parameter must be 8-128 characters [a-zA-Z0-9_-]",
        )
    try:
        outcome = latest_lookup_attempt(uid, raw)
    except LookupOutcomeStoreUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "reason": "lookup_outcome_store_unavailable",
            },
        ) from exc
    except LookupOutcomeCorrupt as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "reason": "lookup_outcome_contract_invalid",
            },
        ) from exc
    if outcome is None:
        return {
            "lookup_id": raw,
            "failed": False,
            "terminal": False,
            "status": LookupExecutionStatus.PENDING.value,
        }
    payload = {
        "lookup_id": raw,
        "job_id": outcome.job_id,
        "pipeline_run_id": outcome.pipeline_run_id,
        "attempt": outcome.attempt,
        "disposition": outcome.disposition.value,
        "recorded_at": outcome.recorded_at.isoformat(),
        "failed": outcome.failed,
        "terminal": outcome.terminal,
        "status": outcome.status.value,
    }
    if outcome.startup_id:
        payload["startup_id"] = outcome.startup_id
    if outcome.code:
        payload["code"] = outcome.code
    if outcome.failed_stage:
        payload["failed_stage"] = outcome.failed_stage
    if outcome.detail:
        payload["detail"] = outcome.detail
        payload["message"] = outcome.detail
    if outcome.recovery_action:
        payload["recovery_action"] = outcome.recovery_action
    return payload


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
    # Several sequential sync Supabase round trips: keep them off the event loop.
    return await asyncio.to_thread(_acknowledge_startup_sync, request, startup_id)


def _acknowledge_startup_sync(request: Request, startup_id: str):
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
                "pipeline_status": state_status,
                "error": err_from_row,
            }

        if state_status and state_status != "ready":
            return {
                "status": "generating",
                "memo": None,
                "partial": _memo_partial_payload(startup) if startup.scout_info else None,
                "pipeline_run_id": pr_str,
                "pipeline_status": state_status,
                "error": None,
            }

        if md:
            return {
                "status": "ready",
                "memo": md,
                "partial": None,
                "pipeline_run_id": pr_str,
                "pipeline_status": state_status,
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
                "pipeline_status": state_status,
                "error": None,
            }

        return {
            "status": "generating",
            "memo": None,
            "partial": _memo_partial_payload(startup) if startup.scout_info else None,
            "pipeline_run_id": pr_str,
            "pipeline_status": state_status,
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
        "pipeline_status": None,
        "error": None,
    }


@app.get("/health")
def health():
    """Lightweight health check (public; no auth). Pending escalations require auth via /api/settings."""
    return {"status": "ok"}


@app.get("/api/system/status")
async def system_status(request: Request):
    """Authenticated execution-plane status without secrets or raw exceptions."""
    user_id = require_authenticated_user(request)
    counts: Dict[str, int]
    if _durable_job_repository is not None:
        try:
            counts = await _durable_job_repository.tenant_queue_depths(user_id=user_id)
        except Exception as exc:
            _logger_agents.warning(
                "Durable system status read failed: %s", type(exc).__name__
            )
            counts = {}
    else:
        counts = {
            "pipeline_cycle:queued": _agent_queue.qsize() if _agent_queue is not None else 0,
            "company_lookup:queued": _lookup_queue.qsize() if _lookup_queue is not None else 0,
            "outbox:pending": 0,
        }
    return {
        "status": "ok",
        "durable_jobs": {
            "required": _durable_jobs_required(),
            "ready": _durable_job_repository is not None,
            "error": _durable_job_error if _durable_jobs_required() else None,
            "counts": counts,
        },
    }


@app.get("/metrics")
def prometheus_metrics(request: Request):
    """Prometheus exposition: pipeline throughput/latency, lookup outcomes, queue
    depth, SSE subscribers, persistent loops.

    Bypasses Clerk auth (it's a machine endpoint scraped by Prometheus, not the
    SPA). When METRICS_TOKEN is set it must be presented as a Bearer token.
    METRICS_ENABLED=0 hides it. In production the endpoint is CLOSED BY DEFAULT:
    if METRICS_TOKEN is unset it returns 404, so a public ingress can't scrape
    operational data unless an operator opts in by setting the token. Outside
    production it stays open for local Prometheus/dev convenience.
    """
    if not env_config.get_bool("METRICS_ENABLED"):
        raise HTTPException(status_code=404, detail="Not found")
    token = env_config.get_str("METRICS_TOKEN")
    if not token and _is_production_env():
        # Fail closed in prod rather than expose queue depths / loop counts publicly.
        raise HTTPException(status_code=404, detail="Not found")
    if token:
        auth = request.headers.get("Authorization", "")
        presented = auth[7:].strip() if auth.startswith("Bearer ") else ""
        if presented != token:
            raise HTTPException(status_code=401, detail="Missing or invalid metrics token")
    if _durable_job_repository is not None:
        agent_depth = sum(
            count
            for key, count in _durable_depth_snapshot.items()
            if key.startswith("pipeline_cycle:")
        )
        lookup_depth = sum(
            count
            for key, count in _durable_depth_snapshot.items()
            if key.startswith("company_lookup:")
        )
    else:
        agent_depth = _agent_queue.qsize() if _agent_queue is not None else 0
        lookup_depth = _lookup_queue.qsize() if _lookup_queue is not None else 0
    body = metrics.render(
        sse_subscribers=event_bus.total_subscribers(),
        agent_queue_depth=agent_depth,
        lookup_queue_depth=lookup_depth,
        persistent_loops=len(_per_user_loops),
    )
    from fastapi.responses import Response

    return Response(content=body, media_type=metrics.CONTENT_TYPE_LATEST)


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
    # Sync Supabase reads/writes (+ optional OpenAI thesis sync) off the event loop.
    current = await asyncio.to_thread(_patch_settings_sync, user_id, body)

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


def _patch_settings_sync(user_id: str, body: dict) -> dict:
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
async def publish_settings_policy(request: Request, body: dict | None = None):
    """Publish the current or supplied fund_config draft as an immutable scoring policy version."""
    user_id = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited is not None:
        return limited
    payload = body if isinstance(body, dict) else {}
    fund_config = payload.get("fund_config") if isinstance(payload.get("fund_config"), dict) else None
    try:
        if fund_config is None:
            settings = await asyncio.to_thread(load_settings, user_id, use_cache=False)
            fund_config = (
                settings.get("fund_config")
                if isinstance(settings.get("fund_config"), dict)
                else {}
            )
        compiled = await asyncio.to_thread(
            compile_policy_from_fund_config,
            fund_config,
            require_publish_ready=True,
        )
        repository = getattr(app.state, "fund_intelligence_repository", None)
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="Governed policy store unavailable",
            )
        version = await repository.publish_settings_policy(
            user_id=user_id,
            actor_id=user_id,
            fund_config=fund_config,
            policy_hash=compiled["policy_hash"],
        )
    except PolicyValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Policy validation failed", "errors": exc.errors},
        ) from exc
    return {
        "policy": {
            **compiled,
            "policy_version_id": version["governed_policy_version_id"],
            "published_at": version.get("published_at"),
            "authoritative_store": "governed_policy_versions",
            "legacy_projection": "pending",
        }
    }


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


@app.get("/api/agents/status")
async def agents_status(request: Request):
    """
    Return whether the server is configured for agents (for debugging deployment).
    Does not expose secrets; use to see why agents might be skipped on e.g. Render.
    Includes fund thesis readiness for the authenticated user.
    """
    use_supabase = env_config.use_supabase_storage()
    supabase_configured = bool(
        use_supabase
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    openai_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    # Sync Supabase reads (thesis + settings) off the event loop.
    user_id = request.state.user_id
    (
        thesis_ready,
        mandate_published,
        active_thesis_version_id,
        thesis_error,
        user_agents_enabled,
    ) = await asyncio.to_thread(_agents_status_reads_sync, user_id, supabase_configured)
    durable_counts: Dict[str, int] = {}
    if _durable_job_repository is not None:
        try:
            durable_counts = await _durable_job_repository.tenant_queue_depths(
                user_id=user_id
            )
        except Exception:
            durable_counts = {}
    worker_ready = (
        _durable_job_repository is not None
        if _durable_jobs_required()
        else _agent_queue is not None
    )
    lookup_worker_ready = (
        _durable_job_repository is not None
        if _durable_jobs_required()
        else _lookup_queue is not None
    )
    agents_infrastructure_ready = bool(
        supabase_configured and openai_configured and worker_ready
    )
    lookup_infrastructure_ready = bool(
        supabase_configured and openai_configured and lookup_worker_ready
    )
    execution_prerequisites_ready = False
    published_policy_ready = False
    active_policy_version_id: Optional[str] = None
    execution_prerequisite_code: Optional[str] = None
    execution_prerequisite_detail: Optional[str] = None
    execution_prerequisite_recovery_action: Optional[str] = None
    if supabase_configured:
        try:
            prerequisites = await load_evaluation_prerequisites(
                user_id=user_id,
                fund_intelligence_repository=getattr(
                    app.state, "fund_intelligence_repository", None
                ),
            )
        except EvaluationPrerequisiteError as exc:
            execution_prerequisite_code = exc.code
            execution_prerequisite_detail = exc.detail
            execution_prerequisite_recovery_action = exc.recovery_action
        except Exception:
            execution_prerequisite_code = "prerequisite_unavailable"
            execution_prerequisite_detail = (
                "The execution prerequisites could not be loaded."
            )
            execution_prerequisite_recovery_action = (
                "Retry after the thesis and published-policy stores are available."
            )
        else:
            execution_prerequisites_ready = True
            published_policy_ready = True
            thesis_ready = True
            active_thesis_version_id = prerequisites.thesis_version_id
            active_policy_version_id = prerequisites.policy.policy_version_id
            thesis_error = None
    else:
        execution_prerequisite_code = "infrastructure_unavailable"
        execution_prerequisite_detail = (
            "Supabase is required to load the active thesis and published policy."
        )
        execution_prerequisite_recovery_action = (
            "Configure Supabase before dispatching evaluation work."
        )
    return {
        "worker_ready": worker_ready,
        "lookup_worker_ready": lookup_worker_ready,
        "agents_infrastructure_ready": agents_infrastructure_ready,
        "lookup_infrastructure_ready": lookup_infrastructure_ready,
        "agent_queue_size": (
            sum(v for k, v in durable_counts.items() if k.startswith("pipeline_cycle:"))
            if _durable_jobs_required()
            else (_agent_queue.qsize() if _agent_queue is not None else None)
        ),
        "lookup_queue_size": (
            sum(v for k, v in durable_counts.items() if k.startswith("company_lookup:"))
            if _durable_jobs_required()
            else (_lookup_queue.qsize() if _lookup_queue is not None else None)
        ),
        "durable_jobs_required": _durable_jobs_required(),
        "durable_jobs_ready": _durable_job_repository is not None,
        "durable_job_error": _durable_job_error if _durable_jobs_required() else None,
        "durable_job_counts": durable_counts,
        "supabase_configured": supabase_configured,
        "openai_configured": openai_configured,
        "user_agents_enabled": user_agents_enabled,
        "agents_will_run": (
            agents_infrastructure_ready
            and user_agents_enabled
            and execution_prerequisites_ready
        ),
        "lookup_will_run": (
            lookup_infrastructure_ready
            and execution_prerequisites_ready
        ),
        "execution_prerequisites_ready": execution_prerequisites_ready,
        "execution_prerequisite_code": execution_prerequisite_code,
        "execution_prerequisite_detail": execution_prerequisite_detail,
        "execution_prerequisite_recovery_action": (
            execution_prerequisite_recovery_action
        ),
        "thesis_ready": thesis_ready,
        "mandate_published": mandate_published,
        "active_thesis_version_id": active_thesis_version_id,
        "thesis_error": thesis_error,
        "published_policy_ready": published_policy_ready,
        "active_policy_version_id": active_policy_version_id,
    }


def _agents_status_reads_sync(user_id: str, supabase_configured: bool):
    thesis_ready = False
    mandate_published = False
    active_thesis_version_id: Optional[str] = None
    thesis_error: Optional[str] = None
    if supabase_configured:
        try:
            t = get_active_thesis(get_service_client(), user_id)
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
    user_agents_enabled = False
    try:
        user_settings = load_settings(user_id)
        ac = user_settings.get("agent_config") or {}
        user_agents_enabled = bool(
            ac.get("scouts_enabled", False)
            or ac.get("reviewers_enabled", False)
            or ac.get("partners_enabled", False)
        )
    except Exception as e:
        _logger_agents.debug("Could not compute user_agents_enabled: %s", e)
    return thesis_ready, mandate_published, active_thesis_version_id, thesis_error, user_agents_enabled


@app.post("/api/agents/trigger")
async def trigger_agents(request: Request):
    """
    Trigger agent execution for the current user.
    When Ops/Agents is on, start or reuse the user's persistent loop.
    When Ops/Agents is off, enqueue a manual one-shot cycle.
    """
    user_id = require_authenticated_user(request)
    use_supabase = env_config.use_supabase_storage()
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
        # This endpoint fires on every login: keep its sync Supabase reads off
        # the event loop so they can't stall concurrent first-paint fetches.
        settings = await asyncio.to_thread(load_settings, user_id)
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
    if agents_enabled and _is_user_loop_alive(user_id) and not _durable_jobs_required():
        _logger_agents.info(
            "trigger_agents ignored user=%s reason=loop_already_running",
            user_id[:12],
        )
        _logger_visible.info("[AGENT LOOP] Trigger ignored because loop already running for user %s", user_id[:12])
        return JSONResponse(
            status_code=202,
            content={"status": "loop_running", "user_id": user_id},
        )
    if agents_enabled and _loops_lock is None and not _is_user_loop_alive(user_id):
        _logger_agents.warning(
            "trigger_agents unavailable user=%s reason=loop_registry_not_ready",
            user_id[:12],
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "loop_registry_not_ready"},
        )
    if _durable_jobs_required() and _durable_job_repository is None:
        _logger_agents.warning(
            "trigger_agents unavailable user=%s reason=durable_job_store_unavailable",
            user_id[:12],
        )
        return _durable_store_unavailable()
    if not _durable_jobs_required() and not agents_enabled and _agent_queue is None:
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
        svc = await asyncio.to_thread(get_service_client)
        thesis = await asyncio.to_thread(get_active_thesis, svc, user_id)
        if thesis is None:
            await asyncio.to_thread(_bootstrap_default_thesis_or_raise, svc, user_id)
            thesis = await asyncio.to_thread(get_active_thesis, svc, user_id)
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
    if _durable_jobs_required():
        try:
            accepted_job = await _enqueue_pipeline_cycle(
                user_id,
                manual_one_shot=not agents_enabled,
                source="login_trigger" if agents_enabled else "manual_one_shot",
            )
        except Exception as exc:
            _logger_agents.error(
                "trigger_agents durable enqueue failed user=%s error=%s",
                user_id[:12],
                type(exc).__name__,
            )
            _release_security_lock(lock_key)
            return _durable_store_unavailable()
        _release_security_lock(lock_key)
        loop_status = None
        if agents_enabled:
            started = await _ensure_user_loop(user_id)
            loop_status = "loop_started" if started else "loop_running"
        content = {
            **_job_response_fields(accepted_job),
            "user_id": user_id,
            "loop_status": loop_status,
        }
        _logger_agents.info(
            "trigger_agents accepted durable cycle user=%s job_id=%s",
            user_id[:12],
            accepted_job.job_id,
        )
        return JSONResponse(status_code=202, content=content)

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
    except Exception as e:
        _logger_agents.debug("Request body not JSON; using empty body: %s", e)

    enabled = bool(body.get("enabled", False))

    try:
        s = await asyncio.to_thread(load_settings, user_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not load settings: {e}") from e

    ac = s.setdefault("agent_config", {})
    has_enabled_stage = bool(
        ac.get("scouts_enabled")
        or ac.get("reviewers_enabled")
        or ac.get("partners_enabled")
    )
    invalid_enable = enabled and not has_enabled_stage
    if invalid_enable:
        ac["agents_status"] = "stopped"
    elif enabled:
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
        await asyncio.to_thread(save_settings, s, user_id)
    except Exception as e:
        _logger_agents.warning("toggle_agents: could not save settings for user %s: %s", user_id[:12], e)
        raise HTTPException(status_code=503, detail="Could not save agent state") from e

    if invalid_enable:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Enable at least one agent stage before starting the agent loop.",
                "enabled": False,
                "user_id": user_id,
            },
        )
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
def get_loop_status(request: Request):
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
    # Optional operator-supplied background (private traction/team/funding facts)
    # forwarded to the scout to fill "missing evidence" gaps.
    additional_context = str(body.get("additional_context") or "").strip() or None
    if additional_context and len(additional_context) > 2000:
        raise HTTPException(status_code=422, detail="additional_context is too long (max 2000 chars)")
    user_id = require_authenticated_user(request)
    lookup_id = _coerce_lookup_id(body.get("lookup_id"))
    parsed = _parse_lookup_input(lookup_input)
    company_name = str(parsed.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Could not derive company name from lookup_input")
    if _durable_jobs_required() and _durable_job_repository is None:
        return _durable_store_unavailable()
    if not _durable_jobs_required() and _lookup_queue is None:
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
    resolution = _consume_lookup_resolution(
        user_id,
        str(body.get("resolution_token") or "").strip() or None,
    )
    if _durable_jobs_required():
        try:
            accepted_job = await _enqueue_company_lookup(
                user_id,
                company_name=company_name,
                website=parsed.get("website"),
                lookup_query=parsed.get("lookup_query"),
                lookup_input_type=parsed.get("lookup_input_type"),
                lookup_id=lookup_id,
                additional_context=additional_context,
                resolution=resolution,
            )
        except Exception as exc:
            _logger_agents.error(
                "lookup durable enqueue failed user=%s error=%s",
                user_id[:12],
                type(exc).__name__,
            )
            _release_security_lock(lock_key)
            return _durable_store_unavailable()
        _release_security_lock(lock_key)
        job_fields = _job_response_fields(accepted_job)
    else:
        await _lookup_queue.put(
            {
                "user_id": user_id,
                "company_name": company_name,
                "website": parsed.get("website"),
                "lookup_query": parsed.get("lookup_query"),
                "lookup_input_type": parsed.get("lookup_input_type"),
                "lookup_id": lookup_id,
                "lock_key": lock_key,
                "additional_context": additional_context,
                "resolution": resolution,
            }
        )
        job_fields = {"status": "queued"}
    return JSONResponse(
        status_code=202,
        content={
            **job_fields,
            "user_id": user_id,
            "lookup_id": lookup_id,
            "lookup_input": lookup_input,
            "company_name": company_name,
            "website": parsed.get("website"),
            "lookup_input_type": parsed.get("lookup_input_type"),
            "mode": "on_demand_lookup",
        },
    )


_AMBIGUOUS_MIN_CONFIDENCE = 0.7


def _resolve_status_for(resolution, website_hint: Optional[str]) -> str:
    """Classify a resolution for the dispatch picker: resolved | ambiguous | not_found."""
    candidates = list(getattr(resolution, "candidates", []) or [])
    if resolution.resolution_status == "NOT_FOUND" or not candidates:
        return "not_found"
    if (website_hint or "").strip():
        return "resolved"
    strong = sum(1 for c in candidates if c.confidence >= _AMBIGUOUS_MIN_CONFIDENCE)
    if strong >= 2:
        return "ambiguous"
    return "resolved"


@app.post("/api/startups/{startup_id}/rerun")
async def rerun_startup_lookup(request: Request, startup_id: str, body: Dict[str, Any]):
    """
    Re-review an EXISTING startup with operator-supplied context (post-hoc
    "missing evidence" fill). Fetches any operator-supplied links, then re-runs
    reviewer → partner in place on the same startup row via the lookup worker.
    Body: {"additional_context": "...", "lookup_id": optional stable id}.
    """
    validate_route_id(startup_id, field_name="startup_id")
    additional_context = str(body.get("additional_context") or "").strip()
    if not additional_context:
        raise HTTPException(status_code=422, detail="additional_context is required for a re-review")
    if len(additional_context) > 2000:
        raise HTTPException(status_code=422, detail="additional_context is too long (max 2000 chars)")
    user_id = require_authenticated_user(request)
    lookup_id = _coerce_lookup_id(body.get("lookup_id"))
    storage = _get_storage(request)
    # Sync Supabase round trip — keep it off the event loop (async handler).
    raw = await asyncio.to_thread(storage.get_by_id, startup_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Startup not found")
    scout_info = raw.get("scout_info") or {}
    company_name = str(scout_info.get("name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Startup has no company name to re-run")
    website = (
        str(scout_info.get("lookup_website") or "").strip()
        or str((scout_info.get("company_resolution") or {}).get("website") or "").strip()
        or None
    )
    if _durable_jobs_required() and _durable_job_repository is None:
        return _durable_store_unavailable()
    if not _durable_jobs_required() and _lookup_queue is None:
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
                "mode": "on_demand_rerun",
            },
        )
    limited = _enforce_rate_limits(f"user:{user_id}:lookup", [_LOOKUP_MINUTE_POLICY, _LOOKUP_DAY_POLICY])
    if limited is not None:
        _release_security_lock(lock_key)
        return limited
    if _durable_jobs_required():
        try:
            accepted_job = await _enqueue_company_lookup(
                user_id,
                company_name=company_name,
                website=website,
                lookup_query=company_name,
                lookup_input_type="company_name",
                lookup_id=lookup_id,
                additional_context=additional_context,
                replace_startup_id=startup_id,
            )
        except Exception as exc:
            _logger_agents.error(
                "rerun durable enqueue failed user=%s error=%s",
                user_id[:12],
                type(exc).__name__,
            )
            _release_security_lock(lock_key)
            return _durable_store_unavailable()
        _release_security_lock(lock_key)
        job_fields = _job_response_fields(accepted_job)
    else:
        await _lookup_queue.put(
            {
                "user_id": user_id,
                "company_name": company_name,
                "website": website,
                "lookup_query": company_name,
                "lookup_input_type": "company_name",
                "lookup_id": lookup_id,
                "lock_key": lock_key,
                "additional_context": additional_context,
                "replace_startup_id": startup_id,
            }
        )
        job_fields = {"status": "queued"}
    return JSONResponse(
        status_code=202,
        content={
            **job_fields,
            "user_id": user_id,
            "lookup_id": lookup_id,
            "startup_id": startup_id,
            "company_name": company_name,
            "mode": "on_demand_rerun",
        },
    )


@app.post("/api/startups/lookup/resolve")
async def resolve_lookup_candidates(request: Request, body: Dict[str, Any]):
    """Cheap, synchronous, LLM-free identity resolution for the dispatch picker.

    Body: {"lookup_input": "...", "website_hint": optional}. Returns the distinct
    company candidates the typed name could mean WITHOUT running scout/reviewer/partner.
    """
    from resolver.company_resolver import resolve_company

    lookup_input = str(body.get("lookup_input") or body.get("company_name") or "").strip()
    if not lookup_input:
        raise HTTPException(status_code=422, detail="lookup_input is required")
    if len(lookup_input) > 300:
        raise HTTPException(status_code=422, detail="lookup_input is too long")
    user_id = require_authenticated_user(request)
    # Own bucket: a cheap resolve must not consume the expensive queue's budget.
    limited = _enforce_rate_limits(f"user:{user_id}:resolve", [_RESOLVE_MINUTE_POLICY])
    if limited is not None:
        return limited

    parsed = _parse_lookup_input(lookup_input)
    company_name = str(parsed.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="Could not derive company name from lookup_input")
    website_hint = str(body.get("website_hint") or parsed.get("website") or "").strip() or None

    resolver_started = time.perf_counter()
    resolution = await asyncio.to_thread(
        resolve_company,
        company_name,
        user_id=user_id,
        website_hint=website_hint,
    )
    metrics.observe_pipeline_stage(
        time.perf_counter() - resolver_started,
        pipeline="lookup",
        stage="resolver",
        outcome="success",
    )
    status = _resolve_status_for(resolution, website_hint=website_hint)
    resolution_token = (
        _cache_lookup_resolution(user_id, resolution) if status == "resolved" else None
    )
    candidates = [c.model_dump(mode="json") for c in resolution.candidates]
    return JSONResponse(
        status_code=200,
        content={
            "status": status,
            "canonical_name": resolution.canonical_name,
            "company_name": company_name,
            "website_hint": website_hint,
            "candidates": candidates if status != "resolved" else candidates[:1],
            "resolution_token": resolution_token,
        },
    )


@app.post("/api/startups/lookup/cancel")
async def cancel_lookup(request: Request, body: Dict[str, Any]):
    """Cancel queued/running on-demand lookups for this user.

    Running lookups stop cooperatively at stage boundaries; the frontend can clear
    its dispatch state immediately after this returns.
    """
    user_id = require_authenticated_user(request)
    raw_ids = body.get("lookup_ids")
    if raw_ids is None and body.get("lookup_id") is not None:
        raw_ids = [body.get("lookup_id")]
    if not isinstance(raw_ids, list) or not raw_ids:
        raise HTTPException(status_code=422, detail="lookup_ids is required")

    cancelled: List[str] = []
    cancelled_job_ids: List[str] = []
    conflicts: List[Dict[str, str]] = []
    restored_startup_ids: List[str] = []
    storage = None
    if env_config.use_supabase_storage():
        try:
            storage = _get_storage(request)
        except Exception as e:
            _logger_agents.warning("lookup cancel: storage restore unavailable: %s", e)
    for raw in raw_ids[:16]:
        lookup_id = _coerce_lookup_id(raw)
        if _durable_job_repository is not None:
            job = await _durable_job_repository.get_by_idempotency_key(
                user_id=user_id,
                idempotency_key=_lookup_idempotency_key(user_id, lookup_id),
            )
            if job is not None:
                try:
                    cancellation = await _durable_job_repository.cancel(
                        user_id=user_id,
                        job_id=job.job_id,
                    )
                except LookupOutcomeStoreUnavailable as exc:
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "status": "unavailable",
                            "reason": "lookup_outcome_store_unavailable",
                        },
                    ) from exc
                if not cancellation.cancellation_won:
                    current_status = (
                        cancellation.job.status.value
                        if cancellation.job is not None
                        else JobCancellationDisposition.NOT_FOUND.value
                    )
                    conflicts.append(
                        {
                            "lookup_id": lookup_id,
                            "job_id": job.job_id,
                            "status": current_status,
                        }
                    )
                    continue
                cancelled_job_ids.append(job.job_id)
            else:
                conflicts.append(
                    {
                        "lookup_id": lookup_id,
                        "job_id": "",
                        "status": JobCancellationDisposition.NOT_FOUND.value,
                    }
                )
                continue
        _mark_lookup_cancelled(user_id, lookup_id)
        cancelled.append(lookup_id)
        if isinstance(storage, SupabaseStartupsStorage):
            restored = await asyncio.to_thread(storage.mark_existing_rerun_cancelled, lookup_id)
            if restored:
                restored_startup_ids.append(restored)
                _notify_startups_changed(user_id, "lookup_cancelled")

    response_status = (
        "cancelled"
        if not conflicts
        else ("partially_cancelled" if cancelled else "conflict")
    )
    return JSONResponse(
        status_code=202 if cancelled else 409,
        content={
            "status": response_status,
            "cancelled": cancelled,
            "job_ids": cancelled_job_ids,
            "restored_startup_ids": restored_startup_ids,
            "conflicts": conflicts,
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
        report = await agent.run_cycle(force=True)
        if not report:
            return {"status": "no-op", "cycle_number": 0}
        cycle_number = int(report.get("cycle_number", 0))
        return {"status": "ok", "cycle_number": cycle_number}
    finally:
        _release_security_lock(lock_key)


@app.get("/api/escalations")
def get_escalations(request: Request):
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
def resolve_escalation(request: Request, startup_id: str, body: Dict[str, Any]):
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
        except Exception as e:
            _logger_agents.debug("Could not read AI recommendation for escalation: %s", e)
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
    except Exception as e:
        _logger_agents.debug("Could not persist escalation resolution: %s", e)

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
    except Exception as e:
        _logger_agents.debug("Could not append decision to fund memory: %s", e)

    return {"status": "ok"}
