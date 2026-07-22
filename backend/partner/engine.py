"""
Partner execution engine.
Runs continuously, processing reviewed entries and making investment decisions.
"""
import asyncio
import copy
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
from evaluation_v2.prerequisites import EvaluationPrerequisites
from models import EvaluationManifestIdentity
from pipeline_execution import StageExecutionResult


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
        evaluation_prerequisites: Optional[EvaluationPrerequisites] = None,
        model: Optional[str] = None,
        include_deal_context_digest: Optional[bool] = None,
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
            evaluation_prerequisites=evaluation_prerequisites,
            model=model,
            include_deal_context_digest=include_deal_context_digest,
        )
        if evaluation_prerequisites is not None:
            evaluation_prerequisites.require_tenant(
                self.tenant_user_id, context="PartnerEngine"
            )
            if (
                fund_thesis is not None
                and fund_thesis != evaluation_prerequisites.thesis_context
            ):
                raise RuntimeError(
                    "PartnerEngine: fund thesis does not match governed prerequisites"
                )
            fund_thesis = copy.deepcopy(evaluation_prerequisites.thesis_context)
        self.evaluation_prerequisites = evaluation_prerequisites
        self.evaluation_manifest_identity: Optional[
            EvaluationManifestIdentity
        ] = None
        self.fund_thesis: Optional[Dict[str, Any]] = copy.deepcopy(fund_thesis)
        # Max undecided to process per cycle (ramp: process a solid batch when backlog is high)
        self.batch_max = int(os.getenv("PARTNER_BATCH_MAX", "20"))

        self.logger = logging.getLogger("partner.engine")
        self.running = False
        self.last_cycle_escalations: int = 0

    def set_evaluation_manifest_identity(
        self,
        identity: EvaluationManifestIdentity | Dict[str, Any],
    ) -> None:
        """Bind the exact pipeline construction identity once, before execution."""
        validated = EvaluationManifestIdentity.model_validate(
            identity.model_dump(mode="python")
            if isinstance(identity, EvaluationManifestIdentity)
            else dict(identity)
        )
        if validated.dependency_identity.user_id != self.tenant_user_id:
            raise RuntimeError("PartnerEngine manifest identity tenant mismatch")
        if self.evaluation_prerequisites is None:
            raise RuntimeError(
                "PartnerEngine manifest identity requires governed prerequisites"
            )
        if (
            validated.dependency_identity.model_dump(mode="python")
            != self.evaluation_prerequisites.dependency_identity
        ):
            raise RuntimeError(
                "PartnerEngine manifest dependency identity mismatch"
            )
        if self.evaluation_manifest_identity is not None:
            if self.evaluation_manifest_identity != validated:
                raise RuntimeError(
                    "PartnerEngine manifest identity cannot be replaced"
                )
            return
        self.evaluation_manifest_identity = validated
    
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
                # Provenance metadata is engine-owned, never model-repaired.
                fixed["prompt_version"] = decision.get("prompt_version")
                fixed["llm_fallback_reason"] = decision.get(
                    "llm_fallback_reason"
                )
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
        decision, partner_execution_prompt_version = await asyncio.to_thread(
            self.decision_engine.decide_with_execution_identity,
            scout_output,
            review_output,
            fund_thesis=self.fund_thesis,
        )
        persisted_prompt_version = str(decision.get("prompt_version") or "").strip()
        captured_prompt_version = str(
            partner_execution_prompt_version or ""
        ).strip()
        if persisted_prompt_version != captured_prompt_version:
            self.logger.error(
                "Partner prompt provenance mismatch for %s: output did not match "
                "the independently captured engine invocation",
                entry_id,
            )
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="partner execution prompt provenance mismatch",
                )
            return False, decision

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

        if (
            str(decision.get("prompt_version") or "").strip()
            != captured_prompt_version
        ):
            self.logger.error(
                "Partner prompt provenance changed before persistence for %s",
                entry_id,
            )
            if pr and client and uid:
                upsert_pipeline_state(
                    client,
                    user_id=uid,
                    startup_id=entry_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="partner execution prompt provenance changed before persistence",
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
            self.cost_controller.record_usage(
                "partner",
                "partner",
                tokens_used=tokens_used,
                model=getattr(self.decision_engine, "model", "unknown"),
            )

        from utils.adapters import partner_output_to_partner_info

        partner_info = partner_output_to_partner_info(decision)
        partner_info.partner_agent_id = self.agent_id

        try:
            persist_kwargs: Dict[str, Any] = {"pipeline_run_id": pr}
            if self.evaluation_manifest_identity is not None:
                persist_kwargs["evaluation_manifest_identity"] = (
                    self.evaluation_manifest_identity
                )
                persist_kwargs["partner_execution_prompt_version"] = (
                    partner_execution_prompt_version
                )
            success = await asyncio.to_thread(
                self.storage.add_partner_decision,
                entry_id,
                partner_info,
                **persist_kwargs,
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

    async def run_cycle(
        self,
        pipeline_run_id: Optional[str] = None,
        *,
        eligible_startup_ids: Optional[set[str]] = None,
    ) -> StageExecutionResult:
        """
        Run one decision cycle.
        Processes all undecided entries.
        
        Returns a typed, lossless account of every candidate attempted.
        """
        self.logger.info(f"Starting decision cycle at {utcnow().isoformat()}")
        if not is_partners_enabled(self.tenant_user_id):
            self.logger.info("Decision cycle skipped (partners disabled in settings)")
            return StageExecutionResult.skipped_result(
                stage="partner",
                code="partner_disabled",
                detail="The Partner stage is disabled for this tenant.",
            )

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
        limit = (
            min(500, undecided_count)
            if eligible_startup_ids is not None and undecided_count
            else min(effective_batch_max, undecided_count)
            if undecided_count
            else None
        )
        undecided = await asyncio.to_thread(self._get_undecided_entries, limit=limit)
        if eligible_startup_ids is not None:
            undecided = [
                entry for entry in undecided if entry["id"] in eligible_startup_ids
            ][:effective_batch_max]
        
        if not undecided:
            self.logger.info("No undecided entries found")
            return StageExecutionResult.skipped_result(
                stage="partner",
                code="partner_no_eligible_work",
                detail="No reviewed startup is eligible for the Partner stage.",
            )
        
        self.logger.info(f"Found {len(undecided)} entries awaiting partner decision")
        
        decided_count = 0
        failed_count = 0
        blocked_count = 0
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
                        blocked_count += 1
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
                else:
                    self.logger.error(
                        "Partner decision did not persist a complete outcome for %s",
                        entry_id,
                    )
                    failed_count += 1
                    
            except Exception as e:
                self.logger.error(
                    f"Error making decision for entry {entry_id}: {e}",
                    exc_info=True
                )
                failed_count += 1
                continue
        
        self.logger.info(
            f"Decision cycle complete: {decided_count}/{len(undecided)} decisions successful"
        )
        
        attempted_count = len(undecided)
        if failed_count:
            return StageExecutionResult.failed_result(
                stage="partner",
                code="partner_candidate_failures",
                detail=(
                    f"Partner completed {decided_count} of {attempted_count} "
                    "attempted candidates; one or more candidates failed."
                ),
                recovery_action=(
                    "Inspect Partner decision and persistence logs, correct the "
                    "failures, and retry the affected candidates."
                ),
                attempted=attempted_count,
                succeeded=decided_count,
                failed=failed_count,
                blocked=blocked_count,
            )
        if blocked_count:
            if decided_count:
                return StageExecutionResult.failed_result(
                    stage="partner",
                    code="partner_partial_budget_block",
                    detail=(
                        f"Partner completed {decided_count} of {attempted_count} "
                        "attempted candidates before the budget blocked remaining work."
                    ),
                    recovery_action=(
                        "Increase the Partner budget or wait for the budget window "
                        "to reset, then retry the blocked candidates."
                    ),
                    attempted=attempted_count,
                    succeeded=decided_count,
                    failed=0,
                    blocked=blocked_count,
                )
            return StageExecutionResult.blocked_result(
                stage="partner",
                code="partner_budget_blocked",
                detail="Partner budget denied all eligible work in this cycle.",
                recovery_action=(
                    "Increase the Partner budget or wait for the budget window "
                    "to reset, then retry."
                ),
                attempted=attempted_count,
                blocked=blocked_count,
            )
        return StageExecutionResult.completed(
            stage="partner",
            code="partner_completed",
            detail=f"Partner completed {decided_count} eligible candidate(s).",
            attempted=attempted_count,
            succeeded=decided_count,
        )

    async def run_startup(
        self,
        startup_id: str,
        pipeline_run_id: Optional[str] = None,
        force_rerun: bool = False,
        *,
        bypass_agent_enabled_gate: bool = False,
        startup=None,
    ) -> bool:
        """
        Make a partner decision for one specific startup id.
        Returns True when decision is saved.

        bypass_agent_enabled_gate: when True, run even if partners are disabled in settings
        (used for occasional on-demand company lookup only).
        """
        if startup is None:
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
            success, decision = await self._decide_and_save(
                startup_id,
                entry["scout"],
                entry["review"],
                pipeline_run_id,
            )
            if success and decision:
                from utils.adapters import partner_output_to_partner_info

                startup.partner_info = partner_output_to_partner_info(decision)
                startup.update_timestamp()
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
                cycle_count += 1
                self.logger.info(f"=== Decision Cycle #{cycle_count} ===")
                from uuid import uuid4

                result = await self.run_cycle(pipeline_run_id=str(uuid4()))
                self.logger.info(
                    "Partner cycle state=%s code=%s attempted=%s succeeded=%s failed=%s blocked=%s skipped=%s",
                    result.state.value,
                    result.code,
                    result.attempted,
                    result.succeeded,
                    result.failed,
                    result.blocked,
                    result.skipped,
                )
                
                # Wait for next cycle
                if self.running:
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
