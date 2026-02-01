"""
Scout execution engine.
Runs all Scouts in parallel on a configurable interval.
"""
import asyncio
import logging
import os
from typing import List, Optional
from datetime import datetime

from scout.scouts import (
    MarketDrivenScout,
    BuilderTechnicalScout,
    PainPointScout,
    ContrarianScout,
)
from scout.schema import ScoutOutput
from storage import Storage
from settings_loader import is_scouts_enabled


logger = logging.getLogger(__name__)


class ScoutEngine:
    """
    Execution engine for running multiple Scouts in parallel.
    
    Features:
    - Parallel execution of all Scouts
    - Configurable interval between cycles
    - Clean logging with Scout identity labels
    - Graceful error handling
    """
    
    def __init__(
        self,
        api_key: str,
        storage: Optional[Storage] = None,
        interval_seconds: int = 300,  # 5 minutes default
        model: str = "gpt-5-nano",
    ):
        """
        Initialize the Scout engine.
        
        Args:
            api_key: OpenAI API key
            storage: Optional Storage instance for persistence
            interval_seconds: Time between discovery cycles
            model: OpenAI model to use (default: gpt-5-nano for cost efficiency)
        """
        self.api_key = api_key
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.model = model
        
        # Initialize all Scouts
        self.scouts: List[Scout] = [
            MarketDrivenScout(api_key, model=model),
            BuilderTechnicalScout(api_key, model=model),
            PainPointScout(api_key, model=model),
            ContrarianScout(api_key, model=model),
        ]
        
        self.logger = logging.getLogger("scout.engine")
        self.running = False
    
    async def run_cycle(self) -> List[ScoutOutput]:
        """
        Run one discovery cycle with all Scouts in parallel.
        
        Returns:
            List of valid ScoutOutputs (may be empty if all Scouts fail)
        """
        self.logger.info(f"Starting discovery cycle at {datetime.now().isoformat()}")
        
        # Run all Scouts in parallel
        tasks = [scout._discover_with_validation() for scout in self.scouts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect valid outputs
        discoveries: List[ScoutOutput] = []
        for i, result in enumerate(results):
            scout = self.scouts[i]
            
            if isinstance(result, Exception):
                self.logger.error(
                    f"[{scout.scout_type}] Discovery failed with exception: {result}"
                )
            elif result is None:
                self.logger.warning(f"[{scout.scout_type}] Discovery returned None")
            else:
                discoveries.append(result)
                self.logger.info(
                    f"[{scout.scout_type}] Discovered: {result['name']} "
                    f"(confidence: {result['confidence']:.2f})"
                )
                
                # Persist to storage if available
                if self.storage:
                    try:
                        self.storage.add_discovery(result)
                    except Exception as e:
                        self.logger.error(
                            f"Failed to persist discovery {result.get('id')}: {e}"
                        )
        
        self.logger.info(
            f"Cycle complete: {len(discoveries)}/{len(self.scouts)} discoveries successful"
        )
        
        return discoveries
    
    async def run_forever(self):
        """
        Run Scouts continuously on the configured interval.
        This is the main entry point for production execution.
        """
        self.running = True
        self.logger.info(
            f"Scout engine started. Running {len(self.scouts)} Scouts "
            f"every {self.interval_seconds} seconds"
        )
        
        cycle_count = 0
        
        while self.running:
            try:
                if not is_scouts_enabled():
                    self.logger.info("Scouts disabled in settings, skipping cycle")
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue
                cycle_count += 1
                self.logger.info(f"=== Discovery Cycle #{cycle_count} ===")
                
                discoveries = await self.run_cycle()
                
                # Log discoveries in a structured way
                if discoveries:
                    self.logger.info("Discoveries:")
                    for disc in discoveries:
                        self.logger.info(
                            f"  - [{disc['scout_type']}] {disc['name']}: "
                            f"{disc['one_line']}"
                        )
                
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
        """Stop the Scout engine gracefully."""
        self.logger.info("Stopping Scout engine...")
        self.running = False


async def main():
    """
    Main entry point for running the Scout engine.
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
    interval_seconds = int(os.getenv("SCOUT_INTERVAL_SECONDS", "300"))
    model = os.getenv("SCOUT_MODEL", "gpt-5-nano")
    
    # Initialize storage
    storage = Storage(file_path=storage_path)
    
    # Create and run engine
    engine = ScoutEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=interval_seconds,
        model=model,
    )
    
    try:
        await engine.run_forever()
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Scout engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
