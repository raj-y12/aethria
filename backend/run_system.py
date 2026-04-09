#!/usr/bin/env python3
"""
Run both Scout and Reviewer engines together.

This is the main entry point for running the complete AETHRIA system.
User ID is always explicit: pass --user-id=<clerk_user_id> so agents read/write
that user's startups and settings. No .env default.
"""
import argparse
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from parent directory (project root)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Also try loading from current directory
    load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from typing import Optional

from utils.storage import Storage
from utils.settings_loader import is_cost_budget_enabled
from supabase_client import get_service_client
from supabase_storage import SupabaseStartupsStorage
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine
from partner.engine import PartnerEngine
from portfolio.engine import PortfolioEngine
from portfolio.cost_control import CostController
from memory import DealMemory


class ColorFormatter(logging.Formatter):
    """
    Color-coded logs by subsystem for terminal readability.

    Examples:
    - scout.engine      → cyan
    - reviewer.engine   → magenta
    - partner.engine    → yellow
    - portfolio.engine  → green
    - storage           → blue
    - system / default  → dim white
    """

    RESET = "\033[0m"
    COLORS = {
        "scout.engine": "\033[38;5;45m",      # bright cyan
        "reviewer.engine": "\033[38;5;207m",  # magenta
        "partner.engine": "\033[38;5;220m",   # yellow
        "portfolio.engine": "\033[38;5;40m",  # green
        "storage": "\033[38;5;33m",           # blue
        "serp": "\033[38;5;208m",             # orange
        "system": "\033[38;5;250m",           # grey
    }

    def format(self, record: logging.LogRecord) -> str:
        name = record.name
        # Map child loggers like scout.engine.http to parent color
        color = None
        for key, val in self.COLORS.items():
            if name == key or name.startswith(f"{key}."):
                color = val
                break
        if color is None:
            color = self.COLORS.get("system", "")

        original_name = record.name
        try:
            record.name = f"{color}{original_name}{self.RESET}"
            return super().format(record)
        finally:
            record.name = original_name


def _parse_args():
    parser = argparse.ArgumentParser(description="Run AETHRIA Scout + Reviewer + Partner + Portfolio + Meta-Agent")
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Clerk user ID (JWT 'sub') for this run. Required when USE_SUPABASE_STORAGE=1. Agents read/write this user's startups and settings.",
    )
    return parser.parse_args()


