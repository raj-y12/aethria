"""
Reviewer execution engine.
Runs continuously, processing unreviewed Scout discoveries.
"""
import asyncio
import logging
import os
from typing import List, Optional
from datetime import datetime

from reviewer.reviewer import DefaultReviewer
from reviewer.skeptical import SkepticalReviewer
from reviewer.opportunist import OpportunistReviewer
from storage import Storage
from settings_loader import is_reviewers_enabled, load_settings


logger = logging.getLogger(__name__)


class ReviewerEngine:
    """
    Execution engine for the Reviewer layer.
    
    Features:
    - Processes unreviewed entries from storage
    - Runs continuously on configurable interval
    - Skips entries already reviewed
    - One LLM call per review
    - Clean logging with Reviewer identity labels
    """
    
    def __init__(
        self,
        api_key: str,
        storage: Storage,
        interval_seconds: int = 60,  # 1 minute default (faster than Scouts)
        model: str = "gpt-5-nano",
        batch_size: int = 1,  # Process one at a time for now
        cost_controller=None,
        deal_memory=None,
    ):
        """
        Initialize the Reviewer engine.
        
        Args:
            api_key: OpenAI API key
            storage: Storage instance to read/write
            interval_seconds: Time between review cycles
            model: OpenAI model to use (default: gpt-5-nano)
            batch_size: Number of entries to process per cycle
            cost_controller: Optional CostController instance for budget enforcement
            deal_memory: Optional DealMemory instance for cross-agent learning
        """
        self.api_key = api_key
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.model = model
        self.batch_size = batch_size
        self.agent_id = "reviewer_v1"  # Default agent ID
        self.cost_controller = cost_controller
        self.deal_memory = deal_memory
        self.backpressure_threshold = int(
            os.getenv("REVIEWER_BACKPRESSURE_THRESHOLD", "10")
        )
        
        # Initialize Reviewers (default + persona reviewers)
        self.reviewer = DefaultReviewer(api_key, model=model)
        self.skeptical_reviewer = SkepticalReviewer(api_key, model=model)
        self.opportunist_reviewer = OpportunistReviewer(api_key, model=model)
        
        self.logger = logging.getLogger("reviewer.engine")
        self.running = False
    
    async def run_cycle(self) -> int:
        """
        Run one review cycle.
        Processes up to batch_size unreviewed entries.
        
        Returns:
            Number of entries reviewed in this cycle
        """
        self.logger.info(f"Starting review cycle at {datetime.now().isoformat()}")
        
        # Check budget before reviewing
        if self.cost_controller:
            allowed, reason = self.cost_controller.check_budget("reviewer", "reviewer_engine")
            if not allowed:
                self.logger.warning(f"Reviewer budget denied: {reason}")
                return 0
        
        # Get unreviewed startups
        unreviewed_startups = self.storage.get_unreviewed(limit=self.batch_size)
        
        if not unreviewed_startups:
            self.logger.info("No unreviewed entries found")
            return 0
        
        # Sort by confidence_score descending (highest confidence first)
        unreviewed_startups.sort(
            key=lambda s: s.scout_info.confidence_score, reverse=True
        )
        
        self.logger.info(f"Found {len(unreviewed_startups)} unreviewed entries")
        
        # Load confidence threshold from settings
        settings = load_settings()
        confidence_threshold = settings.get("agent_config", {}).get("confidence_threshold", 0.5)
        
        reviewed_count = 0
        
        # Process each startup
        for startup in unreviewed_startups:
            confidence_score = startup.scout_info.confidence_score
            if confidence_score < confidence_threshold:
                self.logger.info(
                    f"Below confidence threshold ({confidence_score:.2f} < {confidence_threshold}), "
                    f"skipping {startup.scout_info.name}"
                )
                continue
            entry_id = startup.startup_id
            scout_output: dict = {
                "id": entry_id,
                "name": startup.scout_info.name,
                "one_line": startup.scout_info.one_line,
                "sector": startup.scout_info.sector,
                "problem": startup.scout_info.problem,
                "solution": startup.scout_info.solution,
                "target_users": startup.scout_info.target_users,
                "why_now": startup.scout_info.why_now,
                "confidence": startup.scout_info.confidence_score,
            }
            # Scout hypothesis fields: default to None for backward compatibility
            scout_output["primary_thesis"] = getattr(
                startup.scout_info, "primary_thesis", None
            )
            scout_output["key_assumptions"] = getattr(
                startup.scout_info, "key_assumptions", None
            )
            scout_output["biggest_unknown"] = getattr(
                startup.scout_info, "biggest_unknown", None
            )
            
            try:
                self.logger.info(
                    f"Reviewing entry {entry_id}: {scout_output.get('name', 'Unknown')}"
                )
                
                # Review the discovery
                review_output = await self.reviewer.review(scout_output)
                
                if review_output is None:
                    self.logger.warning(f"Review failed for entry {entry_id}")
                    continue
                
                # Record token usage if cost controller exists
                if self.cost_controller:
                    self.cost_controller.record_usage(
                        "reviewer", self.agent_id, self.reviewer._last_token_usage
                    )
                
                # Convert to ReviewInfo and save
                from adapters import reviewer_output_to_review_info
                review_info = reviewer_output_to_review_info(review_output)
                review_info.reviewer_agent_id = self.agent_id
                success = self.storage.add_review(entry_id, review_info)
                
                if success:
                    reviewed_count += 1
                    verdict = review_output.get("verdict", "UNKNOWN")
                    avg_score = (
                        review_output.get("market_score", 0) +
                        review_output.get("product_score", 0) +
                        review_output.get("technical_score", 0) +
                        review_output.get("execution_score", 0)
                    ) / 4.0
                    
                    self.logger.info(
                        f"Reviewed entry {entry_id}: {verdict} "
                        f"(avg score: {avg_score:.1f}/10)"
                    )
                    
                    # Record negative assumption feedback in deal memory
                    if self.deal_memory:
                        try:
                            negative_keywords = (
                                "weak", "unvalidated", "critical unknown",
                                "could invalidate",
                            )
                            assumption_feedback = review_output.get(
                                "assumption_feedback", []
                            ) or []
                            negative_items = [
                                item for item in assumption_feedback
                                if any(kw in item.lower() for kw in negative_keywords)
                            ]
                            if negative_items:
                                self.deal_memory.record_failed_assumptions(
                                    negative_items
                                )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to record failed assumptions: {e}"
                            )
                else:
                    self.logger.error(f"Failed to save review for entry {entry_id}")
                    
            except Exception as e:
                self.logger.error(
                    f"Error reviewing entry {entry_id}: {e}",
                    exc_info=True
                )
                continue
        
        self.logger.info(
            f"Review cycle complete: {reviewed_count}/{len(unreviewed_startups)} reviews successful"
        )
        
        return reviewed_count
    
    async def run_forever(self):
        """
        Run Reviewer continuously on the configured interval.
        This is the main entry point for production execution.
        """
        self.running = True
        self.logger.info(
            f"Reviewer engine started. Processing unreviewed entries "
            f"every {self.interval_seconds} seconds"
        )
        
        cycle_count = 0
        
        while self.running:
            try:
                if not is_reviewers_enabled():
                    self.logger.info("Reviewers disabled in settings, skipping cycle")
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue

                # Backpressure: skip cycle if too many undecided startups
                undecided_count = self.storage.count_undecided()
                if undecided_count > self.backpressure_threshold:
                    self.logger.warning(
                        f"Backpressure: {undecided_count} undecided startups "
                        f"exceeds threshold ({self.backpressure_threshold}), skipping review cycle"
                    )
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue

                cycle_count += 1
                self.logger.info(f"=== Review Cycle #{cycle_count} ===")
                
                reviewed = await self.run_cycle()
                
                if reviewed > 0:
                    self.logger.info(f"Reviewed {reviewed} entries in this cycle")
                
                # Wait for next cycle
                if self.running:
                    self.logger.info(
                        f"Waiting {self.interval_seconds} seconds until next cycle..."
                    )
                    await asyncio.sleep(self.interval_seconds)
                    
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in run loop: {e}", exc_info=True)
                # Continue running even after errors
                await asyncio.sleep(self.interval_seconds)
    
    def stop(self):
        """Stop the Reviewer engine gracefully."""
        self.logger.info("Stopping Reviewer engine...")
        self.running = False


async def main():
    """
    Main entry point for running the Reviewer engine.
    Reads configuration from environment variables.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Get configuration from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    storage_path = os.getenv("STORAGE_PATH", "data/discoveries.json")
    interval_seconds = int(os.getenv("REVIEWER_INTERVAL_SECONDS", "60"))
    model = os.getenv("REVIEWER_MODEL", "gpt-5-nano")
    
    # Initialize storage
    storage = Storage(file_path=storage_path)
    
    # Create and run engine
    engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=interval_seconds,
        model=model,
    )
    
    try:
        await engine.run_forever()
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Reviewer engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
