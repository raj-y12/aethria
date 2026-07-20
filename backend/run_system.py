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
from typing import Any, Optional

from fund_intelligence.repository import FundIntelligenceRepository
from identity.repository import IdentityRepository
from jobs.postgres import DurableJobConfigurationError, create_pool
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState
from pipeline_runner import run_one_pipeline_cycle
from tenant_context import require_user_id


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
        "retrieval_grounding": "\033[38;5;208m",  # orange
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
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one governed pipeline cycle and exit.",
    )
    return parser.parse_args()


async def run_system(
    user_id: Optional[str],
    *,
    once: bool = False,
    identity_repository: Any = None,
    fund_intelligence_repository: Any = None,
) -> PipelineExecutionResult:
    """Run governed cycles through the same prerequisite boundary as every entry path."""
    uid = require_user_id(user_id, context="run_system")

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
    logger.info("Starting governed AETHRIA pipeline user_id=%s", uid)

    owned_pool = None
    try:
        if identity_repository is None or fund_intelligence_repository is None:
            try:
                owned_pool = await create_pool()
            except DurableJobConfigurationError as exc:
                return PipelineExecutionResult.blocked(
                    code="institutional_repository_required",
                    detail=str(exc),
                    recovery_action=(
                        "Configure DATABASE_URL or SUPABASE_DB_URL before running "
                        "the governed pipeline CLI."
                    ),
                )
            except Exception as exc:
                logger.error(
                    "Institutional repository unavailable: %s", type(exc).__name__
                )
                return PipelineExecutionResult.blocked(
                    code="institutional_repository_unavailable",
                    detail="The institutional PostgreSQL repository is unavailable.",
                    recovery_action=(
                        "Restore database connectivity and retry the governed "
                        "pipeline CLI."
                    ),
                )
            identity_repository = identity_repository or IdentityRepository(owned_pool)
            fund_intelligence_repository = (
                fund_intelligence_repository
                or FundIntelligenceRepository(owned_pool)
            )

        while True:
            result = await run_one_pipeline_cycle(
                uid,
                manual_one_shot=True,
                identity_repository=identity_repository,
                fund_intelligence_repository=fund_intelligence_repository,
            )
            if not isinstance(result, PipelineExecutionResult):
                raise RuntimeError("Pipeline runner returned an invalid execution result")
            logger.info(
                "Pipeline execution state=%s code=%s detail=%s recovery_action=%s",
                result.state.value,
                result.code,
                result.detail,
                result.recovery_action or "",
            )
            if once or result.state is not PipelineExecutionState.COMPLETED:
                return result
            await asyncio.sleep(max(1, int(os.getenv("SCOUT_INTERVAL_SECONDS", "300"))))
    finally:
        if owned_pool is not None:
            await owned_pool.close()


def _execution_exit_code(result: PipelineExecutionResult) -> int:
    if result.state in {
        PipelineExecutionState.COMPLETED,
        PipelineExecutionState.SKIPPED,
    }:
        return 0
    if result.state is PipelineExecutionState.BLOCKED:
        return 2
    return 1


if __name__ == "__main__":
    args = _parse_args()
    execution = asyncio.run(run_system(user_id=args.user_id, once=args.once))
    raise SystemExit(_execution_exit_code(execution))
