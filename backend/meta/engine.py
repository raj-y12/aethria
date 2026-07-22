"""
MetaAgentEngine — standard engine pattern for the Meta-Agent.
Runs on a long cycle (default 24h).
"""
import asyncio
import logging
import os
from typing import Optional

from meta.agent import MetaAgent

logger = logging.getLogger(__name__)


class MetaAgentEngine:
    """Run the Meta-Agent on a configurable interval."""

    def __init__(self, meta_agent: MetaAgent):
        self.meta_agent = meta_agent
        self.interval = int(os.getenv("META_AGENT_INTERVAL_SECONDS", "86400"))
        self.logger = logging.getLogger("meta.engine")
        self.running = False

    async def run_forever(self):
        """Run Meta-Agent continuously."""
        self.running = True
        self.logger.info(
            f"[MetaAgentEngine] Started. Cycle interval: {self.interval}s"
        )
        while self.running:
            try:
                result = await self.meta_agent.run_cycle()
                outcome = result.outcome
                self.logger.info(
                    "Meta cycle state=%s code=%s attempted=%s succeeded=%s failed=%s skipped=%s",
                    outcome.state.value,
                    outcome.code,
                    outcome.attempted,
                    outcome.succeeded,
                    outcome.failed,
                    outcome.skipped,
                )
            except Exception as e:
                self.logger.error(f"[MetaAgentEngine] Cycle error: {e}", exc_info=True)
            if self.running:
                await asyncio.sleep(self.interval)

    def stop(self):
        self.logger.info("[MetaAgentEngine] Stopping...")
        self.running = False
