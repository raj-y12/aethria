"""
Run one pipeline cycle (scout → reviewer → partner → portfolio → meta) for a single user.
Used by the per-user agent queue: explicit user_id on every storage path (no run_context).
"""
import asyncio
import gc
import logging
import os
import re
import env_config
import metrics
import resource
import time
from datetime import datetime, timezone
from utils.timeutil import utcnow
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    from pathlib import Path

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
    else:
        load_dotenv()

from tenant_context import TenantContext, require_user_id
from event_bus import publish as _publish_event
from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    EvaluationPrerequisites,
    load_evaluation_prerequisites,
)
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState
from pipeline_concurrency import pipeline_execution_slot, lookup_execution_slot
from supabase_doc_store import list_upsert
from utils.settings_loader import load_settings, is_thesis_reprocess_agents_enabled
from supabase_client import get_service_client
from supabase_storage import SupabaseStartupsStorage
from pipeline_state import upsert_pipeline_state
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine
from partner.engine import PartnerEngine
from portfolio.store import PortfolioStore
from portfolio.engine import PortfolioEngine
from portfolio.cost_control import CostController
from memory import DealMemory
from meta.agent import MetaAgent
from memo_generator import MemoGenerator
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisMissingError,
    _bootstrap_default_thesis_or_raise,
    get_active_thesis,
)
from identity.acquisition import observation_from_scout_discovery
from identity.projection import link_admission_projection
from identity.service import IdentityService
from utils.reference_validation import is_generic_reference

logger = logging.getLogger("pipeline_runner")
_visible_logger = logging.getLogger("uvicorn.error")

DEFAULT_SCOUT_MODEL = "gpt-5-nano"
DEFAULT_REVIEWER_MODEL = "gpt-5-nano"


@dataclass
class _PipelineEngines:
    scout_engine: ScoutEngine
    reviewer_engine: ReviewerEngine
    partner_engine: PartnerEngine
    portfolio_store: PortfolioStore
    cost_controller: Optional[CostController] = None
    model_metadata: Dict[str, str] = field(default_factory=dict)


def _build_pipeline_engines(
    *,
    user_id: str,
    storage: SupabaseStartupsStorage,
    api_key: str,
    settings: Dict[str, Any],
    thesis_ctx=None,
    evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
    use_resource_fund_thesis_fallback: bool = True,
) -> _PipelineEngines:
    uid = require_user_id(user_id, context="_build_pipeline_engines")
    if evaluation_prerequisites is not None:
        evaluation_prerequisites.require_tenant(
            uid, context="_build_pipeline_engines"
        )
        if (
            thesis_ctx is not None
            and thesis_ctx != evaluation_prerequisites.thesis_context
        ):
            raise RuntimeError(
                "_build_pipeline_engines: thesis does not match governed prerequisites"
            )
        thesis_ctx = evaluation_prerequisites.thesis_context
    if thesis_ctx is None:
        raise RuntimeError("_build_pipeline_engines requires an exact thesis context")
    cost_budget_enabled = bool((settings.get("cost_budget") or {}).get("enabled", False))
    cost_controller = CostController(
        user_id=user_id,
        enforce_limits=cost_budget_enabled,
    )
    deal_memory = DealMemory(user_id=user_id)
    model = os.getenv("SCOUT_MODEL", DEFAULT_SCOUT_MODEL)
    reviewer_model = os.getenv("REVIEWER_MODEL", DEFAULT_REVIEWER_MODEL)
    use_llm_fallback = os.getenv("PARTNER_USE_LLM", "true").lower() == "true"
    reviewer_batch_size = max(1, int(os.getenv("REVIEWER_BATCH_SIZE", "3")))

    scout_engine = ScoutEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=300,
        model=model,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        tenant_user_id=user_id,
        active_thesis=thesis_ctx,
    )
    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model=reviewer_model,
        batch_size=reviewer_batch_size,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        tenant_user_id=user_id,
        active_thesis=thesis_ctx,
        use_resource_fund_thesis_fallback=use_resource_fund_thesis_fallback,
        evaluation_prerequisites=evaluation_prerequisites,
    )
    portfolio_dir = os.getenv("PORTFOLIO_DIR", "data/portfolio")
    portfolio_store = PortfolioStore(data_dir=portfolio_dir, user_id=user_id)
    partner_engine = PartnerEngine(
        storage=storage,
        interval_seconds=30,
        use_llm_fallback=use_llm_fallback,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        portfolio_store=portfolio_store,
        tenant_user_id=user_id,
        fund_thesis=thesis_ctx,
        use_resource_fund_thesis_fallback=use_resource_fund_thesis_fallback,
        evaluation_prerequisites=evaluation_prerequisites,
    )
    return _PipelineEngines(
        scout_engine=scout_engine,
        reviewer_engine=reviewer_engine,
        partner_engine=partner_engine,
        portfolio_store=portfolio_store,
        cost_controller=cost_controller,
        model_metadata={
            "scout": model,
            "reviewer": reviewer_model,
            "partner": getattr(
                getattr(partner_engine, "decision_engine", None), "model", None
            )
            or os.getenv("PARTNER_MODEL", "gpt-5-nano"),
        },
    )


