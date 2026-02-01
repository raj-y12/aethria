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
from storage import Storage
from settings_loader import is_reviewers_enabled


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
    ):
        """
        Initialize the Reviewer engine.
        
        Args:
            api_key: OpenAI API key
            storage: Storage instance to read/write
            interval_seconds: Time between review cycles
            model: OpenAI model to use (default: gpt-5-nano)
            batch_size: Number of entries to process per cycle
        """
        self.api_key = api_key
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.model = model
        self.batch_size = batch_size
        self.agent_id = "reviewer_v1"  # Default agent ID
        
        # Initialize Reviewer
        self.reviewer = DefaultReviewer(api_key, model=model)
        
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
        
        # Get unreviewed startups
        unreviewed_startups = self.storage.get_unreviewed(limit=self.batch_size)
        
        if not unreviewed_startups:
            self.logger.info("No unreviewed entries found")
            return 0
        
        self.logger.info(f"Found {len(unreviewed_startups)} unreviewed entries")
        
        reviewed_count = 0
        
        # Process each startup
        for startup in unreviewed_startups:
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
