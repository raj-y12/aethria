"""
Reviewer execution engine.
Runs continuously, processing unreviewed Scout discoveries.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from reviewer.reviewer import DefaultReviewer
from reviewer.skeptical import SkepticalReviewer
from reviewer.opportunist import OpportunistReviewer
from tenant_context import require_user_id
from fund_thesis import rule_based_thesis_alignment, thesis_context_has_embeddings
from pipeline_state import upsert_pipeline_state
from utils.storage import Storage
from utils.settings_loader import is_reviewers_enabled, load_settings


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
        tenant_user_id: str = "",
        active_thesis: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Reviewer engine.

        Args:
            tenant_user_id: Explicit Clerk user id for settings and calibration.
        """
        inferred = (tenant_user_id or "").strip()
        if not inferred:
            inferred = (getattr(storage, "_user_id", None) or "").strip()
        self.tenant_user_id = require_user_id(inferred, context="ReviewerEngine")
        self.api_key = api_key
        self.storage = storage
        self.interval_seconds = interval_seconds
        self.model = model
        self.batch_size = batch_size
        self.agent_id = "reviewer_v1"  # Default agent ID
        self.cost_controller = cost_controller
        self.deal_memory = deal_memory
        self.active_thesis: Optional[Dict[str, Any]] = active_thesis
        self.backpressure_threshold = int(
            os.getenv("REVIEWER_BACKPRESSURE_THRESHOLD", "10")
        )
        # Ramp-up: when unreviewed backlog is high, process more per cycle
        self.ramp_threshold = int(os.getenv("REVIEWER_RAMP_THRESHOLD", "5"))
        self.ramp_batch_max = int(os.getenv("REVIEWER_RAMP_BATCH_MAX", "5"))
        
        # Initialize Reviewers (default + persona reviewers)
        self.reviewer = DefaultReviewer(api_key, model=model)
        self.skeptical_reviewer = SkepticalReviewer(api_key, model=model)
        self.opportunist_reviewer = OpportunistReviewer(api_key, model=model)
        
        self.logger = logging.getLogger("reviewer.engine")
        self.running = False

    def set_active_thesis(self, thesis: Optional[Dict[str, Any]]) -> None:
        self.active_thesis = thesis
        self._sync_thesis_to_reviewers()

    def _sync_thesis_to_reviewers(self) -> None:
        t = self.active_thesis
        self.reviewer.set_fund_thesis(t)
        self.skeptical_reviewer.set_fund_thesis(t)
        self.opportunist_reviewer.set_fund_thesis(t)
    
    def _compute_consensus(self, results: list) -> dict:
        """
        Compute consensus verdict, disagreement flag, and score variance from multiple reviewer results.
        """
        verdicts = [r.get("verdict", "MEDIUM") for r in results]
        from collections import Counter
        verdict_counts = Counter(verdicts)
        consensus_verdict = verdict_counts.most_common(1)[0][0]
        reviewer_disagreement = len(set(verdicts)) > 1

        score_fields = ["market_score", "product_score", "technical_score", "execution_score"]
        score_variance = {}
        for field in score_fields:
            values = [r.get(field, 0) for r in results]
            if len(values) > 1:
                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)
                score_variance[field] = round(variance, 2)

        return {
            "consensus_verdict": consensus_verdict,
            "reviewer_disagreement": reviewer_disagreement,
            "score_variance": score_variance,
        }

    @staticmethod
    def _mean_round_score(values: list) -> int:
        nums = [int(v) for v in values if isinstance(v, (int, float))]
        if not nums:
            return 5
        return int(round(sum(nums) / len(nums)))

    def _blend_numeric_scores_into_primary(self, primary: dict, all_results: list) -> None:
        """Deterministic dimension scores: integer mean across successful reviewers."""
        dims = ["market_score", "product_score", "technical_score", "execution_score"]
        for d in dims:
            primary[d] = self._mean_round_score([r.get(d) for r in all_results])
        defs = [r.get("defensibility_score") for r in all_results if r.get("defensibility_score") is not None]
        if defs:
            primary["defensibility_score"] = self._mean_round_score(defs)

    def _apply_rule_based_thesis_alignment(self, review_output: dict, scout_output: dict) -> None:
        """When thesis has no embeddings, set alignment from deterministic rules (no extra API calls)."""
        t = self.active_thesis
        if not t or not t.get("version_id"):
            return
        if thesis_context_has_embeddings(t):
            return
        pj = t.get("parsed_json") if isinstance(t.get("parsed_json"), dict) else {}
        review_output.update(rule_based_thesis_alignment(scout_output, pj))

    def _apply_resource_fund_thesis_alignment(
        self,
        review_output: dict,
        scout_output: dict,
        startup_id: str,
    ) -> None:
        """Non-blocking resource thesis lens score; stored only; does not change rubric scores."""
        try:
            from core.fund_thesis_resolver import compute_and_log_alignment

            emb_opt = None
            ctx = self.active_thesis
            if ctx and thesis_context_has_embeddings(ctx):
                te = ctx.get("embedding")
                if isinstance(te, list) and te:
                    emb_opt = (None, te)
            score = compute_and_log_alignment(startup_id, scout_output, emb_opt)
            review_output["fund_thesis_alignment_score"] = round(float(score), 4)
        except Exception as e:
            self.logger.debug("resource fund thesis alignment skipped: %s", e)

    async def run_cycle(self, pipeline_run_id: Optional[str] = None) -> int:
        """
        Run one review cycle.
        Processes up to batch_size unreviewed entries.
        Runs all 3 reviewer personas in parallel for each startup.
        
        Returns:
            Number of entries reviewed in this cycle
        """
        self.logger.info(f"Starting review cycle at {datetime.now().isoformat()}")
        self._sync_thesis_to_reviewers()

        # Check budget before reviewing
        if self.cost_controller:
            allowed, reason = self.cost_controller.check_budget("reviewer", "reviewer_engine")
            if not allowed:
                self.logger.warning(f"Reviewer budget denied: {reason}")
                return 0
        
        # Ramp-up: process more per cycle when unreviewed backlog is high
        unreviewed_count = self.storage.count_unreviewed()
        if unreviewed_count > self.ramp_threshold:
            effective_batch = min(self.ramp_batch_max, unreviewed_count)
            self.logger.info(
                f"Ramp-up: {unreviewed_count} unreviewed > {self.ramp_threshold}, "
                f"processing up to {effective_batch} this cycle"
            )
        else:
            effective_batch = min(self.batch_size, unreviewed_count) if unreviewed_count else 0
        unreviewed_startups = self.storage.get_unreviewed(limit=effective_batch)
        
        if not unreviewed_startups:
            self.logger.info("No unreviewed entries found")
            return 0
        
        # Sort by confidence_score descending (highest confidence first)
        unreviewed_startups.sort(
            key=lambda s: s.scout_info.confidence_score, reverse=True
        )
        
        self.logger.info(f"Found {len(unreviewed_startups)} unreviewed entries")
        
        # Load confidence threshold from settings
        settings = load_settings(self.tenant_user_id)
        confidence_threshold = settings.get("agent_config", {}).get("confidence_threshold", 0.5)

        # Apply calibration override if present
        try:
            from meta.calibrator import load_calibration_state
            cal_state = load_calibration_state(self.tenant_user_id)
            ct_override = cal_state.get("confidence_threshold_override")
            if ct_override is not None:
                confidence_threshold = ct_override
                self.logger.debug(f"Using calibration override: confidence_threshold={ct_override}")
        except ImportError:
            pass

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
                    f"Reviewing entry {entry_id}: {scout_output.get('name', 'Unknown')} "
                    f"with 3 reviewer personas"
                )
                
                # Run all 3 reviewers in parallel
                default_task = self.reviewer.review(scout_output)
                skeptical_task = self.skeptical_reviewer.review(scout_output)
                opportunist_task = self.opportunist_reviewer.review(scout_output)
                
                results = await asyncio.gather(
                    default_task, skeptical_task, opportunist_task,
                    return_exceptions=True,
                )
                
                # Collect successful results
                reviewer_types = ["DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer"]
                successful_results = []
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        self.logger.warning(
                            f"{reviewer_types[i]} reviewer failed for {entry_id}: {res}"
                        )
                    elif res is not None:
                        res["reviewer_type"] = reviewer_types[i]
                        successful_results.append(res)
                
                if not successful_results:
                    self.logger.warning(f"All reviewers failed for entry {entry_id}")
                    pr = (pipeline_run_id or "").strip() or None
                    client = getattr(self.storage, "_client", None)
                    uid = getattr(self.storage, "_user_id", None)
                    if pr and client and uid:
                        upsert_pipeline_state(
                            client,
                            user_id=uid,
                            startup_id=entry_id,
                            pipeline_run_id=pr,
                            status="failed",
                            error="all reviewers failed",
                        )
                    continue
                
                # Primary narrative/summary: DefaultReviewer (types are set to class names above)
                default_results = [
                    r for r in successful_results if r.get("reviewer_type") == "DefaultReviewer"
                ]
                if default_results:
                    review_output = dict(default_results[0])
                else:
                    review_output = dict(successful_results[0])

                self._blend_numeric_scores_into_primary(review_output, successful_results)
                if self.active_thesis and self.active_thesis.get("version_id"):
                    review_output["fund_thesis_version_id"] = self.active_thesis["version_id"]
                self._apply_rule_based_thesis_alignment(review_output, scout_output)
                self._apply_resource_fund_thesis_alignment(
                    review_output, scout_output, entry_id
                )

                # Record token usage if cost controller exists (sum all persona calls)
                if self.cost_controller:
                    total_tok = (
                        int(getattr(self.reviewer, "_last_token_usage", 0) or 0)
                        + int(getattr(self.skeptical_reviewer, "_last_token_usage", 0) or 0)
                        + int(getattr(self.opportunist_reviewer, "_last_token_usage", 0) or 0)
                    )
                    self.cost_controller.record_usage("reviewer", self.agent_id, total_tok)
                
                # Compute consensus across all successful results
                consensus = self._compute_consensus(successful_results)
                
                # Build SingleReview list for storage
                from models import SingleReview
                single_reviews = []
                type_map = {
                    "default": "DefaultReviewer",
                    "skeptical": "SkepticalReviewer",
                    "opportunist": "OpportunistReviewer",
                }
                for r in successful_results:
                    raw_type = r.get("reviewer_type", "DefaultReviewer")
                    reviewer_label = type_map.get(raw_type, raw_type)
                    if reviewer_label not in (
                        "DefaultReviewer",
                        "SkepticalReviewer",
                        "OpportunistReviewer",
                    ):
                        reviewer_label = "DefaultReviewer"
                    single_reviews.append(SingleReview(
                        reviewer_type=reviewer_label,
                        market_score=r.get("market_score", 5),
                        product_score=r.get("product_score", 5),
                        technical_score=r.get("technical_score", 5),
                        execution_score=r.get("execution_score", 5),
                        defensibility_score=r.get("defensibility_score"),
                        overall_summary=r.get("overall_summary", ""),
                        key_risks=r.get("key_risks", []),
                        verdict=r.get("verdict", "MEDIUM"),
                        diligence_red_flags=r.get("diligence_red_flags", []),
                        assumption_feedback=r.get("assumption_feedback", []),
                        team_analysis=r.get("team_analysis") or None,
                        competition_analysis=r.get("competition_analysis") or None,
                        business_model_analysis=r.get("business_model_analysis") or None,
                        investment_thesis=r.get("investment_thesis") or None,
                        risk_mitigation=r.get("risk_mitigation") or None,
                        score_reasoning=r.get("score_reasoning") or None,
                        prompt_version=r.get("prompt_version"),
                    ))
                
                # Convert to ReviewInfo and save (primary fields from default reviewer)
                from utils.adapters import reviewer_output_to_review_info
                review_info = reviewer_output_to_review_info(review_output)
                review_info.reviewer_agent_id = self.agent_id
                review_info.reviews = single_reviews
                review_info.consensus_verdict = consensus["consensus_verdict"]
                review_info.reviewer_disagreement = consensus["reviewer_disagreement"]
                review_info.score_variance = consensus["score_variance"]
                
                success = self.storage.add_review(
                    entry_id, review_info, pipeline_run_id=pipeline_run_id
                )
                
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
                        f"(avg score: {avg_score:.1f}/10, "
                        f"consensus: {consensus['consensus_verdict']}, "
                        f"disagreement: {consensus['reviewer_disagreement']})"
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

    async def run_startup(
        self,
        startup_id: str,
        ignore_confidence_threshold: bool = False,
        pipeline_run_id: Optional[str] = None,
        force_rerun: bool = False,
    ) -> bool:
        """
        Review one specific startup id.
        Returns True when a review is saved.
        """
        startup = self.storage.get_startup(startup_id)
        if startup is None:
            self.logger.warning("Startup not found for review: %s", startup_id)
            return False
        if startup.review_info is not None and not force_rerun:
            self.logger.info("Startup already reviewed: %s", startup_id)
            return True

        settings = load_settings(self.tenant_user_id)
        confidence_threshold = settings.get("agent_config", {}).get("confidence_threshold", 0.5)
        try:
            from meta.calibrator import load_calibration_state
            cal_state = load_calibration_state(self.tenant_user_id)
            ct_override = cal_state.get("confidence_threshold_override")
            if ct_override is not None:
                confidence_threshold = ct_override
        except ImportError:
            pass

        self._sync_thesis_to_reviewers()

        confidence_score = startup.scout_info.confidence_score
        if not ignore_confidence_threshold and confidence_score < confidence_threshold:
            self.logger.info(
                "Below confidence threshold for startup %s (%.2f < %s)",
                startup_id,
                confidence_score,
                confidence_threshold,
            )
            return False

        scout_output: dict = {
            "id": startup.startup_id,
            "name": startup.scout_info.name,
            "one_line": startup.scout_info.one_line,
            "sector": startup.scout_info.sector,
            "problem": startup.scout_info.problem,
            "solution": startup.scout_info.solution,
            "target_users": startup.scout_info.target_users,
            "why_now": startup.scout_info.why_now,
            "confidence": startup.scout_info.confidence_score,
            "primary_thesis": getattr(startup.scout_info, "primary_thesis", None),
            "key_assumptions": getattr(startup.scout_info, "key_assumptions", None),
            "biggest_unknown": getattr(startup.scout_info, "biggest_unknown", None),
        }

        try:
            default_task = self.reviewer.review(scout_output)
            skeptical_task = self.skeptical_reviewer.review(scout_output)
            opportunist_task = self.opportunist_reviewer.review(scout_output)
            results = await asyncio.gather(
                default_task, skeptical_task, opportunist_task,
                return_exceptions=True,
            )
            reviewer_types = ["DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer"]
            successful_results = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    self.logger.warning("%s reviewer failed for %s: %s", reviewer_types[i], startup_id, res)
                elif res is not None:
                    res["reviewer_type"] = reviewer_types[i]
                    successful_results.append(res)
            if not successful_results:
                self.logger.warning("All reviewers failed for startup %s", startup_id)
                return False

            default_results = [
                r for r in successful_results if r.get("reviewer_type") == "DefaultReviewer"
            ]
            if default_results:
                review_output = dict(default_results[0])
            else:
                review_output = dict(successful_results[0])
            self._blend_numeric_scores_into_primary(review_output, successful_results)
            if self.active_thesis and self.active_thesis.get("version_id"):
                review_output["fund_thesis_version_id"] = self.active_thesis["version_id"]
            self._apply_rule_based_thesis_alignment(review_output, scout_output)
            self._apply_resource_fund_thesis_alignment(
                review_output, scout_output, startup_id
            )
            consensus = self._compute_consensus(successful_results)

            from models import SingleReview
            from utils.adapters import reviewer_output_to_review_info
            single_reviews = []
            type_map = {
                "default": "DefaultReviewer",
                "skeptical": "SkepticalReviewer",
                "opportunist": "OpportunistReviewer",
            }
            for r in successful_results:
                raw_type = r.get("reviewer_type", "DefaultReviewer")
                reviewer_label = type_map.get(raw_type, raw_type)
                if reviewer_label not in (
                    "DefaultReviewer",
                    "SkepticalReviewer",
                    "OpportunistReviewer",
                ):
                    reviewer_label = "DefaultReviewer"
                single_reviews.append(SingleReview(
                    reviewer_type=reviewer_label,
                    market_score=r.get("market_score", 5),
                    product_score=r.get("product_score", 5),
                    technical_score=r.get("technical_score", 5),
                    execution_score=r.get("execution_score", 5),
                    defensibility_score=r.get("defensibility_score"),
                    overall_summary=r.get("overall_summary", ""),
                    key_risks=r.get("key_risks", []),
                    verdict=r.get("verdict", "MEDIUM"),
                    diligence_red_flags=r.get("diligence_red_flags", []),
                    assumption_feedback=r.get("assumption_feedback", []),
                    team_analysis=r.get("team_analysis") or None,
                    competition_analysis=r.get("competition_analysis") or None,
                    business_model_analysis=r.get("business_model_analysis") or None,
                    investment_thesis=r.get("investment_thesis") or None,
                    risk_mitigation=r.get("risk_mitigation") or None,
                    score_reasoning=r.get("score_reasoning") or None,
                    prompt_version=r.get("prompt_version"),
                ))

            review_info = reviewer_output_to_review_info(review_output)
            review_info.reviewer_agent_id = self.agent_id
            review_info.reviews = single_reviews
            review_info.consensus_verdict = consensus["consensus_verdict"]
            review_info.reviewer_disagreement = consensus["reviewer_disagreement"]
            review_info.score_variance = consensus["score_variance"]
            if self.cost_controller:
                total_tok = (
                    int(getattr(self.reviewer, "_last_token_usage", 0) or 0)
                    + int(getattr(self.skeptical_reviewer, "_last_token_usage", 0) or 0)
                    + int(getattr(self.opportunist_reviewer, "_last_token_usage", 0) or 0)
                )
                self.cost_controller.record_usage("reviewer", self.agent_id, total_tok)
            return bool(
                self.storage.add_review(
                    startup_id, review_info, pipeline_run_id=pipeline_run_id
                )
            )
        except Exception as e:
            self.logger.error("Error reviewing startup %s: %s", startup_id, e, exc_info=True)
            return False
    
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
                if not is_reviewers_enabled(self.tenant_user_id):
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
                from uuid import uuid4

                reviewed = await self.run_cycle(pipeline_run_id=str(uuid4()))
                
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