def _close_pipeline_engines(*engines: object) -> None:
    """Tear down per-cycle LLM clients / thread pools so they don't accumulate.

    Engines are rebuilt every cycle; their OpenAI (httpx) clients and worker
    threads must be released explicitly or RSS grows until the instance OOMs.
    """
    for engine in engines:
        if engine is None:
            continue
        close = getattr(engine, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Engine close failed (%s): %s", type(engine).__name__, exc)


def _observe_decision_ready_usage(
    cost_controller: Optional[CostController],
    *,
    before: Dict[str, Any],
    cohort: str,
    decision_count: int = 1,
) -> None:
    """Observe per-decision usage from one tenant-local cumulative delta."""
    if cost_controller is None or decision_count <= 0:
        return
    after = cost_controller.snapshot_usage()
    delta = cost_controller.usage_delta(before, after)
    metrics.observe_decision_ready_usage(
        cohort=cohort,
        cost_usd=round(float(delta["cost_usd"]) / decision_count, 8),
        tokens=int(round(int(delta["tokens"]) / decision_count)),
    )


def _usage_snapshot(cost_controller: Optional[CostController]) -> Dict[str, Any]:
    if cost_controller is None:
        return {"calls": 0, "tokens": 0, "cost_usd": 0.0}
    return cost_controller.snapshot_usage()


def _build_storage_sync(user_id: str) -> SupabaseStartupsStorage:
    """Blocking client/storage construction; call via asyncio.to_thread."""
    return SupabaseStartupsStorage(get_service_client(), user_id)


def _load_active_thesis_sync(user_id: str, *, tolerate_bootstrap_failure: bool = False):
    """Read (bootstrapping if absent) the active thesis. Blocking Supabase I/O;
    call via asyncio.to_thread. May raise FundThesisIncompleteError."""
    svc = get_service_client()
    active = get_active_thesis(svc, user_id)
    if active is None:
        try:
            _bootstrap_default_thesis_or_raise(svc, user_id)
            active = get_active_thesis(svc, user_id)
        except Exception as e:
            if not tolerate_bootstrap_failure:
                raise
            logger.info("[%s] Lookup: default thesis bootstrap skipped: %s", user_id[:12], e)
    return active


def _count_startups_sync(user_id: str) -> int:
    """Blocking Supabase count; call via asyncio.to_thread."""
    r = (
        get_service_client()
        .table("startups")
        .select("startup_id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return int(getattr(r, "count", None) or 0)


def _safe_stage_count(storage: SupabaseStartupsStorage, method_name: str, user_id: str) -> Optional[int]:
    """Best-effort counter for stage logging; never raise."""
    try:
        method = getattr(storage, method_name)
        return int(method())
    except Exception as e:
        logger.debug(
            "[%s] %s unavailable: %s",
            user_id[:12],
            method_name,
            e,
        )
        return None


def _visible_info(message: str, *args: object) -> None:
    """Log to both pipeline logger and uvicorn logger for local dev visibility."""
    logger.info(message, *args)
    _visible_logger.info(message, *args)


def _rss_mb() -> float:
    """Best-effort current resident memory in MB for small-instance diagnostics."""
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        with open("/proc/self/statm", "r", encoding="utf-8") as f:
            parts = f.read().split()
        if len(parts) >= 2:
            return round((int(parts[1]) * page_size) / (1024 * 1024), 1)
    except Exception:
        pass
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Fallback: macOS reports bytes; Linux reports high-water KiB.
        return round((rss / (1024 * 1024)) if rss > 10_000_000 else (rss / 1024), 1)
    except Exception:
        return -1.0


def _notify_startups_changed(user_id: str, reason: str) -> None:
    """Best-effort SSE nudge: tell connected clients their deal-flow changed.

    A pipeline stage just mutated the user's startups, so push a lightweight
    event that makes the frontend refetch immediately instead of waiting for
    its next poll tick. Never raises — a failed notify must not affect the
    pipeline. When no client is connected this is a cheap no-op.
    """
    try:
        _publish_event(user_id, {"type": "startups_changed", "reason": reason})
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("[%s] startups_changed notify failed: %s", user_id[:12], e)


async def _prune_unreferenced_startups(
    storage: SupabaseStartupsStorage,
    user_id: str,
) -> int:
    """Apply the mandatory reference gate without blocking the serving loop."""
    removed = await asyncio.to_thread(storage.remove_startups_without_references)
    if removed:
        logger.info("[%s] Reference gate pruned %s startup(s)", user_id[:12], removed)
        _notify_startups_changed(user_id, "reference_prune")
    return removed


async def _admit_autonomous_discoveries(
    *,
    user_id: str,
    discoveries: list[Dict[str, Any]],
    storage: Any,
    identity_repository: Any,
    identity_service: Optional[Any] = None,
    discoveries_are_persisted: bool = True,
) -> list[Any]:
    """Admit only reference-gated rows and quarantine ambiguous projections."""

    if identity_repository is None:
        return []
    service = identity_service or IdentityService(identity_repository)
    admissions = []
    for discovery in discoveries:
        startup_id = str(
            discovery.get("persisted_startup_id") or discovery.get("id") or ""
        ).strip()
        if not startup_id:
            continue
        if discoveries_are_persisted:
            # The reference prune is authoritative for compatibility survival. A
            # raw Scout result that no longer has a row must never create state.
            if await asyncio.to_thread(storage.get_startup, startup_id) is None:
                continue
        else:
            references = discovery.get("references")
            valid_references = [
                item
                for item in references or []
                if isinstance(item, str)
                and item.strip()
                and not is_generic_reference(item)
            ]
            if not valid_references:
                continue
        observation = observation_from_scout_discovery(
            user_id=user_id,
            discovery=discovery,
            include_legacy_projection=discoveries_are_persisted,
        )
        admission = await service.admit(observation)
        admissions.append(admission)
        if admission.blocks_evaluation or not admission.opportunity_id:
            if not discoveries_are_persisted:
                logger.info(
                    "[%s] Identity review blocked unpersisted discovery startup_id=%s case_id=%s",
                    user_id[:12],
                    startup_id,
                    admission.identity_case_id,
                )
                continue
            remover = getattr(storage, "remove_startup", None)
            if not callable(remover):
                raise RuntimeError(
                    "Identity-blocked discovery cannot be removed from review queue"
                )
            await asyncio.to_thread(remover, startup_id)
            logger.info(
                "[%s] Identity review blocked discovery startup_id=%s case_id=%s",
                user_id[:12],
                startup_id,
                admission.identity_case_id,
            )
            continue
        if not discoveries_are_persisted:
            persisted_id = await asyncio.to_thread(
                storage.add_discovery,
                discovery,
                pipeline_run_id=discovery.get("pipeline_run_id"),
            )
            startup_id = str(persisted_id or startup_id)
            discovery["persisted_startup_id"] = startup_id
        await link_admission_projection(
            identity_repository,
            admission=admission,
            legacy_startup_id=startup_id,
        )
    return admissions


async def _record_lookup_failure(user_id: str, lookup_id: Optional[str], message: str) -> None:
    lid = (lookup_id or "").strip()
    if not lid or not user_id or not str(user_id).strip():
        return
    use_supabase = env_config.use_supabase_storage()
    if not use_supabase:
        return
    uid = user_id.strip()
    text = (message or "Lookup failed.").strip()[:500]
    try:
        await asyncio.to_thread(
            list_upsert,
            "lookup_job_outcomes",
            {
                "id": lid,
                "lookup_id": lid,
                "status": "failed",
                "message": text,
                "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            user_id=uid,
        )
    except Exception as e:
        logger.warning(
            "[%s] Could not persist lookup failure for %s: %s",
            uid[:12],
            lid[:16],
            e,
        )


async def _record_lookup_outcome(
    user_id: str,
    lookup_id: Optional[str],
    *,
    status: str,
    startup_id: str,
    message: Optional[str] = None,
) -> None:
    """Persist a terminal non-failure lookup outcome for frontend correlation."""
    lid = (lookup_id or "").strip()
    sid = (startup_id or "").strip()
    uid = (user_id or "").strip()
    if not lid or not sid or not uid or not env_config.use_supabase_storage():
        return
    record = {
        "id": lid,
        "lookup_id": lid,
        "status": status.strip().lower(),
        "startup_id": sid,
        "message": (message or "").strip() or None,
    }
    if record["message"] is None:
        record.pop("message")
    try:
        await asyncio.to_thread(
            list_upsert,
            "lookup_job_outcomes",
            record,
            user_id=uid,
        )
    except Exception as exc:
        logger.warning(
            "[%s] Could not persist lookup outcome for %s: %s",
            uid[:12],
            lid[:16],
            exc,
        )


async def _record_lookup_execution_result(
    user_id: str,
    lookup_id: Optional[str],
    result: PipelineExecutionResult,
) -> None:
    """Persist an actionable non-completed direct-worker result for the UI."""
    lid = (lookup_id or "").strip()
    uid = (user_id or "").strip()
    if not lid or not uid or not env_config.use_supabase_storage():
        return
    record = {
        "id": lid,
        "lookup_id": lid,
        "status": result.state.value,
        "code": result.code,
        "message": result.detail[:500],
        "recovery_action": result.recovery_action,
        "failed_stage": result.failed_stage,
        "startup_id": result.startup_id,
    }
    record = {key: value for key, value in record.items() if value is not None}
    try:
        await asyncio.to_thread(
            list_upsert,
            "lookup_job_outcomes",
            record,
            user_id=uid,
        )
    except Exception as exc:
        logger.warning(
            "[%s] Could not persist typed lookup result for %s: %s",
            uid[:12],
            lid[:16],
            exc,
        )


async def _mark_lookup_pipeline_failed(
    storage: SupabaseStartupsStorage,
    startup_id: Optional[str],
    pipeline_run_id: str,
    message: str,
) -> None:
    """Best-effort terminal state for a lookup that already persisted a row."""
    sid = (startup_id or "").strip()
    client = getattr(storage, "_client", None)
    uid = str(getattr(storage, "_user_id", None) or "").strip()
    if not sid or not client or not uid:
        return
    await asyncio.to_thread(
        upsert_pipeline_state,
        client,
        user_id=uid,
        startup_id=sid,
        pipeline_run_id=pipeline_run_id,
        status="failed",
        error=(message or "Lookup failed.").strip()[:500],
    )


async def run_one_pipeline_cycle(
    user_id: str,
    *,
    manual_one_shot: bool = False,
    pipeline_run_id: Optional[str] = None,
    identity_repository: Optional[Any] = None,
    evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
    fund_intelligence_repository: Optional[Any] = None,
) -> PipelineExecutionResult:
    """Run one cycle of scout, reviewer, partner, portfolio, and meta for the given user."""
    uid = require_user_id(user_id, context="run_one_pipeline_cycle")
    try:
        if evaluation_prerequisites is None:
            evaluation_prerequisites = await load_evaluation_prerequisites(
                user_id=uid,
                fund_intelligence_repository=fund_intelligence_repository,
            )
        evaluation_prerequisites.require_tenant(
            uid, context="run_one_pipeline_cycle"
        )
        async with pipeline_execution_slot(uid):
            return await _run_one_pipeline_cycle_inner(
                uid,
                manual_one_shot=manual_one_shot,
                pipeline_run_id=pipeline_run_id,
                identity_repository=identity_repository,
                evaluation_prerequisites=evaluation_prerequisites,
            )
    except EvaluationPrerequisiteError as exc:
        return PipelineExecutionResult.blocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        )


async def _run_one_pipeline_cycle_inner(
    user_id: str,
    *,
    manual_one_shot: bool = False,
    pipeline_run_id: Optional[str] = None,
    identity_repository: Optional[Any] = None,
    evaluation_prerequisites: EvaluationPrerequisites,
) -> PipelineExecutionResult:
    evaluation_prerequisites.require_tenant(
        user_id, context="_run_one_pipeline_cycle_inner"
    )
    tenant = TenantContext(user_id=user_id)
    logger.info(
        "event=tenant_context user_id=%s module=pipeline_cycle",
        tenant.user_id[:24],
    )

    use_supabase = env_config.use_supabase_storage()
    if not use_supabase:
        logger.info("[%s] Skipping pipeline (USE_SUPABASE_STORAGE not set)", user_id[:12])
        return PipelineExecutionResult.blocked(
            code="supabase_storage_required",
            detail="Pipeline execution requires Supabase storage.",
            recovery_action="Set USE_SUPABASE_STORAGE=1 and configure Supabase, then retry.",
        )

    try:
        # Read fresh settings at cycle boundaries so stage toggles apply immediately.
        # Blocking Supabase read — keep it off the serving event loop.
        settings = await asyncio.to_thread(load_settings, user_id, use_cache=False)
    except Exception as e:
        logger.warning("[%s] Pipeline skipped (settings unavailable): %s", user_id[:12], e)
        return PipelineExecutionResult.blocked(
            code="runtime_settings_unavailable",
            detail="Tenant runtime settings could not be loaded.",
            recovery_action="Restore the settings store and retry the pipeline cycle.",
        )
    ac = settings.get("agent_config") or {}
    scouts_enabled = bool(ac.get("scouts_enabled", False))
    reviewers_enabled = bool(ac.get("reviewers_enabled", False))
    partners_enabled = bool(ac.get("partners_enabled", False))
    if not (scouts_enabled or reviewers_enabled or partners_enabled):
        if manual_one_shot:
            scouts_enabled = True
            reviewers_enabled = True
            partners_enabled = True
            logger.info("[%s] Manual one-shot pipeline using all stages while Ops/Agents is off", user_id[:12])
        else:
            logger.info("[%s] Agents disabled in settings, skipping", user_id[:12])
            return PipelineExecutionResult.skipped(
                code="agents_disabled",
                detail="No Scout, Reviewer, or Partner stage is enabled for this tenant.",
            )
    logger.debug(
        "[%s] agent gates: scouts=%s reviewers=%s partners=%s",
        user_id[:12],
        scouts_enabled,
        reviewers_enabled,
        partners_enabled,
    )
    if identity_repository is None:
        logger.error(
            "[%s] Pipeline blocked: canonical identity repository unavailable",
            user_id[:12],
        )
        return PipelineExecutionResult.blocked(
            code="institutional_identity_repository_required",
            detail="Enabled pipeline stages require the canonical identity repository.",
            recovery_action=(
                "Restore the institutional PostgreSQL repository and retry the "
                "pipeline cycle."
            ),
        )

    try:
        storage = await asyncio.to_thread(_build_storage_sync, user_id)
    except Exception as e:
        logger.warning("[%s] Failed to create storage: %s", user_id[:12], e)
        return PipelineExecutionResult.blocked(
            code="startup_storage_unavailable",
            detail="Tenant startup storage could not be initialized.",
            recovery_action="Restore Supabase connectivity and retry the pipeline cycle.",
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[%s] OPENAI_API_KEY missing, skipping pipeline", user_id[:12])
        _visible_logger.warning("[%s] Pipeline skipped: OPENAI_API_KEY not set", user_id[:12])
        return PipelineExecutionResult.blocked(
            code="openai_api_key_required",
            detail="OPENAI_API_KEY is required for pipeline evaluation.",
            recovery_action="Configure OPENAI_API_KEY and retry the pipeline cycle.",
        )

    # Engine constructors do blocking I/O (DealMemory doc-store read,
    # ReviewerEngine settings/policy load, CostController budget state) —
    # one thread hop for the whole build.
    try:
        engines = await asyncio.to_thread(
            _build_pipeline_engines,
            user_id=user_id,
            storage=storage,
            api_key=api_key,
            settings=settings,
            evaluation_prerequisites=evaluation_prerequisites,
        )
    except EvaluationPrerequisiteError:
        raise
    except Exception as exc:
        logger.exception("[%s] Pipeline engine initialization failed: %s", user_id[:12], exc)
        return PipelineExecutionResult.stage_failure(
            stage="initialization",
            code="pipeline_engine_initialization_failed",
            detail="Pipeline engines could not be initialized from certified inputs.",
            recovery_action="Inspect engine initialization logs, correct the runtime configuration, and retry.",
        )
    scout_engine = engines.scout_engine
    reviewer_engine = engines.reviewer_engine
    partner_engine = engines.partner_engine
    portfolio_store = engines.portfolio_store
    cycle_usage_before = _usage_snapshot(engines.cost_controller)

    started_at = time.perf_counter()
    agents_executed = 0
    total_startups_before: Optional[int] = None
    total_startups_after: Optional[int] = None
    current_stage = "scout"
    try:
        pipeline_run_id = (pipeline_run_id or "").strip() or str(uuid4())
        logger.info(
            "[%s] pipeline_run_id=%s module=pipeline_cycle rss_mb_start=%.1f",
            user_id[:12],
            pipeline_run_id,
            _rss_mb(),
        )
        _activity_startups_before = 0
        _activity_startups_found = 0
        try:
            total_startups_before = await asyncio.to_thread(_count_startups_sync, user_id)
            _activity_startups_before = total_startups_before
        except Exception as e:
            logger.debug("[%s] startups_before count unavailable: %s", user_id[:12], e)
        discoveries = []
        if scouts_enabled and identity_repository is not None:
            agents_executed += len(getattr(scout_engine, "scouts", []) or [])
            discoveries = await scout_engine.run_cycle(
                pipeline_run_id=pipeline_run_id,
                persist_discoveries=False,
            )
        elif scouts_enabled:
            logger.error(
                "[%s] Scout stage skipped: canonical identity store unavailable",
                user_id[:12],
            )
        else:
            logger.info("[%s] Scout stage skipped (disabled in settings)", user_id[:12])

        # Mandatory production gate: periodic discoveries without verifiable
        # external references must not reach reviewer/partner stages. Existing
        # on-demand lookup and resolution-status guards live in storage.
        await _prune_unreferenced_startups(storage, user_id)

        if scouts_enabled and identity_repository is not None:
            await _admit_autonomous_discoveries(
                user_id=user_id,
                discoveries=discoveries,
                storage=storage,
                identity_repository=identity_repository,
                discoveries_are_persisted=False,
            )
            _notify_startups_changed(user_id, "scout")

        eligible_startup_ids: set[str] = set()
        if identity_repository is not None:
            eligible_startup_ids = set(
                await identity_repository.list_linked_legacy_startup_ids(
                    user_id=user_id
                )
            )

        _activity_reviewed_count = 0
        _activity_decided_count = 0
        _activity_escalations_count = 0
        if reviewers_enabled and identity_repository is not None:
            current_stage = "reviewer"
            agents_executed += 3
            unreviewed_before = await asyncio.to_thread(_safe_stage_count, storage, "count_unreviewed", user_id)
            if (unreviewed_before or 0) > 0:
                _visible_info(
                    "[%s] Reviewer stage start: unreviewed_before=%s",
                    user_id[:12],
                    unreviewed_before,
                )
            reviewed_count = await reviewer_engine.run_cycle(
                pipeline_run_id=pipeline_run_id,
                eligible_startup_ids=eligible_startup_ids,
            )
            _activity_reviewed_count = reviewed_count or 0
            if _activity_reviewed_count > 0:
                _notify_startups_changed(user_id, "reviewer")
            reviewer_stats = getattr(reviewer_engine, "last_cycle_stats", {}) or {}
            unreviewed_after = await asyncio.to_thread(_safe_stage_count, storage, "count_unreviewed", user_id)
            if reviewed_count > 0 or (unreviewed_before or 0) > 0 or (unreviewed_after or 0) > 0:
                _visible_info(
                    "[%s] Reviewer stage done: reviewed=%s unreviewed_after=%s threshold=%s candidates_seen=%s skipped_low_confidence=%s reason=%s",
                    user_id[:12],
                    reviewed_count,
                    unreviewed_after,
                    reviewer_stats.get("confidence_threshold"),
                    reviewer_stats.get("candidates_seen"),
                    reviewer_stats.get("skipped_low_confidence"),
                    reviewer_stats.get("reason"),
                )
        else:
            logger.info(
                "[%s] Reviewer stage skipped (%s)",
                user_id[:12],
                "disabled in settings" if not reviewers_enabled else "canonical identity store unavailable",
            )

        if partners_enabled and identity_repository is not None:
            current_stage = "partner"
            agents_executed += 1
            undecided_before = await asyncio.to_thread(_safe_stage_count, storage, "count_undecided", user_id)
            if (undecided_before or 0) > 0:
                _visible_info(
                    "[%s] Partner stage start: undecided_before=%s",
                    user_id[:12],
                    undecided_before,
                )
            decided_count = await partner_engine.run_cycle(
                pipeline_run_id=pipeline_run_id,
                eligible_startup_ids=eligible_startup_ids,
            )
            _activity_decided_count = decided_count or 0
            if _activity_decided_count > 0:
                _observe_decision_ready_usage(
                    engines.cost_controller,
                    before=cycle_usage_before,
                    cohort="autonomous_discovery",
                    decision_count=_activity_decided_count,
                )
                for _ in range(_activity_decided_count):
                    metrics.inc_evaluation_manifest(
                        path="autonomous_discovery", outcome="success"
                    )
            _activity_escalations_count = getattr(partner_engine, "last_cycle_escalations", 0)
            if _activity_decided_count > 0 or _activity_escalations_count > 0:
                _notify_startups_changed(user_id, "partner")
            undecided_after = await asyncio.to_thread(_safe_stage_count, storage, "count_undecided", user_id)
            if decided_count > 0 or (undecided_before or 0) > 0 or (undecided_after or 0) > 0:
                _visible_info(
                    "[%s] Partner stage done: decided=%s undecided_after=%s",
                    user_id[:12],
                    decided_count,
                    undecided_after,
                )
        else:
            logger.info(
                "[%s] Partner stage skipped (%s)",
                user_id[:12],
                "disabled in settings" if not partners_enabled else "canonical identity store unavailable",
            )

        current_stage = "portfolio"
        portfolio_engine = PortfolioEngine(
            discovery_storage=storage,
            portfolio_store=portfolio_store,
            execution_interval=10,
            signal_interval=3600,
            feedback_interval=86400,
            health_interval=3600,
        )
        agents_executed += 1
        await portfolio_engine.run_cycle()

        try:
            current_stage = "meta"
            meta_agent = MetaAgent(
                scout_engine=scout_engine,
                reviewer_engine=reviewer_engine,
                user_id=user_id,
            )
            agents_executed += 1
            await meta_agent.run_cycle()
        except Exception as meta_err:
            logger.warning("[%s] Meta-agent cycle skipped: %s", user_id[:12], meta_err)

        # Persist activity metrics for the "While you were away" summary
        try:
            _startups_after = 0
            total_startups_after = await asyncio.to_thread(_count_startups_sync, user_id)
            if scouts_enabled:
                _startups_after = total_startups_after
            _activity_startups_found = max(0, _startups_after - _activity_startups_before)

            def _insert_activity_sync() -> None:
                get_service_client().table("pipeline_activity").insert({
                    "user_id": user_id,
                    "startups_found": _activity_startups_found,
                    "reviewed_count": _activity_reviewed_count,
                    "decisions_made": _activity_decided_count,
                    "escalations_count": _activity_escalations_count,
                }).execute()

            await asyncio.to_thread(_insert_activity_sync)
        except Exception as _act_err:
            logger.warning("[%s] Could not persist pipeline_activity: %s", user_id[:12], _act_err)

        gc.collect()
        _cycle_duration = time.perf_counter() - started_at
        metrics.observe_pipeline_cycle(_cycle_duration, outcome="success")
        metrics.inc_stage("startups_found", _activity_startups_found)
        metrics.inc_stage("reviewed", _activity_reviewed_count)
        metrics.inc_stage("decided", _activity_decided_count)
        metrics.inc_stage("escalations", _activity_escalations_count)
        logger.info(
            "[%s] Pipeline cycle completed rss_mb_end=%.1f duration_s=%.2f startups_before=%s startups_after=%s startups_found=%s reviewed=%s decided=%s escalations=%s agents_executed=%s",
            user_id[:12],
            _rss_mb(),
            _cycle_duration,
            total_startups_before,
            total_startups_after,
            _activity_startups_found,
            _activity_reviewed_count,
            _activity_decided_count,
            _activity_escalations_count,
            agents_executed,
        )
        return PipelineExecutionResult.completed(
            code="pipeline_cycle_completed",
            detail="The pipeline cycle completed.",
            metadata={
                "startups_found": _activity_startups_found,
                "reviewed": _activity_reviewed_count,
                "decided": _activity_decided_count,
                "escalations": _activity_escalations_count,
                "agents_executed": agents_executed,
            },
        )
    except Exception as e:
        metrics.observe_pipeline_cycle(time.perf_counter() - started_at, outcome="error")
        logger.exception("[%s] Pipeline cycle error: %s", user_id[:12], e)
        if isinstance(e, EvaluationPrerequisiteError):
            raise
        return PipelineExecutionResult.stage_failure(
            stage=current_stage,
            code=f"{current_stage}_stage_failed",
            detail=f"The {current_stage} stage did not complete.",
            recovery_action="Inspect the pipeline stage logs, correct the failure, and retry.",
        )
    finally:
        _close_pipeline_engines(scout_engine, reviewer_engine, partner_engine)
        gc.collect()


async def run_on_demand_lookup(
    user_id: str,
    company_name: str,
    website: Optional[str] = None,
    lookup_query: Optional[str] = None,
    lookup_input_type: Optional[str] = None,
    lookup_id: Optional[str] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    additional_context: Optional[str] = None,
    replace_startup_id: Optional[str] = None,
    resolution: Optional[Any] = None,
    pipeline_run_id: Optional[str] = None,
    checkpoint: Optional[
        Callable[[str, str, Dict[str, Any]], Awaitable[None]]
    ] = None,
    institutional_context: Optional[Dict[str, Any]] = None,
    evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
    fund_intelligence_repository: Optional[Any] = None,
) -> PipelineExecutionResult:
    """
    Run scout -> reviewer -> partner for one explicit company name.
    `additional_context` is optional operator-supplied background. Fresh lookups
    pass it to Scout; in-place re-reviews fetch named links and pass it directly
    to Reviewer via the stored scout context.
    `replace_startup_id` re-reviews an EXISTING row in place (post-hoc re-review):
    scout/resolver are SKIPPED — the stored profile, resolution, and sources are
    kept, the operator context (plus fetched content of any links it names) is
    stamped on the row, and only reviewer + partner run again.
    """
    uid = require_user_id(user_id, context="run_on_demand_lookup")
    company = (company_name or "").strip()
    if not company:
        logger.warning("run_on_demand_lookup: skipped (empty company name)")
        return PipelineExecutionResult.skipped(
            code="empty_company_name",
            detail="The lookup was skipped because no company name was provided.",
        )

    try:
        if evaluation_prerequisites is None:
            evaluation_prerequisites = await load_evaluation_prerequisites(
                user_id=uid,
                fund_intelligence_repository=fund_intelligence_repository,
            )
        evaluation_prerequisites.require_tenant(
            uid, context="run_on_demand_lookup"
        )
        # Lookups use their own slot so they never wait behind a full periodic cycle.
        async with lookup_execution_slot(uid):
            result = await _run_on_demand_lookup_inner(
                uid,
                company,
                website=website,
                lookup_query=lookup_query,
                lookup_input_type=lookup_input_type,
                lookup_id=lookup_id,
                is_cancelled=is_cancelled,
                additional_context=additional_context,
                replace_startup_id=replace_startup_id,
                resolution=resolution,
                pipeline_run_id=pipeline_run_id,
                checkpoint=checkpoint,
                institutional_context=institutional_context,
                evaluation_prerequisites=evaluation_prerequisites,
            )
        if result.state is not PipelineExecutionState.COMPLETED:
            await _record_lookup_execution_result(uid, lookup_id, result)
        return result
    except EvaluationPrerequisiteError as exc:
        result = PipelineExecutionResult.blocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        )
        await _record_lookup_execution_result(uid, lookup_id, result)
        return result


_OPERATOR_URL_RE = re.compile(r"https?://[^\s)>\]}\"']+")


def _build_rerun_operator_context(additional_context: Optional[str]) -> str:
    """
    Operator context block for a post-hoc re-review: the raw text plus the fetched
    content of any links it names (max 3, best-effort — a dead or unreachable link
    simply contributes nothing). Runs blocking HTTP; call via asyncio.to_thread.
    """
    from utils.tavily_client import tavily_extract

    text = (additional_context or "").strip()
    urls = _OPERATOR_URL_RE.findall(text)[:3]
    if not urls:
        return text
    for page in tavily_extract(urls):
        text += (
            f"\n\n[Content of operator-provided link {page['url']}]\n{page['content']}"
        )
    return text


async def _run_on_demand_lookup_inner(
    user_id: str,
    company: str,
    *,
    website: Optional[str] = None,
    lookup_query: Optional[str] = None,
    lookup_input_type: Optional[str] = None,
    lookup_id: Optional[str] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    additional_context: Optional[str] = None,
    replace_startup_id: Optional[str] = None,
    resolution: Optional[Any] = None,
    pipeline_run_id: Optional[str] = None,
    checkpoint: Optional[
        Callable[[str, str, Dict[str, Any]], Awaitable[None]]
    ] = None,
    institutional_context: Optional[Dict[str, Any]] = None,
    evaluation_prerequisites: EvaluationPrerequisites,
) -> PipelineExecutionResult:
    evaluation_prerequisites.require_tenant(
        user_id, context="_run_on_demand_lookup_inner"
    )
    tenant = TenantContext(user_id=user_id)
    logger.info(
        "event=tenant_context user_id=%s module=on_demand_lookup",
        tenant.user_id[:24],
    )
    lid = (lookup_id or "").strip() or None

    async def emit(stage: str, status: str, **metadata: Any) -> None:
        if checkpoint is not None:
            await checkpoint(stage, status, metadata)

    def cancelled() -> bool:
        try:
            return bool(is_cancelled and is_cancelled())
        except Exception:
            return False

    if cancelled():
        logger.info("[%s] Lookup cancelled before start: %s", user_id[:12], lid or company)
        return PipelineExecutionResult.skipped(
            code="lookup_cancelled",
            detail="The lookup was cancelled before evaluation started.",
        )

    use_supabase = env_config.use_supabase_storage()
    if not use_supabase:
        logger.info("[%s] Skipping lookup (USE_SUPABASE_STORAGE not set)", user_id[:12])
        await _record_lookup_failure(
            user_id,
            lid,
            "On-demand lookup requires Supabase storage (USE_SUPABASE_STORAGE).",
        )
        return PipelineExecutionResult.blocked(
            code="supabase_storage_required",
            detail="On-demand lookup requires Supabase storage.",
            recovery_action="Set USE_SUPABASE_STORAGE=1 and configure Supabase, then retry.",
        )
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[%s] OPENAI_API_KEY missing, skipping lookup", user_id[:12])
        _visible_logger.warning("[%s] Lookup skipped: OPENAI_API_KEY not set", user_id[:12])
        await _record_lookup_failure(
            user_id,
            lid,
            "OpenAI API key is not configured; lookup was not run.",
        )
        return PipelineExecutionResult.blocked(
            code="openai_api_key_required",
            detail="OPENAI_API_KEY is required for on-demand lookup.",
            recovery_action="Configure OPENAI_API_KEY and retry the lookup.",
        )

    try:
        storage = await asyncio.to_thread(_build_storage_sync, user_id)
    except Exception as e:
        logger.warning("[%s] Failed to create storage for lookup: %s", user_id[:12], e)
        await _record_lookup_failure(
            user_id,
            lid,
            "Could not connect to storage for this lookup.",
        )
        return PipelineExecutionResult.blocked(
            code="startup_storage_unavailable",
            detail="Tenant startup storage could not be initialized for lookup.",
            recovery_action="Restore Supabase connectivity and retry the lookup.",
        )

    # Consume the exact immutable thesis context certified by the shared gate.
    thesis_ctx = evaluation_prerequisites.thesis_context
    logger.info("[%s] Lookup will evaluate against certified thesis", user_id[:12])

    try:
        settings = await asyncio.to_thread(load_settings, user_id)
    except Exception as e:
        logger.warning("[%s] settings load failed during lookup: %s", user_id[:12], e)
        return PipelineExecutionResult.blocked(
            code="runtime_settings_unavailable",
            detail="Tenant runtime settings could not be loaded for lookup.",
            recovery_action="Restore the settings store and retry the lookup.",
        )
    # Same blocking-constructor offload as the periodic cycle path.
    try:
        engines = await asyncio.to_thread(
            _build_pipeline_engines,
            user_id=user_id,
            storage=storage,
            api_key=api_key,
            settings=settings,
            evaluation_prerequisites=evaluation_prerequisites,
            use_resource_fund_thesis_fallback=False,
        )
    except EvaluationPrerequisiteError:
        raise
    except Exception as exc:
        logger.exception("[%s] Lookup engine initialization failed: %s", user_id[:12], exc)
        return PipelineExecutionResult.stage_failure(
            stage="initialization",
            code="lookup_engine_initialization_failed",
            detail="Lookup engines could not be initialized from certified inputs.",
            recovery_action="Inspect engine initialization logs, correct the runtime configuration, and retry.",
        )
    scout_engine = engines.scout_engine
    reviewer_engine = engines.reviewer_engine
    partner_engine = engines.partner_engine
    lookup_usage_before = _usage_snapshot(engines.cost_controller)

    startup_id: Optional[str] = None
    lookup_outcome: Dict[str, Any] = {}
    current_stage = "scout"
    try:
        lookup_run_id = (pipeline_run_id or "").strip() or str(uuid4())
        evaluation_context = {
            **(institutional_context or {}),
            "thesis_version_id": evaluation_prerequisites.thesis_version_id,
            "policy_version_id": evaluation_prerequisites.policy.policy_version_id,
            "policy_hash": evaluation_prerequisites.policy.policy_hash,
        }
        await emit(
            "accepted",
            "succeeded",
            lookup_id=lid,
            pipeline_run_id=lookup_run_id,
            **evaluation_context,
        )
        logger.info(
            "[%s] on_demand_lookup pipeline_run_id=%s rss_mb_start=%.1f",
            user_id[:12],
            lookup_run_id,
            _rss_mb(),
        )
        if cancelled():
            logger.info("[%s] Lookup cancelled before scout: %s", user_id[:12], lid or company)
            return PipelineExecutionResult.skipped(
                code="lookup_cancelled",
                detail="The lookup was cancelled before Scout started.",
            )
        if replace_startup_id:
            # Post-hoc re-review: the company is already resolved and scouted — do NOT
            # re-discover. Keep the existing profile/resolution/sources, fetch any links
            # the operator named, stamp the context on the row, and re-run only
            # reviewer + partner below.
            operator_context = await asyncio.to_thread(
                _build_rerun_operator_context, additional_context
            )
            startup_id = await asyncio.to_thread(
                storage.prepare_rerun_startup,
                replace_startup_id,
                operator_context=operator_context,
                lookup_id=lid,
                pipeline_run_id=lookup_run_id,
            )
            if not startup_id:
                await _record_lookup_failure(
                    user_id,
                    lid,
                    "Re-review could not find the original record. It may have been "
                    "removed — run a fresh lookup.",
                )
                metrics.inc_lookup("not_found")
                return PipelineExecutionResult.stage_failure(
                    stage="scout",
                    code="rerun_target_not_found",
                    detail="The original startup record for re-review was not found.",
                    recovery_action="Run a fresh lookup or restore the original startup record.",
                )
        else:
            scout_stage_started = time.perf_counter()
            startup_id = await scout_engine.run_named_lookup(
                company_name=company,
                scout_type="market_driven",
                website=website,
                lookup_query=lookup_query,
                lookup_input_type=lookup_input_type,
                lookup_id=lookup_id,
                pipeline_run_id=lookup_run_id,
                additional_context=additional_context,
                resolution=resolution,
            )
            metrics.observe_pipeline_stage(
                time.perf_counter() - scout_stage_started,
                pipeline="lookup",
                stage="scout",
                outcome="success" if startup_id else "incomplete",
            )
            lookup_outcome = getattr(scout_engine, "last_lookup_outcome", None) or {}
        if not startup_id:
            # The resolver/scout records WHY it failed (status, queries used, missing
            # evidence) so the UI can explain instead of looking like a random failure.
            outcome = getattr(scout_engine, "last_lookup_outcome", None) or {}
            message = (outcome.get("message") or "").strip() or (
                f'Scout could not complete lookup for "{company}". Try a different name or website.'
            )
            logger.warning(
                "[%s] On-demand lookup failed at scout stage: %s status=%s",
                user_id[:12],
                company,
                outcome.get("status") or "unknown",
            )
            await _record_lookup_failure(user_id, lid, message)
            metrics.inc_lookup("not_found")
            return PipelineExecutionResult.stage_failure(
                stage="scout",
                code="scout_lookup_failed",
                detail=message,
                recovery_action="Retry with a canonical company name or verified website.",
            )
        await emit("scout", "succeeded", startup_id=startup_id)
        # The scout persisted a row — nudge the UI so the card appears at once.
        _notify_startups_changed(user_id, "lookup_scout")
        handoff_startup = getattr(scout_engine, "last_lookup_startup", None)
        if handoff_startup is None:
            # Existing-company and rerun paths load the pre-existing record once.
            get_startup = getattr(storage, "get_startup", None)
            if callable(get_startup):
                handoff_startup = await asyncio.to_thread(get_startup, startup_id)
        if cancelled():
            logger.info("[%s] Lookup cancelled after scout: %s (%s)", user_id[:12], company, startup_id)
            return PipelineExecutionResult.skipped(
                code="lookup_cancelled",
                detail="The lookup was cancelled after Scout completed.",
                startup_id=startup_id,
            )
        current_stage = "reviewer"
        reviewer_stage_started = time.perf_counter()
        reviewed = await reviewer_engine.run_startup(
            startup_id,
            ignore_confidence_threshold=True,
            pipeline_run_id=lookup_run_id,
            force_rerun=bool(replace_startup_id),
            bypass_agent_enabled_gate=True,
            startup=handoff_startup,
        )
        metrics.observe_pipeline_stage(
            time.perf_counter() - reviewer_stage_started,
            pipeline="lookup",
            stage="reviewer",
            outcome="success" if reviewed else "incomplete",
        )
        if not reviewed:
            logger.warning("[%s] On-demand lookup not reviewed: %s", user_id[:12], startup_id)
            message = "Lookup found the company, but analyst review could not complete after retrying."
            await _mark_lookup_pipeline_failed(storage, startup_id, lookup_run_id, message)
            await _record_lookup_failure(user_id, lid, message)
            metrics.inc_lookup("error")
            return PipelineExecutionResult.stage_failure(
                stage="reviewer",
                code="reviewer_stage_failed",
                detail=message,
                recovery_action="Inspect Reviewer logs and retry the lookup.",
                startup_id=startup_id,
            )
        await emit("reviewer", "succeeded", startup_id=startup_id)
        _notify_startups_changed(user_id, "lookup_reviewer")
        if cancelled():
            logger.info("[%s] Lookup cancelled after review: %s (%s)", user_id[:12], company, startup_id)
            return PipelineExecutionResult.skipped(
                code="lookup_cancelled",
                detail="The lookup was cancelled after Reviewer completed.",
                startup_id=startup_id,
            )
        current_stage = "partner"
        partner_stage_started = time.perf_counter()
        decided = await partner_engine.run_startup(
            startup_id,
            pipeline_run_id=lookup_run_id,
            force_rerun=bool(replace_startup_id),
            bypass_agent_enabled_gate=True,
            startup=handoff_startup,
        )
        metrics.observe_pipeline_stage(
            time.perf_counter() - partner_stage_started,
            pipeline="lookup",
            stage="partner",
            outcome="success" if decided else "incomplete",
        )
        if not decided:
            logger.warning("[%s] On-demand lookup not decided yet: %s", user_id[:12], startup_id)
            message = "Lookup review completed, but the partner decision could not complete after retrying."
            await _mark_lookup_pipeline_failed(storage, startup_id, lookup_run_id, message)
            await _record_lookup_failure(user_id, lid, message)
            metrics.inc_lookup("error")
            return PipelineExecutionResult.stage_failure(
                stage="partner",
                code="partner_stage_failed",
                detail=message,
                recovery_action="Inspect Partner logs and retry the lookup.",
                startup_id=startup_id,
            )
        else:
            await emit("partner", "succeeded", startup_id=startup_id)
            if replace_startup_id:
                await asyncio.to_thread(
                    upsert_pipeline_state,
                    getattr(storage, "_client", None),
                    user_id=user_id,
                    startup_id=startup_id,
                    pipeline_run_id=lookup_run_id,
                    status="writing_memo",
                )
                updated_startup = await asyncio.to_thread(storage.get_startup, startup_id)
                if updated_startup is None:
                    raise RuntimeError("Re-reviewed startup disappeared before memo regeneration")
                regenerated_memo = await asyncio.to_thread(
                    MemoGenerator().generate_memo,
                    updated_startup,
                    for_display=True,
                    tenant_user_id=user_id,
                    fund_thesis=thesis_ctx,
                )
                memo_saved = await asyncio.to_thread(
                    storage.update_startup_partial,
                    startup_id,
                    {"investment_memo_markdown": regenerated_memo},
                )
                if not memo_saved:
                    raise RuntimeError("Regenerated memo could not be persisted")
                await asyncio.to_thread(
                    upsert_pipeline_state,
                    getattr(storage, "_client", None),
                    user_id=user_id,
                    startup_id=startup_id,
                    pipeline_run_id=lookup_run_id,
                    status="ready",
                )
            _notify_startups_changed(user_id, "lookup_partner")
            if lookup_outcome.get("status") == "ALREADY_IN_DEAL_FLOW":
                await _record_lookup_outcome(
                    user_id,
                    lid,
                    status="already_in_deal_flow",
                    startup_id=startup_id,
                    message=lookup_outcome.get("message"),
                )
        evaluation_path = "rerun" if replace_startup_id else "manual_lookup"
        _observe_decision_ready_usage(
            engines.cost_controller,
            before=lookup_usage_before,
            cohort="manual_lookup",
        )
        metrics.inc_evaluation_manifest(path=evaluation_path, outcome="success")
        await emit("completed", "succeeded", startup_id=startup_id)
        logger.info(
            "[%s] On-demand lookup completed for %s (%s) rss_mb_end=%.1f",
            user_id[:12],
            company,
            startup_id,
            _rss_mb(),
        )
        metrics.inc_lookup("success")
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="The company lookup and evaluation completed.",
            startup_id=startup_id,
            projection_id=str((institutional_context or {}).get("opportunity_id") or "").strip() or None,
        )
    except Exception as e:
        metrics.inc_lookup("error")
        logger.exception("[%s] On-demand lookup error (%s): %s", user_id[:12], company, e)
        message = "Lookup failed with an unexpected error. Try again or check server logs."
        if startup_id:
            await _mark_lookup_pipeline_failed(storage, startup_id, lookup_run_id, message)
        await _record_lookup_failure(
            user_id,
            lid,
            message,
        )
        if isinstance(e, EvaluationPrerequisiteError):
            raise
        return PipelineExecutionResult.stage_failure(
            stage=current_stage,
            code=f"lookup_{current_stage}_failed",
            detail=message,
            recovery_action="Inspect lookup logs, correct the stage failure, and retry.",
            startup_id=startup_id,
        )
    finally:
        _close_pipeline_engines(scout_engine, reviewer_engine, partner_engine)
        gc.collect()


async def reprocess_startups_missing_fund_thesis(
    user_id: str,
    *,
    dry_run: bool = False,
    limit: int = 1000,
    evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
    fund_intelligence_repository: Optional[Any] = None,
) -> PipelineExecutionResult:
    """
    Re-run reviewer + partner only for startups that have review_info but no
    review_info.fund_thesis_version_id. Same startup rows; no scout.
    """
    uid = require_user_id(
        user_id, context="reprocess_startups_missing_fund_thesis"
    )
    try:
        if evaluation_prerequisites is None:
            evaluation_prerequisites = await load_evaluation_prerequisites(
                user_id=uid,
                fund_intelligence_repository=fund_intelligence_repository,
            )
        evaluation_prerequisites.require_tenant(
            uid, context="reprocess_startups_missing_fund_thesis"
        )
    except EvaluationPrerequisiteError as exc:
        return PipelineExecutionResult.blocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        )

    use_supabase = env_config.use_supabase_storage()
    if not use_supabase:
        return PipelineExecutionResult.blocked(
            code="supabase_storage_required",
            detail="Thesis reprocessing requires Supabase storage.",
            recovery_action="Set USE_SUPABASE_STORAGE=1 and configure Supabase, then retry.",
        )

    limit = max(1, min(int(limit), 1000))
    try:
        storage = await asyncio.to_thread(_build_storage_sync, uid)
        ids = await asyncio.to_thread(
            storage.get_startups_missing_thesis, limit=limit
        )
    except Exception as exc:
        logger.warning("[%s] Thesis reprocessing storage unavailable: %s", uid[:12], exc)
        return PipelineExecutionResult.blocked(
            code="startup_storage_unavailable",
            detail="Tenant startup storage could not be loaded for thesis reprocessing.",
            recovery_action="Restore Supabase connectivity and retry thesis reprocessing.",
        )

    if dry_run:
        if not await asyncio.to_thread(is_thesis_reprocess_agents_enabled, uid):
            return PipelineExecutionResult.skipped(
                code="reprocess_agents_disabled",
                detail="Thesis reprocessing is disabled because Reviewer and Partner are not enabled.",
                metadata={"dry_run": True, "eligible": len(ids)},
            )
        return PipelineExecutionResult.completed(
            code="reprocess_dry_run_completed",
            detail="Thesis reprocessing eligibility was calculated.",
            metadata={"dry_run": True, "eligible": len(ids)},
        )

    if not ids:
        return PipelineExecutionResult.skipped(
            code="reprocess_no_work",
            detail="No startup required thesis reprocessing.",
            metadata={"processed": 0, "skipped": 0, "failed": 0},
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key.strip():
        return PipelineExecutionResult.blocked(
            code="openai_api_key_required",
            detail="OPENAI_API_KEY is required for thesis reprocessing.",
            recovery_action="Configure OPENAI_API_KEY and retry thesis reprocessing.",
        )

    if not await asyncio.to_thread(is_thesis_reprocess_agents_enabled, uid):
        return PipelineExecutionResult.skipped(
            code="reprocess_agents_disabled",
            detail="Thesis reprocessing is disabled because Reviewer and Partner are not enabled.",
            metadata={"processed": 0, "skipped": len(ids), "failed": 0},
        )

    try:
        settings = await asyncio.to_thread(load_settings, uid, use_cache=False)
    except Exception as exc:
        logger.warning("[%s] Thesis reprocessing settings unavailable: %s", uid[:12], exc)
        return PipelineExecutionResult.blocked(
            code="runtime_settings_unavailable",
            detail="Tenant runtime settings could not be loaded for thesis reprocessing.",
            recovery_action="Restore the settings store and retry thesis reprocessing.",
        )
    try:
        engines = await asyncio.to_thread(
            _build_pipeline_engines,
            user_id=uid,
            storage=storage,
            api_key=api_key,
            settings=settings,
            evaluation_prerequisites=evaluation_prerequisites,
            use_resource_fund_thesis_fallback=False,
        )
    except EvaluationPrerequisiteError as exc:
        return PipelineExecutionResult.blocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        )
    except Exception as exc:
        logger.exception("[%s] Thesis reprocessing engine initialization failed: %s", uid[:12], exc)
        return PipelineExecutionResult.stage_failure(
            stage="initialization",
            code="reprocess_engine_initialization_failed",
            detail="Reprocessing engines could not be initialized from certified inputs.",
            recovery_action="Inspect engine initialization logs, correct the runtime configuration, and retry.",
        )
    reviewer_engine = engines.reviewer_engine
    partner_engine = engines.partner_engine

    processed = 0
    skipped = 0
    failed = 0

    try:
        for sid in ids:
            st = await asyncio.to_thread(storage.get_startup, sid)
            if st is None:
                failed += 1
                continue
            if st.review_info is None:
                skipped += 1
                continue
            vid = getattr(st.review_info, "fund_thesis_version_id", None)
            if vid is not None and str(vid).strip():
                skipped += 1
                continue

            prid = str(uuid4())
            try:
                ok_rev = await reviewer_engine.run_startup(
                    sid,
                    ignore_confidence_threshold=True,
                    pipeline_run_id=prid,
                    force_rerun=True,
                )
                if not ok_rev:
                    failed += 1
                    continue
                ok_p = await partner_engine.run_startup(sid, pipeline_run_id=prid, force_rerun=True)
                if not ok_p:
                    failed += 1
                    continue
                processed += 1
            except Exception:
                logger.exception("[%s] ThesisBackfill failed for startup %s", uid[:12], sid)
                failed += 1
    finally:
        _close_pipeline_engines(
            engines.scout_engine, reviewer_engine, partner_engine
        )

    logger.info(
        "[ThesisBackfill] user_id=%s processed=%s skipped=%s failed=%s",
        uid[:24],
        processed,
        skipped,
        failed,
    )
    counts = {"processed": processed, "skipped": skipped, "failed": failed}
    if failed:
        return PipelineExecutionResult.stage_failure(
            stage="reprocess",
            code="reprocess_stage_failed",
            detail=f"Thesis reprocessing failed for {failed} startup(s).",
            recovery_action="Inspect Reviewer and Partner logs, then retry the failed startups.",
            metadata=counts,
        )
    if processed == 0:
        return PipelineExecutionResult.skipped(
            code="reprocess_no_work",
            detail="No startup required thesis reprocessing.",
            metadata=counts,
        )
    return PipelineExecutionResult.completed(
        code="reprocess_completed",
        detail=f"Thesis reprocessing completed for {processed} startup(s).",
        metadata=counts,
    )
