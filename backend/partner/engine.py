"""
Partner execution engine.
Runs continuously, processing reviewed entries and making investment decisions.
"""
import asyncio
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from partner.decision import PartnerDecisionEngine
from partner.schema import validate_partner_output
from storage import Storage
from settings_loader import is_partners_enabled


logger = logging.getLogger(__name__)


class PartnerEngine:
    """
    Execution engine for the Partner layer.
    
    Features:
    - Processes entries with completed reviews but no partner decision
    - Makes rule-based investment decisions
    - Runs continuously on configurable interval
    - Skips entries already decided
    - Logs decisions clearly (YES / NO / MAYBE)
    """
    
    def __init__(
        self,
        storage: Storage,
        interval_seconds: int = 30,  # 30 seconds default (fast processing)
        use_llm_fallback: bool = True,
        agent_id: str = "partner_v1",
    ):
        """
        Initialize the Partner engine.
        
        Args:
            storage: Storage instance to read/write
            interval_seconds: Time between decision cycles
            use_llm_fallback: Whether to use LLM for edge cases
            agent_id: Agent identifier for performance tracking
        """
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.agent_id = agent_id
        self.decision_engine = PartnerDecisionEngine(use_llm_fallback=use_llm_fallback)
        
        self.logger = logging.getLogger("partner.engine")
        self.running = False
    
    def _get_undecided_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get entries that have reviews but no partner decision.
        Includes Scout hypothesis (primary_thesis, key_assumptions, biggest_unknown) and
        Reviewer assumption_feedback for hypothesis-aware decisions. Defaults missing
        fields for backward compatibility with older Reviewer/Scout outputs.
        
        Args:
            limit: Optional limit on number of entries
        
        Returns:
            List of entries ready for partner decision (scout + review dicts)
        """
        undecided_startups = self.storage.get_undecided(limit=limit)
        result: List[Dict[str, Any]] = []
        for startup in undecided_startups:
            if startup.review_info is None:
                continue
            scout_info = startup.scout_info
            review_info = startup.review_info
            result.append({
                "id": startup.startup_id,
                "scout": {
                    "id": startup.startup_id,
                    "name": scout_info.name,
                    "one_line": scout_info.one_line,
                    "sector": scout_info.sector,
                    "problem": scout_info.problem,
                    "solution": scout_info.solution,
                    "target_users": scout_info.target_users,
                    "why_now": scout_info.why_now,
                    "confidence": scout_info.confidence_score,
                    "primary_thesis": getattr(scout_info, "primary_thesis", None),
                    "key_assumptions": getattr(scout_info, "key_assumptions", None),
                    "biggest_unknown": getattr(scout_info, "biggest_unknown", None),
                },
                "review": {
                    "market_score": review_info.market_score,
                    "product_score": review_info.product_score,
                    "technical_score": review_info.technical_score,
                    "execution_score": review_info.execution_score,
                    "overall_summary": review_info.overall_summary,
                    "key_risks": review_info.key_risks,
                    "verdict": review_info.verdict,
                    "assumption_feedback": getattr(review_info, "assumption_feedback", []) or [],
                    "team_analysis": getattr(review_info, "team_analysis", None) or [],
                    "competition_analysis": getattr(review_info, "competition_analysis", None) or [],
                    "business_model_analysis": getattr(review_info, "business_model_analysis", None) or [],
                    "investment_thesis": getattr(review_info, "investment_thesis", None) or [],
                    "risk_mitigation": getattr(review_info, "risk_mitigation", None) or [],
                },
            })
        return result
    
    async def run_cycle(self) -> int:
        """
        Run one decision cycle.
        Processes all undecided entries.
        
        Returns:
            Number of decisions made in this cycle
        """
        self.logger.info(f"Starting decision cycle at {datetime.now().isoformat()}")
        
        # Get undecided entries
        undecided = self._get_undecided_entries()
        
        if not undecided:
            self.logger.info("No undecided entries found")
            return 0
        
        self.logger.info(f"Found {len(undecided)} entries awaiting partner decision")
        
        decided_count = 0
        
        # Process each entry
        for entry in undecided:
            entry_id = entry["id"]
            scout_output = entry["scout"]
            review_output = entry["review"]
            
            try:
                company_name = scout_output.get("name", "Unknown")
                self.logger.info(
                    f"Making decision for entry {entry_id}: {company_name}"
                )
                
                # Make decision (hypothesis-aware; uses assumption_feedback and Scout hypothesis)
                decision = self.decision_engine.decide(scout_output, review_output)
                validate_partner_output(decision)

                # Convert to PartnerInfo and save
                from adapters import partner_output_to_partner_info
                partner_info = partner_output_to_partner_info(decision)
                partner_info.partner_agent_id = self.agent_id
                success = self.storage.add_partner_decision(entry_id, partner_info)
                
                if success:
                    decided_count += 1
                    decision_type = decision.get("decision", "UNKNOWN")
                    conviction = decision.get("conviction_level") or decision.get("confidence", 0)
                    assumption_risks = decision.get("assumption_risks") or []
                    self.logger.info(
                        f"Decision for entry {entry_id}: {decision_type} "
                        f"(conviction: {conviction}/10)"
                    )
                    if assumption_risks:
                        self.logger.info(
                            f"Entry {entry_id} assumption_risks: {assumption_risks}"
                        )
                else:
                    self.logger.error(f"Failed to save decision for entry {entry_id}")
                    
            except Exception as e:
                self.logger.error(
                    f"Error making decision for entry {entry_id}: {e}",
                    exc_info=True
                )
                continue
        
        self.logger.info(
            f"Decision cycle complete: {decided_count}/{len(undecided)} decisions successful"
        )
        
        return decided_count
    
    async def run_forever(self):
        """
        Run Partner continuously on the configured interval.
        This is the main entry point for production execution.
        """
        self.running = True
        self.logger.info(
            f"Partner engine started. Processing undecided entries "
            f"every {self.interval_seconds} seconds"
        )
        
        cycle_count = 0
        
        while self.running:
            try:
                if not is_partners_enabled():
                    self.logger.info("Partners disabled in settings, skipping cycle")
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue
                cycle_count += 1
                self.logger.info(f"=== Decision Cycle #{cycle_count} ===")
                
                decided = await self.run_cycle()
                
                if decided > 0:
                    self.logger.info(f"Made {decided} decisions in this cycle")
                
                # Wait for next cycle
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
        """Stop the Partner engine gracefully."""
        self.logger.info("Stopping Partner engine...")
        self.running = False


async def main():
    """
    Main entry point for running the Partner engine.
    Reads configuration from environment variables.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Get configuration from environment
    storage_path = os.getenv("STORAGE_PATH", "data/startups.json")
    partner_interval = int(os.getenv("PARTNER_INTERVAL_SECONDS", "30"))
    use_llm_fallback = os.getenv("PARTNER_USE_LLM", "true").lower() == "true"
    
    # Initialize
    from storage import Storage
    storage = Storage(file_path=storage_path)
    engine = PartnerEngine(
        storage=storage,
        interval_seconds=partner_interval,
        use_llm_fallback=use_llm_fallback,
    )
    
    try:
        await engine.run_forever()
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Partner engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
