"""
Scout execution engine.
Runs all Scouts in parallel on a configurable interval.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from scout.scouts import (
    MarketDrivenScout,
    BuilderTechnicalScout,
    PainPointScout,
    ContrarianScout,
)
from scout.schema import ScoutOutput
from utils.storage import Storage
from tenant_context import require_user_id
from utils.settings_loader import is_scouts_enabled
from utils.prompt_version import hash_prompt


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
        cost_controller=None,
        deal_memory=None,
        tenant_user_id: str = "",
        active_thesis: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Scout engine.

        Args:
            tenant_user_id: Explicit Clerk user id (settings, SERP, meta weights).
        """
        inferred = (tenant_user_id or "").strip()
        if not inferred and storage is not None:
            inferred = (getattr(storage, "_user_id", None) or "").strip()
        self.tenant_user_id = require_user_id(inferred, context="ScoutEngine")
        self.api_key = api_key
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.model = model
        self.cost_controller = cost_controller
        self.deal_memory = deal_memory
        self.active_thesis: Optional[Dict[str, Any]] = active_thesis

        uid = self.tenant_user_id
        self.scouts: List[Scout] = [
            MarketDrivenScout(api_key, model=model, tenant_user_id=uid),
            BuilderTechnicalScout(api_key, model=model, tenant_user_id=uid),
            PainPointScout(api_key, model=model, tenant_user_id=uid),
            ContrarianScout(api_key, model=model, tenant_user_id=uid),
        ]
        
        self.backpressure_threshold = int(
            os.getenv("SCOUT_BACKPRESSURE_THRESHOLD", "10")
        )
        self.logger = logging.getLogger("scout.engine")
        self.running = False

    def set_active_thesis(self, thesis: Optional[Dict[str, Any]]) -> None:
        self.active_thesis = thesis
        for s in self.scouts:
            s.set_fund_thesis(thesis)

    def _sync_thesis_to_scouts(self) -> None:
        for s in self.scouts:
            s.set_fund_thesis(self.active_thesis)
    
    async def run_cycle(self, pipeline_run_id: Optional[str] = None) -> List[ScoutOutput]:
        """
        Run one discovery cycle with all Scouts in parallel.
        
        Returns:
            List of valid ScoutOutputs (may be empty if all Scouts fail)
        """
        self.logger.info(f"Starting discovery cycle at {datetime.now().isoformat()}")
        self._sync_thesis_to_scouts()

        # Backpressure: skip discovery when too many unreviewed (let reviewers catch up)
        if self.storage is not None:
            try:
                unreviewed = self.storage.count_unreviewed()
                if unreviewed > self.backpressure_threshold:
                    self.logger.warning(
                        f"Backpressure: {unreviewed} unreviewed exceeds threshold "
                        f"({self.backpressure_threshold}), skipping scout cycle"
                    )
                    return []
            except Exception as e:
                self.logger.debug("Could not get unreviewed count for backpressure: %s", e)
        
        # Check budget before running scouts
        if self.cost_controller:
            allowed, reason = self.cost_controller.check_budget("scout", "scout_engine")
            if not allowed:
                self.logger.warning(f"Scout budget denied: {reason}")
                return []
        
        # Load scout weights for weighted selection
        import random
        try:
            from meta.reweighter import load_weights

            weights = load_weights(self.tenant_user_id)
            scout_type_to_name = {
                "market_driven": "MarketDrivenScout",
                "builder_technical": "BuilderTechnicalScout",
                "pain_point": "PainPointScout",
                "contrarian": "ContrarianScout",
            }
            weight_list = [weights.get(scout_type_to_name.get(s.scout_type, ""), 0.25) for s in self.scouts]
            # Select scouts with weighted probability, minimum 2
            num_to_run = max(2, len(self.scouts))  # default: run all 4
            selected_indices = set()
            if any(w != 0.25 for w in weight_list):
                # Weighted selection: pick scouts_per_cycle with replacement, then deduplicate
                scouts_per_cycle = 4
                choices = random.choices(range(len(self.scouts)), weights=weight_list, k=scouts_per_cycle * 2)
                selected_indices = set()
                for c in choices:
                    selected_indices.add(c)
                    if len(selected_indices) >= scouts_per_cycle:
                        break
                # Ensure minimum 2
                if len(selected_indices) < 2:
                    all_indices = list(range(len(self.scouts)))
                    random.shuffle(all_indices)
                    for idx in all_indices:
                        selected_indices.add(idx)
                        if len(selected_indices) >= 2:
                            break
                selected_scouts = [self.scouts[i] for i in selected_indices]
            else:
                selected_scouts = self.scouts
        except ImportError:
            selected_scouts = self.scouts

        # Set dynamic context from deal memory for each scout
        if self.deal_memory:
            memory_context = self.deal_memory.get_memory_context_for_scout()
            for scout in self.scouts:
                scout.set_dynamic_context(memory_context)
        
        # Run all Scouts in parallel
        tasks = [scout._discover_with_validation() for scout in selected_scouts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect valid outputs
        discoveries: List[ScoutOutput] = []
        for i, result in enumerate(results):
            scout = selected_scouts[i]
            
            if isinstance(result, Exception):
                self.logger.error(
                    f"[{scout.scout_type}] Discovery failed with exception: {result}"
                )
            elif result is None:
                self.logger.warning(f"[{scout.scout_type}] Discovery returned None")
            else:
                # Check for duplicate thesis via deal memory
                if self.deal_memory:
                    thesis = result.get("primary_thesis", "")
                    if self.deal_memory.is_duplicate_thesis(thesis):
                        self.logger.info(
                            f"[{scout.scout_type}] Skipping duplicate thesis: "
                            f"{result['name']}"
                        )
                        continue

                # Stamp prompt_version so downstream storage can persist which prompt produced this discovery
                try:
                    result = dict(result)
                    result["prompt_version"] = hash_prompt(getattr(scout, "system_prompt", ""))
                except Exception:
                    # If hashing fails, leave prompt_version unset
                    result = dict(result)

                discoveries.append(result)
                self.logger.info(
                    f"[{scout.scout_type}] Discovered: {result['name']} "
                    f"(confidence: {result['confidence']:.2f})"
                )
                
                # Record token usage if cost controller exists
                if self.cost_controller:
                    self.cost_controller.record_usage(
                        "scout", scout.scout_type, scout._last_token_usage
                    )
                
                # Persist to storage if available
                if self.storage:
                    try:
                        self.storage.add_discovery(result, pipeline_run_id=pipeline_run_id)
                    except Exception as e:
                        self.logger.error(
                            f"Failed to persist discovery {result.get('id')}: {e}"
                        )
                
                # Record scout discovery in deal memory
                if self.deal_memory:
                    try:
                        self.deal_memory.record_scout_discovery(
                            result.get("sector", ""),
                            result.get("primary_thesis", ""),
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to record in deal memory: {e}")
        
        self.logger.info(
            f"Cycle complete: {len(discoveries)}/{len(self.scouts)} discoveries successful"
        )
        
        return discoveries

    async def run_named_lookup(
        self,
        company_name: str,
        scout_type: str = "market_driven",
        website: Optional[str] = None,
        lookup_query: Optional[str] = None,
        lookup_input_type: Optional[str] = None,
        lookup_id: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Run a focused scout lookup for one specific company and persist it.
        Returns startup_id on success, else None.
        """
        company = (company_name or "").strip()
        if not company:
            return None
        selected = next((s for s in self.scouts if s.scout_type == scout_type), None)
        if selected is None:
            selected = self.scouts[0] if self.scouts else None
        if selected is None:
            return None

        self._sync_thesis_to_scouts()
        result = await selected.discover_company(company, website=website)
        if result is None:
            return None

        try:
            payload = dict(result)
            payload["prompt_version"] = hash_prompt(getattr(selected, "system_prompt", ""))
            payload["origin_type"] = "on_demand_lookup"
            payload["lookup_query"] = (lookup_query or company).strip()
            payload["lookup_input_type"] = (lookup_input_type or "company_name").strip()
            payload["lookup_website"] = (website or "").strip() or None
            if lookup_id and str(lookup_id).strip():
                payload["lookup_id"] = str(lookup_id).strip()
            pr = (pipeline_run_id or "").strip() or None
            sid = payload.get("id")
            if self.storage and pr and sid:
                from pipeline_state import pipeline_stage_log, upsert_pipeline_state

                client = getattr(self.storage, "_client", None)
                uid = getattr(self.storage, "_user_id", None)
                if client and uid:
                    pipeline_stage_log(
                        pr, startup_id=sid, user_id=uid, stage="ingesting", phase="STARTED"
                    )
                    upsert_pipeline_state(
                        client,
                        user_id=uid,
                        startup_id=sid,
                        pipeline_run_id=pr,
                        status="ingesting",
                    )
                    pipeline_stage_log(
                        pr, startup_id=sid, user_id=uid, stage="ingesting", phase="DONE"
                    )
            if self.storage:
                self.storage.add_discovery(payload, pipeline_run_id=pr)
            return payload.get("id")
        except Exception as e:
            self.logger.error("Failed named lookup persistence for %s: %s", company, e)
            return None
    
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
                if not is_scouts_enabled(self.tenant_user_id):
                    self.logger.info("Scouts disabled in settings, skipping cycle")
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue
                cycle_count += 1
                self.logger.info(f"=== Discovery Cycle #{cycle_count} ===")
                from uuid import uuid4

                discoveries = await self.run_cycle(pipeline_run_id=str(uuid4()))
                
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