async def run_system(user_id: Optional[str]):
    """Run both Scout and Reviewer engines in parallel. user_id must be set when using Supabase."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Apply color formatter to all root handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(
            ColorFormatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    
    logger = logging.getLogger("system")
    
    # Get configuration from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    storage_path = os.getenv("STORAGE_PATH", "data/startups.json")
    use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
    scout_interval = int(os.getenv("SCOUT_INTERVAL_SECONDS", "300"))
    reviewer_interval = int(os.getenv("REVIEWER_INTERVAL_SECONDS", "60"))
    partner_interval = int(os.getenv("PARTNER_INTERVAL_SECONDS", "30"))
    model = os.getenv("SCOUT_MODEL", "gpt-5-nano")  # gpt-5-nano doesn't exist, using gpt-5-nano
    reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-5-nano")
    use_llm_fallback = os.getenv("PARTNER_USE_LLM", "true").lower() == "true"
    
    # User ID is required when using Supabase (no .env default; always dynamic)
    if use_supabase and not (user_id and user_id.strip()):
        raise ValueError(
            "When USE_SUPABASE_STORAGE=1 you must pass --user-id=<clerk_user_id> "
            "(the Clerk JWT 'sub'). From repo root: python backend/run_system.py --user-id=user_xxx. "
            "Or set AETHRIA_AGENT_USER_ID in .env when using run.py (all-in-one)."
        )
    if user_id and user_id.strip():
        logger.info("Run user_id=%s (explicit tenant for engines and storage)", user_id.strip())

    # Initialize shared storage: Supabase (service role + user_id) or file
    if use_supabase and user_id:
        storage = SupabaseStartupsStorage(get_service_client(), user_id.strip())
        logger.info("Using storage: Supabase (startups table) — user_id=%s", user_id.strip())
    else:
        storage = Storage(file_path=storage_path)
        logger.info("Using storage: file %s", storage_path)
    # Remove startups without references (references are mandatory)
    n_removed = storage.remove_startups_without_references()
    if n_removed:
        logger.info(f"Cleaned {n_removed} startup(s) without references from database")
    
    # Cost controller only when budget enforcement is enabled in settings
    uid = (user_id or "").strip()
    cost_controller = CostController(user_id=uid if uid else None) if is_cost_budget_enabled(uid if uid else None) else None

    mem_uid = uid if uid else "local_agents"
    deal_memory = DealMemory(user_id=mem_uid)

    thesis_ctx = None
    if use_supabase and uid:
        from fund_thesis import FundThesisIncompleteError, FundThesisMissingError, get_active_thesis

        try:
            active = get_active_thesis(get_service_client(), uid)
            if active is None:
                raise ValueError("No active thesis")
            thesis_ctx = active.as_engine_context()
        except FundThesisIncompleteError as e:
            raise ValueError(
                "Could not load fund thesis when USE_SUPABASE_STORAGE=1. "
                "Check Supabase connectivity and fund_thesis migrations."
            ) from e

    scout_engine = ScoutEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=scout_interval,
        model=model,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        tenant_user_id=uid or mem_uid,
        active_thesis=thesis_ctx,
    )

    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=reviewer_interval,
        model=reviewer_model,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        tenant_user_id=uid or mem_uid,
        active_thesis=thesis_ctx,
    )

    portfolio_dir = os.getenv("PORTFOLIO_DIR", "data/portfolio")
    from portfolio.store import PortfolioStore

    portfolio_store = PortfolioStore(data_dir=portfolio_dir, user_id=uid if uid else None)

    partner_engine = PartnerEngine(
        storage=storage,
        interval_seconds=partner_interval,
        use_llm_fallback=use_llm_fallback,
        cost_controller=cost_controller,
        deal_memory=deal_memory,
        portfolio_store=portfolio_store,
        tenant_user_id=uid or mem_uid,
        fund_thesis=thesis_ctx,
    )
    portfolio_engine = PortfolioEngine(
        discovery_storage=storage,
        portfolio_store=portfolio_store,
        execution_interval=10,
        signal_interval=3600,
        feedback_interval=86400,
        health_interval=3600,
    )
    
    # Create Meta-Agent
    from meta.agent import MetaAgent
    from meta.engine import MetaAgentEngine
    meta_agent = MetaAgent(
        scout_engine=scout_engine,
        reviewer_engine=reviewer_engine,
        user_id=uid or mem_uid,
    )
    meta_agent_engine = MetaAgentEngine(meta_agent)

    logger.info("Starting AETHRIA system (Scout + Reviewer + Partner + Portfolio + Meta-Agent layers)")
    logger.info(
        f"Scout interval: {scout_interval}s, "
        f"Reviewer interval: {reviewer_interval}s, "
        f"Partner interval: {partner_interval}s"
    )
    logger.info(f"Partner LLM fallback: {use_llm_fallback}")
    logger.info(f"Portfolio directory: {portfolio_dir}")
    
    # Run all engines in parallel
    try:
        await asyncio.gather(
            scout_engine.run_forever(),
            reviewer_engine.run_forever(),
            partner_engine.run_forever(),
            portfolio_engine.run_forever(),
            meta_agent_engine.run_forever(),
        )
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        scout_engine.stop()
        reviewer_engine.stop()
        partner_engine.stop()
        portfolio_engine.stop()
        meta_agent_engine.stop()
        logger.info("System stopped")


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run_system(user_id=args.user_id))
