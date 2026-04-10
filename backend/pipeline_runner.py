"""
Run one pipeline cycle (scout → reviewer → partner → portfolio → meta) for a single user.
Used by the per-user agent queue: explicit user_id on every storage path (no run_context).
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
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

from tenant_context import TenantContext
from supabase_doc_store import list_upsert
from utils.settings_loader import load_settings, is_thesis_reprocess_agents_enabled
from supabase_client import get_service_client
from supabase_storage import SupabaseStartupsStorage
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine
from partner.engine import PartnerEngine
from portfolio.store import PortfolioStore
from portfolio.engine import PortfolioEngine
from portfolio.cost_control import CostController
from memory import DealMemory
from meta.agent import MetaAgent
from fund_thesis import FundThesisIncompleteError, FundThesisMissingError, get_active_thesis

logger = logging.getLogger("pipeline_runner")
_visible_logger = logging.getLogger("uvicorn.error")


def _safe_stage_count(storage: SupabaseStartupsStorage, method_name: str, user_id: str) -> Optional[int]:
    """Best-effort counter for stage logging; never raise."""
    try:
        method = getattr(storage, method_name)
        return int(method())
    except Exception as e:
        logger.warning(
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


def _record_lookup_failure(user_id: str, lookup_id: Optional[str], message: str) -> None:
    lid = (lookup_id or "").strip()
    if not lid or not user_id or not str(user_id).strip():
        return
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        return
    uid = user_id.strip()
    text = (message or "Lookup failed.").strip()[:500]
    try:
        list_upsert(
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


async def run_one_pipeline_cycle(user_id: str) -> None:
    """Run one cycle of scout, reviewer, partner, portfolio, and meta for the given user."""
    if not user_id or not user_id.strip():
        logger.warning("run_one_pipeline_cycle: skipped (empty user_id)")
        return
    user_id = user_id.strip()
    tenant = TenantContext(user_id=user_id)
    logger.info(
        "event=tenant_context user_id=%s module=pipeline_cycle",
        tenant.user_id[:24],
    )

    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        logger.info("[%s] Skipping pipeline (USE_SUPABASE_STORAGE not set)", user_id[:12])
        return

    try:
        settings = load_settings(user_id)
    except Exception as e:
        logger.warning("[%s] Pipeline skipped (settings unavailable): %s", user_id[:12], e)
        return
    ac = settings.get("agent_config") or {}
    scouts_enabled = bool(ac.get("scouts_enabled", False))
    reviewers_enabled = bool(ac.get("reviewers_enabled", False))
    partners_enabled = bool(ac.get("partners_enabled", False))
    if not (scouts_enabled or reviewers_enabled or partners_enabled):
        logger.info("[%s] Agents disabled in settings, skipping", user_id[:12])
        return
    _visible_info(
        "[%s] agent gates: scouts=%s reviewers=%s partners=%s",
        user_id[:12],
        scouts_enabled,
        reviewers_enabled,
        partners_enabled,
    )

    try:
        storage = SupabaseStartupsStorage(get_service_client(), user_id)
    except Exception as e:
        logger.warning("[%s] Failed to create storage: %s", user_id[:12], e)
        return

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[%s] OPENAI_API_KEY missing, skipping pipeline", user_id[:12])
        _visible_logger.warning("[%s] Pipeline skipped: OPENAI_API_KEY not set", user_id[:12])
        return

    try:
        svc = get_service_client()
        active = get_active_thesis(svc, user_id)
        if active is None:
            logger.warning("[%s] Pipeline skipped (fund thesis): missing", user_id[:12])
            _visible_logger.warning("[%s] Pipeline skipped: fund thesis missing — create one in Settings", user_id[:12])
            return
        thesis_ctx = active.as_engine_context()
    except FundThesisIncompleteError as e:
        logger.warning("[%s] Pipeline skipped (fund thesis): %s", user_id[:12], e)
        _visible_logger.warning("[%s] Pipeline skipped: fund thesis incomplete — %s", user_id[:12], e)
        return

    cost_budget_enabled = bool((settings.get("cost_budget") or {}).get("enabled", False))
    cost_controller = CostController(user_id=user_id) if cost_budget_enabled else None
    deal_memory = DealMemory(user_id=user_id)
    model = os.getenv("SCOUT_MODEL", "gpt-4o-mini")
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4o-mini")
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
    )

    try:
        pipeline_run_id = str(uuid4())
        logger.info(
            "[%s] pipeline_run_id=%s module=pipeline_cycle",
            user_id[:12],
            pipeline_run_id,
        )
        if scouts_enabled:
            await scout_engine.run_cycle(pipeline_run_id=pipeline_run_id)
        else:
            logger.info("[%s] Scout stage skipped (disabled in settings)", user_id[:12])

        if reviewers_enabled:
            unreviewed_before = _safe_stage_count(storage, "count_unreviewed", user_id)
            _visible_info(
                "[%s] Reviewer stage start: unreviewed_before=%s",
                user_id[:12],
                unreviewed_before,
            )
            reviewed_count = await reviewer_engine.run_cycle(pipeline_run_id=pipeline_run_id)
            reviewer_stats = getattr(reviewer_engine, "last_cycle_stats", {}) or {}
            _visible_info(
                "[%s] Reviewer stage done: reviewed=%s unreviewed_after=%s threshold=%s candidates_seen=%s skipped_low_confidence=%s reason=%s",
                user_id[:12],
                reviewed_count,
                _safe_stage_count(storage, "count_unreviewed", user_id),
                reviewer_stats.get("confidence_threshold"),
                reviewer_stats.get("candidates_seen"),
                reviewer_stats.get("skipped_low_confidence"),
                reviewer_stats.get("reason"),
            )
        else:
            logger.info("[%s] Reviewer stage skipped (disabled in settings)", user_id[:12])

        if partners_enabled:
            undecided_before = _safe_stage_count(storage, "count_undecided", user_id)
            _visible_info(
                "[%s] Partner stage start: undecided_before=%s",
                user_id[:12],
                undecided_before,
            )
            decided_count = await partner_engine.run_cycle(pipeline_run_id=pipeline_run_id)
            _visible_info(
                "[%s] Partner stage done: decided=%s undecided_after=%s",
                user_id[:12],
                decided_count,
                _safe_stage_count(storage, "count_undecided", user_id),
            )
        else:
            logger.info("[%s] Partner stage skipped (disabled in settings)", user_id[:12])

        portfolio_engine = PortfolioEngine(
            discovery_storage=storage,
            portfolio_store=portfolio_store,
            execution_interval=10,
            signal_interval=3600,
            feedback_interval=86400,
            health_interval=3600,
        )
        portfolio_engine.last_execution = datetime.now() - timedelta(days=1)
        portfolio_engine.last_signal = datetime.now() - timedelta(days=1)
        portfolio_engine.last_feedback = datetime.now() - timedelta(days=1)
        portfolio_engine.last_health = datetime.now() - timedelta(days=1)
        await portfolio_engine.run_cycle()

        try:
            meta_agent = MetaAgent(
                scout_engine=scout_engine,
                reviewer_engine=reviewer_engine,
                user_id=user_id,
            )
            await meta_agent.run_cycle()
        except Exception as meta_err:
            logger.warning("[%s] Meta-agent cycle skipped: %s", user_id[:12], meta_err)

        logger.info("[%s] Pipeline cycle completed", user_id[:12])
    except Exception as e:
        logger.exception("[%s] Pipeline cycle error: %s", user_id[:12], e)


async def run_on_demand_lookup(
    user_id: str,
    company_name: str,
    website: Optional[str] = None,
    lookup_query: Optional[str] = None,
    lookup_input_type: Optional[str] = None,
    lookup_id: Optional[str] = None,
) -> Optional[str]:
    """
    Run scout -> reviewer -> partner for one explicit company name.
    """
    if not user_id or not user_id.strip():
        logger.warning("run_on_demand_lookup: skipped (empty user_id)")
        return None
    company = (company_name or "").strip()
    if not company:
        logger.warning("run_on_demand_lookup: skipped (empty company name)")
        return None

    user_id = user_id.strip()
    tenant = TenantContext(user_id=user_id)
    logger.info(
        "event=tenant_context user_id=%s module=on_demand_lookup",
        tenant.user_id[:24],
    )
    lid = (lookup_id or "").strip() or None

    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        logger.info("[%s] Skipping lookup (USE_SUPABASE_STORAGE not set)", user_id[:12])
        _record_lookup_failure(
            user_id,
            lid,
            "On-demand lookup requires Supabase storage (USE_SUPABASE_STORAGE).",
        )
        return None
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[%s] OPENAI_API_KEY missing, skipping lookup", user_id[:12])
        _visible_logger.warning("[%s] Lookup skipped: OPENAI_API_KEY not set", user_id[:12])
        _record_lookup_failure(
            user_id,
            lid,
            "OpenAI API key is not configured; lookup was not run.",
        )
        return None

    try:
        storage = SupabaseStartupsStorage(get_service_client(), user_id)
    except Exception as e:
        logger.warning("[%s] Failed to create storage for lookup: %s", user_id[:12], e)
        _record_lookup_failure(
            user_id,
            lid,
            "Could not connect to storage for this lookup.",
        )
        return None

    try:
        active = get_active_thesis(get_service_client(), user_id)
        if active is None:
            logger.warning("[%s] Lookup skipped (fund thesis): missing", user_id[:12])
            _visible_logger.warning("[%s] Lookup skipped: fund thesis missing — create one in Settings", user_id[:12])
            _record_lookup_failure(
                user_id,
                lid,
                "Fund thesis is missing. Add a thesis in Settings.",
            )
            return None
        thesis_ctx = active.as_engine_context()
    except FundThesisIncompleteError as e:
        logger.warning("[%s] Lookup skipped (fund thesis): %s", user_id[:12], e)
        _visible_logger.warning("[%s] Lookup skipped: fund thesis incomplete — %s", user_id[:12], e)
        _record_lookup_failure(
            user_id,
            lid,
            "Fund thesis could not be loaded or auto-created. Check Supabase and migrations, or add a thesis in Settings.",
        )
        return None

    try:
        settings = load_settings(user_id)
    except Exception as e:
        logger.warning("[%s] settings load failed during lookup; using defaults: %s", user_id[:12], e)
        settings = {"cost_budget": {}}
    cost_budget_enabled = bool((settings.get("cost_budget") or {}).get("enabled", False))
    cost_controller = CostController(user_id=user_id) if cost_budget_enabled else None
    deal_memory = DealMemory(user_id=user_id)
    model = os.getenv("SCOUT_MODEL", "gpt-4o-mini")
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4o-mini")
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
    )

    try:
        lookup_run_id = str(uuid4())
        logger.info(
            "[%s] on_demand_lookup pipeline_run_id=%s",
            user_id[:12],
            lookup_run_id,
        )
        startup_id = await scout_engine.run_named_lookup(
            company_name=company,
            scout_type="market_driven",
            website=website,
            lookup_query=lookup_query,
            lookup_input_type=lookup_input_type,
            lookup_id=lookup_id,
            pipeline_run_id=lookup_run_id,
        )
        if not startup_id:
            logger.warning("[%s] On-demand lookup failed at scout stage: %s", user_id[:12], company)
            _record_lookup_failure(
                user_id,
                lid,
                f'Scout could not complete lookup for "{company}". Try a different name or website.',
            )
            return None
        reviewed = await reviewer_engine.run_startup(
            startup_id,
            ignore_confidence_threshold=True,
            pipeline_run_id=lookup_run_id,
            bypass_agent_enabled_gate=True,
        )
        if not reviewed:
            logger.warning("[%s] On-demand lookup not reviewed: %s", user_id[:12], startup_id)
            return startup_id
        decided = await partner_engine.run_startup(
            startup_id,
            pipeline_run_id=lookup_run_id,
            bypass_agent_enabled_gate=True,
        )
        if not decided:
            logger.warning("[%s] On-demand lookup not decided yet: %s", user_id[:12], startup_id)
        logger.info("[%s] On-demand lookup completed for %s (%s)", user_id[:12], company, startup_id)
        return startup_id
    except Exception as e:
        logger.exception("[%s] On-demand lookup error (%s): %s", user_id[:12], company, e)
        _record_lookup_failure(
            user_id,
            lid,
            "Lookup failed with an unexpected error. Try again or check server logs.",
        )
        return None


async def reprocess_startups_missing_fund_thesis(
    user_id: str,
    *,
    dry_run: bool = False,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Re-run reviewer + partner only for startups that have review_info but no
    review_info.fund_thesis_version_id. Same startup rows; no scout.
    """
    uid = (user_id or "").strip()
    if not uid:
        return {"dry_run": True, "eligible": 0} if dry_run else {"processed": 0, "skipped": 0, "failed": 0}

    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        return {"dry_run": True, "eligible": 0} if dry_run else {"processed": 0, "skipped": 0, "failed": 0}

    limit = max(1, min(int(limit), 1000))
    storage = SupabaseStartupsStorage(get_service_client(), uid)
    ids = storage.get_startups_missing_thesis(limit=limit)

    if dry_run:
        if not is_thesis_reprocess_agents_enabled(uid):
            raise RuntimeError(
                "Thesis reprocessing requires Reviewers and Partners to be enabled in Settings (Pipeline)."
            )
        return {"dry_run": True, "eligible": len(ids)}

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError("OPENAI_API_KEY required for thesis reprocessing")

    if not is_thesis_reprocess_agents_enabled(uid):
        raise RuntimeError(
            "Thesis reprocessing requires Reviewers and Partners to be enabled in Settings (Pipeline)."
        )

    try:
        active = get_active_thesis(get_service_client(), uid)
        if active is None:
            raise RuntimeError("No active thesis")
        thesis_ctx = active.as_engine_context()
    except FundThesisIncompleteError as e:
        raise RuntimeError(str(e)) from e

    try:
        settings = load_settings(uid)
    except Exception:
        settings = {"cost_budget": {}}
    cost_budget_enabled = bool((settings.get("cost_budget") or {}).get("enabled", False))
    cost_controller = CostController(user_id=uid) if cost_budget_enabled else None
    deal_memory = DealMemory(user_id=uid)
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4o-mini")
    use_llm_fallback = os.getenv("PARTNER_USE_LLM", "true").lower() == "true"
    reviewer_batch_size = max(1, int(os.getenv("REVIEWER_BATCH_SIZE", "3")))

    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model=reviewer_model,
        batch_size=reviewer_batch_size,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        tenant_user_id=uid,
        active_thesis=thesis_ctx,
    )
    portfolio_dir = os.getenv("PORTFOLIO_DIR", "data/portfolio")
    portfolio_store = PortfolioStore(data_dir=portfolio_dir, user_id=uid)
    partner_engine = PartnerEngine(
        storage=storage,
        interval_seconds=30,
        use_llm_fallback=use_llm_fallback,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        portfolio_store=portfolio_store,
        tenant_user_id=uid,
        fund_thesis=thesis_ctx,
    )

    processed = 0
    skipped = 0
    failed = 0

    for sid in ids:
        st = storage.get_startup(sid)
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

    logger.info(
        "[ThesisBackfill] user_id=%s processed=%s skipped=%s failed=%s",
        uid[:24],
        processed,
        skipped,
        failed,
    )
    return {"processed": processed, "skipped": skipped, "failed": failed}
