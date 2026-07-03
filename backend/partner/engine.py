"""
Partner execution engine.
Runs continuously, processing reviewed entries and making investment decisions.
"""
import asyncio
import json
import logging
import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from utils.timeutil import utcnow

from partner.decision import PartnerDecisionEngine
from partner.schema import validate_partner_output
from tenant_context import require_user_id
from utils.storage import Storage
from utils.settings_loader import get_runtime_limits, is_partners_enabled
from portfolio.store import PortfolioStore
from pipeline_state import pipeline_stage_log, upsert_pipeline_state
from agent_trace import handoff_quality_from_trace


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
        use_resource_fund_thesis_fallback: bool = True,
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
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.decision_engine = PartnerDecisionEngine(
            use_llm_fallback=use_llm_fallback,
            api_key=api_key,
            portfolio_store=portfolio_store,
            tenant_user_id=self.tenant_user_id,
            use_resource_fund_thesis_fallback=use_resource_fund_thesis_fallback,
        )
        self.fund_thesis: Optional[Dict[str, Any]] = fund_thesis
        # Max undecided to process per cycle (ramp: process a solid batch when backlog is high)
        self.batch_max = int(os.getenv("PARTNER_BATCH_MAX", "20"))

        self.logger = logging.getLogger("partner.engine")
        self.running = False
        self.last_cycle_escalations: int = 0
    
    def close(self) -> None:
        """Release the decision engine's OpenAI client (called at cycle end)."""
        try:
            self.decision_engine.close()
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug("Partner decision engine close failed: %s", exc)

    def _build_entry(self, startup) -> Optional[Dict[str, Any]]:
        """Build an entry dict from a startup object (scout + review fields only)."""
        if startup.review_info is None:
            return None
        scout_info = startup.scout_info
        review_info = startup.review_info
        handoff_quality = handoff_quality_from_trace(getattr(startup, "agent_trace", None))
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
                "est_tam": getattr(scout_info, "est_tam", None),
                "references": getattr(scout_info, "references", None) or [],
                "lookup_website": getattr(scout_info, "lookup_website", None),
                "field_provenance": getattr(scout_info, "field_provenance", None),
            },
            "review": {
                "market_score": review_info.market_score,
                "product_score": review_info.product_score,
                "technical_score": review_info.technical_score,
                "execution_score": review_info.execution_score,
                "defensibility_score": getattr(review_info, "defensibility_score", None),
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
                "derived_verdict": getattr(review_info, "derived_verdict", None),
                "thesis_alignment_score": getattr(review_info, "thesis_alignment_score", None),
                "thesis_matches_fund": getattr(review_info, "thesis_matches_fund", None),
                "thesis_fit_points": getattr(review_info, "thesis_fit_points", None) or [],
                "thesis_deviation_points": getattr(review_info, "thesis_deviation_points", None) or [],
                "thesis_alignment_confidence": getattr(review_info, "thesis_alignment_confidence", None),
                "confidence_adjusted_score": getattr(
                    review_info, "confidence_adjusted_score", None
                ),
                "structured_scoring": getattr(review_info, "structured_scoring", None),
                "structured_signals": getattr(review_info, "structured_signals", None),
                "resolution_notes": getattr(review_info, "resolution_notes", None),
                "disagreement_summary": getattr(review_info, "disagreement_summary", None),
                "aethria_view": (
                    review_info.aethria_view.model_dump(mode="json")
                    if getattr(review_info, "aethria_view", None) is not None
                    else None
                ),
                "reviews": (
                    [sr.model_dump(mode="json") for sr in review_info.reviews]
                    if review_info.reviews
                    else None
                ),
                "handoff_quality": handoff_quality,
            },
        }

    def _get_undecided_entries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get entries that have reviews but no partner decision.
        Returns scout + review dicts — no memo generation.
        """
        undecided_startups = self.storage.get_undecided(limit=limit)
        result: List[Dict[str, Any]] = []
        for startup in undecided_startups:
            entry = self._build_entry(startup)
            if entry is not None:
                result.append(entry)
        return result

    def _entry_from_startup(self, startup) -> Optional[Dict[str, Any]]:
        if startup is None:
            return None
        return self._build_entry(startup)

    def _supabase_client_uid(self) -> Tuple[Any, Optional[str]]:
        return getattr(self.storage, "_client", None), getattr(self.storage, "_user_id", None)

    def _retry_json_fix(self, decision: dict) -> dict:
        """
        One-shot LLM retry to fix JSON structure when validate_partner_output fails.
        Returns the original dict unchanged if no LLM client is available.
        """
        import json as _json
        client = getattr(self.decision_engine, "client", None)
        model = getattr(self.decision_engine, "model", "gpt-4o-mini")
        if client is None:
            return decision
        try:
            raw = _json.dumps(decision, ensure_ascii=False, default=str)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You fix malformed JSON to match a required schema. "
                            "Return ONLY valid JSON — no prose, no markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Fix this JSON so it has all required fields: "
                            "recommendation (INVEST/PASS/MONITOR), confidence (float 0-1), "
                            "thesis, why_this_matters, snapshot (with one_liner), market_insight, "
                            "product_edge, traction_signals (str or null), risks (list of str), "
                            "decision_rationale, next_action, human_review_required (bool).\n\n"
                            f"Input:\n{raw}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2048,
            )
            content = response.choices[0].message.content or ""
            from partner.decision import _parse_llm_json_object
            fixed = _parse_llm_json_object(content)
            if fixed:
                return fixed
        except Exception as e:
            self.logger.warning("JSON fix retry failed: %s", e)
        return decision

    async def _decide_and_save(
        self,
        entry_id: str,
        scout_output: dict,
        review_output: dict,
        pipeline_run_id: Optional[str],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Run partner decision, validate JSON, write to Supabase, update pipeline state.
        No memo generation.
        """
        pr = (pipeline_run_id or "").strip() or None
        client, uid = self._supabase_client_uid()

        # decision_engine.decide() is synchronous and, on the LLM-fallback path,
        # makes a blocking OpenAI call. Run it off the event loop so a partner LLM
        # round-trip never freezes SSE streams or the queue workers — the Scout and
        # Reviewer engines already offload their .create() calls the same way.
        decision = await asyncio.to_thread(
            self.decision_engine.decide,
            scout_output,
            review_output,
            fund_thesis=self.fund_thesis,
        )

        if os.getenv("DEAL_CONTEXT_LOG_PIPELINE", "").strip().lower() in ("1", "true", "yes"):
            try:
                from utils.deal_context import build_deal_context_v1

                ctx = build_deal_context_v1(scout_output, review_output, self.fund_thesis)
                self.logger.info(
                    "deal_context_v1 startup_id=%s ctx=%s",
                    entry_id,
                    json.dumps(ctx, sort_keys=True),
                )
            except Exception as e:
                self.logger.debug("deal_context_v1 log skipped: %s", e)

        # JSON validation with one retry
        try:
            validate_partner_output(decision)
        except ValueError as ve:
            self.logger.warning("Partner output validation failed for %s: %s — retrying", entry_id, ve)
            # _retry_json_fix makes a second blocking OpenAI call — also off-loop.
            decision = await asyncio.to_thread(self._retry_json_fix, decision)
            try:
                validate_partner_output(decision)
            except ValueError as ve2:
                self.logger.error("Partner output invalid after retry for %s: %s", entry_id, ve2)
                if pr and client and uid:
                    upsert_pipeline_state(
                        client, user_id=uid, startup_id=entry_id,
                        pipeline_run_id=pr, status="failed",
                        error=f"invalid output: {ve2}"[:500],
                    )
                return False, decision

        if self.cost_controller:
            tokens_used = 0
            if decision.get("llm_fallback_reason"):
                usage = getattr(self.decision_engine, "_last_token_usage", None)
                if isinstance(usage, dict):
                    total = usage.get("total_tokens")
                    if isinstance(total, int):
                        tokens_used = total
                    else:
                        tokens_used = int(usage.get("prompt_tokens", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
            self.cost_controller.record_usage("partner", "partner", tokens_used=tokens_used)

        from utils.adapters import partner_output_to_partner_info

        partner_info = partner_output_to_partner_info(decision)
        partner_info.partner_agent_id = self.agent_id

        try:
            success = await asyncio.to_thread(
                self.storage.add_partner_decision,
                entry_id,
                partner_info,
                pipeline_run_id=pr,
            )
        except Exception as e:
            self.logger.error("Partner persist failed for %s: %s", entry_id, e, exc_info=True)
            if pr and client and uid:
                upsert_pipeline_state(
                    client, user_id=uid, startup_id=entry_id,
                    pipeline_run_id=pr, status="failed",
                    error=f"persist: {e}"[:500],
                )
            return False, decision

        if not success and pr and client and uid:
            upsert_pipeline_state(
                client, user_id=uid, startup_id=entry_id,
                pipeline_run_id=pr, status="failed",
                error="add_partner_decision returned false",
            )
            return False, decision

        return success, decision

    async def run_cycle(self, pipeline_run_id: Optional[str] = None) -> int:
        """
        Run one decision cycle.
        Processes all undecided entries.
        
        Returns:
            Number of decisions made in this cycle
        """
        self.logger.info(f"Starting decision cycle at {utcnow().isoformat()}")
        if not is_partners_enabled(self.tenant_user_id):
            self.logger.info("Decision cycle skipped (partners disabled in settings)")
            return 0

        # Ramp: process up to batch_max per cycle so we make progress without one huge cycle
        # Sync Supabase I/O off the serving event loop: a blocked loop stalls
        # every in-flight API response and SSE stream.
        undecided_count = await asyncio.to_thread(self.storage.count_undecided)
        try:
            cycle_limit = int(get_runtime_limits(self.tenant_user_id).get("max_agents_per_run", self.batch_max))
        except Exception as e:
            self.logger.warning("Partner runtime limits unavailable, using batch max: %s", e)
            cycle_limit = self.batch_max
        effective_batch_max = min(self.batch_max, max(1, cycle_limit))
        limit = min(effective_batch_max, undecided_count) if undecided_count else None
        undecided = await asyncio.to_thread(self._get_undecided_entries, limit=limit)
        
        if not undecided:
            self.logger.info("No undecided entries found")
            return 0
        
        self.logger.info(f"Found {len(undecided)} entries awaiting partner decision")
        
        decided_count = 0
        self.last_cycle_escalations = 0

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

                success, decision = await self._decide_and_save(
                    entry_id,
                    scout_output,
                    review_output,
                    pipeline_run_id,
                )

                if success and decision:
                    decided_count += 1
                    if decision.get("human_review_required"):
                        self.last_cycle_escalations += 1
                    recommendation = decision.get("recommendation", "UNKNOWN")
                    confidence = decision.get("confidence", 0)
                    self.logger.info(
                        f"Decision for entry {entry_id}: {recommendation} "
                        f"(confidence: {confidence})"
                    )

                    if self.deal_memory and recommendation == "INVEST":
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
        *,
        bypass_agent_enabled_gate: bool = False,
    ) -> bool:
        """
        Make a partner decision for one specific startup id.
        Returns True when decision is saved.

        bypass_agent_enabled_gate: when True, run even if partners are disabled in settings
        (used for occasional on-demand company lookup only).
        """
        startup = await asyncio.to_thread(self.storage.get_startup, startup_id)
        if startup is None:
            self.logger.warning("Startup not found for partner decision: %s", startup_id)
            return False
        if startup.partner_info is not None and not force_rerun:
            self.logger.info("Startup already has partner decision: %s", startup_id)
            return True
        if not bypass_agent_enabled_gate and not is_partners_enabled(self.tenant_user_id):
            self.logger.info("run_startup skipped (partners disabled in settings): %s", startup_id)
            return False
        entry = self._entry_from_startup(startup)
        if entry is None:
            self.logger.info("Startup is not ready for partner decision: %s", startup_id)
            return False
        try:
            success, _ = await self._decide_and_save(
                startup_id,
                entry["scout"],
                entry["review"],
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
