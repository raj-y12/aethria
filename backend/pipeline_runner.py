"""
Run one pipeline cycle (scout → reviewer → partner → portfolio → meta) for a single user.
Used by the per-user agent queue: when a user logs in and agents are enabled,
we enqueue their user_id and a worker runs this for them.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from run_context import set_run_user_id
from utils.settings_loader import load_settings, is_scouts_enabled, is_reviewers_enabled, is_partners_enabled, is_cost_budget_enabled
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

logger = logging.getLogger("pipeline_runner")


async def run_one_pipeline_cycle(user_id: str) -> None:
    """
    Run one cycle of scout, reviewer, and partner for the given user.
    Sets run context so settings/storage are scoped to this user.
    """
    if not user_id or not user_id.strip():
        logger.warning("run_one_pipeline_cycle: skipped (empty user_id)")
        return
    user_id = user_id.strip()
    set_run_user_id(user_id)

    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    if not use_supabase:
        logger.info("[%s] Skipping pipeline (USE_SUPABASE_STORAGE not set)", user_id[:12])
        return

    settings = load_settings(user_id)
    ac = settings.get("agent_config") or {}
    if not (ac.get("scouts_enabled", True) or ac.get("reviewers_enabled", True) or ac.get("partners_enabled", True)):
        logger.info("[%s] Agents disabled in settings, skipping", user_id[:12])
        return

    try:
        storage = SupabaseStartupsStorage(get_service_client(), user_id)
    except Exception as e:
        logger.warning("[%s] Failed to create storage: %s", user_id[:12], e)
        return

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[%s] OPENAI_API_KEY missing, skipping pipeline", user_id[:12])
        return

    cost_controller = CostController() if is_cost_budget_enabled(user_id) else None
    deal_memory = DealMemory()
    model = os.getenv("SCOUT_MODEL", "gpt-4o-mini")
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-4o-mini")
    use_llm_fallback = os.getenv("PARTNER_USE_LLM", "true").lower() == "true"

    scout_engine = ScoutEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=300,
        model=model,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
    )
    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model=reviewer_model,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
    )
    partner_engine = PartnerEngine(
        storage=storage,
        interval_seconds=30,
        use_llm_fallback=use_llm_fallback,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
    )

    try:
        if is_scouts_enabled(user_id):
            await scout_engine.run_cycle()
        if is_reviewers_enabled(user_id):
            await reviewer_engine.run_cycle()
        if is_partners_enabled(user_id):
            await partner_engine.run_cycle()

        # Portfolio layer: sync partner decisions to portfolio store, run signals, feedback, health
        portfolio_dir = os.getenv("PORTFOLIO_DIR", "data/portfolio")
        portfolio_store = PortfolioStore(data_dir=portfolio_dir)
        portfolio_engine = PortfolioEngine(
            discovery_storage=storage,
            portfolio_store=portfolio_store,
            execution_interval=10,
            signal_interval=3600,
            feedback_interval=86400,
            health_interval=3600,
        )
        # Force first run_cycle to execute all steps (execution, signals, feedback, health)
        portfolio_engine.last_execution = datetime.now() - timedelta(days=1)
        portfolio_engine.last_signal = datetime.now() - timedelta(days=1)
        portfolio_engine.last_feedback = datetime.now() - timedelta(days=1)
        portfolio_engine.last_health = datetime.now() - timedelta(days=1)
        await portfolio_engine.run_cycle()

        # Meta-agent: one cycle to update weights/calibration/reports
        try:
            meta_agent = MetaAgent(scout_engine=scout_engine, reviewer_engine=reviewer_engine)
            await meta_agent.run_cycle()
        except Exception as meta_err:
            logger.warning("[%s] Meta-agent cycle skipped: %s", user_id[:12], meta_err)

        logger.info("[%s] Pipeline cycle completed", user_id[:12])
    except Exception as e:
        logger.exception("[%s] Pipeline cycle error: %s", user_id[:12], e)
