"""
Partner execution engine.
Runs continuously, processing reviewed entries and making investment decisions.
"""
import asyncio
import logging
import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from partner.decision import PartnerDecisionEngine
from partner.schema import validate_partner_output
from tenant_context import require_user_id
from utils.storage import Storage
from utils.settings_loader import is_partners_enabled
from portfolio.store import PortfolioStore
from memo_generator import MemoGenerator
from pipeline_state import pipeline_stage_log, upsert_pipeline_state


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
        cost_controller=None,
        portfolio_store: PortfolioStore = None,
        deal_memory=None,
        tenant_user_id: str = "",
        fund_thesis: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Partner engine.

        Args:
            tenant_user_id: Explicit Clerk user id for settings and memo logging.
        """
        inferred = (tenant_user_id or "").strip()
        if not inferred:
            inferred = (getattr(storage, "_user_id", None) or "").strip()
        self.tenant_user_id = require_user_id(inferred, context="PartnerEngine")
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.agent_id = agent_id
        self.cost_controller = cost_controller
        self.deal_memory = deal_memory
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.decision_engine = PartnerDecisionEngine(
            use_llm_fallback=use_llm_fallback,
            api_key=api_key,
            portfolio_store=portfolio_store,
        )
        self.fund_thesis: Optional[Dict[str, Any]] = fund_thesis
        # Max undecided to process per cycle (ramp: process a solid batch when backlog is high)
        self.batch_max = int(os.getenv("PARTNER_BATCH_MAX", "20"))
        
        self.logger = logging.getLogger("partner.engine")
        self.running = False
    
    def _get_undecided_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get entries that have reviews but no partner decision.
        Includes Scout hypothesis (primary_thesis, key_assumptions, biggest_unknown) and
        Reviewer assumption_feedback for hypothesis-aware decisions. Defaults missing
        fields for backward compatibility with older Reviewer/Scout outputs.
        Generates a pre-decision memo for each startup for LLM context.
        
        Args:
            limit: Optional limit on number of entries
        
        Returns:
            List of entries ready for partner decision (scout + review dicts + memo)
        """
        undecided_startups = self.storage.get_undecided(limit=limit)
        memo_gen = MemoGenerator()
        result: List[Dict[str, Any]] = []
        for startup in undecided_startups:
            if startup.review_info is None:
                continue
            scout_info = startup.scout_info
            review_info = startup.review_info
            try:
                memo = memo_gen.generate_memo(
                    startup,
                    for_display=False,
                    tenant_user_id=self.tenant_user_id,
                    fund_thesis=self.fund_thesis,
                )
            except Exception as e:
                self.logger.warning(f"Memo generation failed for {startup.startup_id}: {e}")
                memo = ""
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
                    "funding_stage": getattr(scout_info, "funding_stage", None),
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
                    "score_reasoning": getattr(review_info, "score_reasoning", None) or {},
                    "reviewer_disagreement": getattr(review_info, "reviewer_disagreement", False),
                    "score_variance": getattr(review_info, "score_variance", None),
                },
                "memo": memo,
            })
        return result

    def _entry_from_startup(self, startup) -> Optional[Dict[str, Any]]:
        if startup is None or startup.review_info is None:
            return None
        scout_info = startup.scout_info
        review_info = startup.review_info
        memo_gen = MemoGenerator()
        try:
            memo = memo_gen.generate_memo(
                startup,
                for_display=False,
                tenant_user_id=self.tenant_user_id,
                fund_thesis=self.fund_thesis,
            )
        except Exception as e:
            self.logger.warning("Memo generation failed for %s: %s", startup.startup_id, e)
            memo = ""
        return {
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
                "funding_stage": getattr(scout_info, "funding_stage", None),
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
                "score_reasoning": getattr(review_info, "score_reasoning", None) or {},
                "reviewer_disagreement": getattr(review_info, "reviewer_disagreement", False),
                "score_variance": getattr(review_info, "score_variance", None),
            },
            "memo": memo,
        }

    def _supabase_client_uid(self) -> Tuple[Any, Optional[str]]:
        return getattr(self.storage, "_client", None), getattr(self.storage, "_user_id", None)

    async def _decide_and_save_with_display_memo(
        self,
        entry_id: str,
        scout_output: dict,
        review_output: dict,
        context_memo: str,
        pipeline_run_id: Optional[str],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Run partner decision, generate display memo, single DB write, pipeline state to ready/failed.
        """
        pr = (pipeline_run_id or "").strip() or None
        client, uid = self._supabase_client_uid()

        if pr and client and uid:
            upsert_pipeline_state(
                client,
                user_id=uid,
                startup_id=entry_id,
                pipeline_run_id=pr,
                status="generating_memo",
            )
            pipeline_stage_log(
                pr, startup_id=entry_id, user_id=self.tenant_user_id, stage="generating_memo", phase="STARTED"
            )

        decision = self.decision_engine.decide(
            scout_output,
            review_output,
            context_memo=context_memo,
            fund_thesis=self.fund_thesis,
        )
        validate_partner_output(decision)

        if self.cost_controller:
            tokens_used = 0
            if decision.get("llm_fallback_reason"):
                usage = getattr(self.decision_engine, "_last_token_usage", None)
                if isinstance(usage, dict):
                    total = usage.get("total_tokens")
                    if isinstance(total, int):
                        tokens_used = total
                    else:
                        prompt_tokens = usage.get("prompt_tokens", 0) or 0
                        completion_tokens = usage.get("completion_tokens", 0) or 0
                        tokens_used = int(prompt_tokens) + int(completion_tokens)
            self.cost_controller.record_usage("partner", "partner", tokens_used=tokens_used)

        from utils.adapters import partner_output_to_partner_info

        partner_info = partner_output_to_partner_info(decision)
        partner_info.partner_agent_id = self.agent_id

        st = self.storage.get_startup(entry_id)
        if st is None:
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="startup missing before memo write",
                )
            return False, decision

        st.partner_info = partner_info
        memo_gen = MemoGenerator()
        try:
            display_memo = memo_gen.generate_memo(
                st,
                for_display=True,
                tenant_user_id=self.tenant_user_id,
                fund_thesis=self.fund_thesis,
            )
        except Exception as e:
            self.logger.warning("Display memo generation failed for %s: %s", entry_id, e)
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error=f"memo generation: {e}"[:500],
                )
            return False, decision

        if not (display_memo or "").strip():
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="empty display memo",
                )
            return False, decision

        if pr and client and uid:
            pipeline_stage_log(
                pr, startup_id=entry_id, user_id=self.tenant_user_id, stage="generating_memo", phase="DONE"
            )
            pipeline_stage_log(
                pr, startup_id=entry_id, user_id=self.tenant_user_id, stage="writing_memo", phase="STARTED"
            )
            upsert_pipeline_state(
                client,
                user_id=uid,
                startup_id=entry_id,
                pipeline_run_id=pr,
                status="writing_memo",
            )

        try:
            success = self.storage.add_partner_decision(
                entry_id,
                partner_info,
                investment_memo_markdown=display_memo,
                pipeline_run_id=pr,
            )
        except Exception as e:
            self.logger.error("Partner persist failed for %s: %s", entry_id, e, exc_info=True)
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error=f"persist: {e}"[:500],
                )
            return False, decision

        if not success and pr and client and uid:
            upsert_pipeline_state(
                client,
                user_id=uid,
                startup_id=entry_id,
                pipeline_run_id=pr,
                status="failed",
                error="add_partner_decision returned false",
            )

        return success, decision

    async def run_cycle(self, pipeline_run_id: Optional[str] = None) -> int:
        """
        Run one decision cycle.
        Processes all undecided entries.
        
        Returns:
            Number of decisions made in this cycle
        """
        self.logger.info(f"Starting decision cycle at {datetime.now().isoformat()}")
        
        # Ramp: process up to batch_max per cycle so we make progress without one huge cycle
        undecided_count = self.storage.count_undecided()
        limit = min(self.batch_max, undecided_count) if undecided_count else None
        undecided = self._get_undecided_entries(limit=limit)
        
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
            context_memo = entry.get("memo", "")
            
            try:
                company_name = scout_output.get("name", "Unknown")
                self.logger.info(
                    f"Making decision for entry {entry_id}: {company_name}"
                )

                # Enforce cost/budget limits before invoking PartnerDecisionEngine
                if self.cost_controller:
                    allowed, reason = self.cost_controller.check_budget(
                        "partner", "partner", estimated_tokens=0
                    )
                    if not allowed:
                        self.logger.warning(
                            f"Partner budget denied for entry {entry_id}: {reason}"
                        )
                        continue

                success, decision = await self._decide_and_save_with_display_memo(
                    entry_id,
                    scout_output,
                    review_output,
                    context_memo,
                    pipeline_run_id,
                )

                if success and decision:
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

                    if self.deal_memory and decision_type == "YES":
                        try:
                            self.deal_memory.record_successful_thesis(
                                scout_output.get("primary_thesis", "")
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to record successful thesis: {e}"
                            )
                elif not success:
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

    async def run_startup(
        self,
        startup_id: str,
        pipeline_run_id: Optional[str] = None,
        force_rerun: bool = False,
    ) -> bool:
        """
        Make a partner decision for one specific startup id.
        Returns True when decision is saved.
        """
        startup = self.storage.get_startup(startup_id)
        if startup is None:
            self.logger.warning("Startup not found for partner decision: %s", startup_id)
            return False
        if startup.partner_info is not None and not force_rerun:
            self.logger.info("Startup already has partner decision: %s", startup_id)
            return True
        entry = self._entry_from_startup(startup)
        if entry is None:
            self.logger.info("Startup is not ready for partner decision: %s", startup_id)
            return False
        try:
            success, _ = await self._decide_and_save_with_display_memo(
                startup_id,
                entry["scout"],
                entry["review"],
                entry.get("memo", ""),
                pipeline_run_id,
            )
            return bool(success)
        except Exception as e:
            self.logger.error("Error making partner decision for %s: %s", startup_id, e, exc_info=True)
            return False
    
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
                if not is_partners_enabled(self.tenant_user_id):
                    self.logger.info("Partners disabled in settings, skipping cycle")
                    if self.running:
                        await asyncio.sleep(self.interval_seconds)
                    continue
                cycle_count += 1
                self.logger.info(f"=== Decision Cycle #{cycle_count} ===")
                from uuid import uuid4

                decided = await self.run_cycle(pipeline_run_id=str(uuid4()))
                
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
    from utils.storage import Storage
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
