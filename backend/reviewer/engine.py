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
from utils.scoring import DEFAULT_SCORE_SOURCE, compute_overall_score, enrich_scores
from services.scoring import DeterministicScoringEngine
from services.reviewer_resolution import apply_resolution_to_primary
from reviewer.aethria_view import build_aethria_view
from utils.reviewer_gap_retrieval import enrich_scout_for_reviewer_llm


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
        self.use_structured_scoring = os.getenv("USE_STRUCTURED_SCORING", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        self.structured_scoring_engine = DeterministicScoringEngine() if self.use_structured_scoring else None
        
        # Initialize Reviewers (default + persona reviewers)
        tid = self.tenant_user_id
        self.reviewer = DefaultReviewer(api_key, model=model, tenant_user_id=tid)
        self.skeptical_reviewer = SkepticalReviewer(api_key, model=model, tenant_user_id=tid)
        self.opportunist_reviewer = OpportunistReviewer(api_key, model=model, tenant_user_id=tid)
        
        self.logger = logging.getLogger("reviewer.engine")
        self.running = False
        self.last_cycle_stats: Dict[str, Any] = {}

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
    def _build_scout_output_payload(startup) -> dict:
        """
        Full scout facts for reviewer + deterministic scorer (matches ScoutInfo on disk).
        """
        si = startup.scout_info
        sid = startup.startup_id
        refs = getattr(si, "references", None)
        if not isinstance(refs, list):
            refs = []
        out: Dict[str, Any] = {
            "id": sid,
            "name": si.name,
            "one_line": si.one_line,
            "sector": si.sector,
            "problem": si.problem,
            "solution": si.solution,
            "target_users": si.target_users,
            "why_now": si.why_now,
            "confidence": si.confidence_score,
            "scout_type": si.scout_type,
            "est_tam": getattr(si, "est_tam", None),
            "funding_stage": getattr(si, "funding_stage", None),
            "references": refs,
            "primary_thesis": getattr(si, "primary_thesis", None),
            "key_assumptions": getattr(si, "key_assumptions", None),
            "biggest_unknown": getattr(si, "biggest_unknown", None),
        }
        for opt in ("lookup_id", "lookup_query", "lookup_website", "origin_type"):
            v = getattr(si, opt, None)
            if v is not None and v != "":
                out[opt] = v
        return out

    def _reviewer_for_persona(self, persona: str):
        m = {
            "DefaultReviewer": self.reviewer,
            "SkepticalReviewer": self.skeptical_reviewer,
            "OpportunistReviewer": self.opportunist_reviewer,
        }
        r = m.get(persona)
        if r is None:
            raise ValueError(f"unknown reviewer persona: {persona}")
        return r

    async def preview_persona_review(
        self,
        persona: str,
        scout_output: dict,
        candidate_system_prompt: str,
    ) -> Optional[dict]:
        """
        Run one reviewer persona with a candidate system prompt; does not persist.
        Restores the reviewer's previous SYSTEM_PROMPT in a finally block.
        """
        rev = self._reviewer_for_persona(persona)
        prev_prompt = rev.SYSTEM_PROMPT
        try:
            rev.set_prompt(candidate_system_prompt)
            scout_for_llm = enrich_scout_for_reviewer_llm(scout_output, self.tenant_user_id)
            res = await rev.review(scout_for_llm)
            if res is None:
                return None
            out = dict(res)
            out["reviewer_type"] = persona
            if self.use_structured_scoring:
                out = self._apply_structured_scoring(scout_output, out)
            self._derive_verdict_from_scores(out)
            return out
        finally:
            rev.set_prompt(prev_prompt)

    @staticmethod
    def _mean_round_score(values: list) -> int:
        nums = [int(v) for v in values if isinstance(v, (int, float))]
        if not nums:
            return 5
        return int(round(sum(nums) / len(nums)))

    def _blend_numeric_scores_into_primary(self, primary: dict, all_results: list) -> None:
        """Deterministic dimension scores: integer mean across reviewers.
        Defensibility uses 1.5x weight for SkepticalReviewer (Weighted Skepticism).
        Also computes confidence_adjusted_score = S_bar × (1 − reviewer_delta/10).
        """
        core_dims = ["market_score", "product_score", "technical_score", "execution_score"]
        for d in core_dims:
            primary[d] = self._mean_round_score([r.get(d) for r in all_results])

        # Weighted Skepticism: SkepticalReviewer defensibility counts 1.5×
        defs_weighted = []
        for r in all_results:
            ds = r.get("defensibility_score")
            if ds is None:
                continue
            try:
                weight = 1.5 if r.get("reviewer_type") == "SkepticalReviewer" else 1.0
                defs_weighted.append((float(ds), weight))
            except (TypeError, ValueError):
                pass
        if defs_weighted:
            weighted_sum = sum(v * w for v, w in defs_weighted)
            total_weight = sum(w for _, w in defs_weighted)
            weighted_def = weighted_sum / total_weight
            primary["defensibility_score"] = int(round(weighted_def))
            primary["weighted_defensibility_score"] = round(weighted_def, 3)

        self._recompute_derived_from_primary(primary, all_results)

    def _recompute_derived_from_primary(
        self, primary: Dict[str, Any], all_results: List[Dict[str, Any]]
    ) -> None:
        """Confidence-adjusted score + enrich_scores from current primary dimension scores."""
        core_dims = ["market_score", "product_score", "technical_score", "execution_score"]
        all_dims = list(core_dims)
        if primary.get("defensibility_score") is not None:
            all_dims.append("defensibility_score")
        s_bar = sum(float(primary.get(d, 5)) for d in all_dims) / len(all_dims)
        reviewer_avgs: List[float] = []
        for r in all_results:
            r_scores = [
                float(r[d]) for d in core_dims if isinstance(r.get(d), (int, float))
            ]
            ds = r.get("defensibility_score")
            if ds is not None:
                try:
                    r_scores.append(float(ds))
                except (TypeError, ValueError):
                    pass
            if r_scores:
                reviewer_avgs.append(sum(r_scores) / len(r_scores))
        if len(reviewer_avgs) >= 2:
            delta = max(reviewer_avgs) - min(reviewer_avgs)
            primary["confidence_adjusted_score"] = round(s_bar * (1.0 - delta / 10.0), 3)
        else:
            primary["confidence_adjusted_score"] = round(s_bar, 3)
        primary["score_source"] = DEFAULT_SCORE_SOURCE
        primary.update(enrich_scores(primary))

    def _refresh_derived_after_dimension_changes(
        self, primary: Dict[str, Any], all_results: List[Dict[str, Any]]
    ) -> None:
        """Re-run confidence_adjusted_score and enrich_scores after resolution tweaks."""
        self._recompute_derived_from_primary(primary, all_results)

    @staticmethod
    def _pick_primary_structured_signals(
        successful_results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Prefer DefaultReviewer normalized structured_signals; else first dict with signals."""
        for r in successful_results:
            if r.get("reviewer_type") == "DefaultReviewer":
                sig = r.get("structured_signals")
                if isinstance(sig, dict) and sig:
                    return dict(sig)
        for r in successful_results:
            sig = r.get("structured_signals")
            if isinstance(sig, dict) and sig:
                return dict(sig)
        return None

    def _apply_structured_scoring(self, scout_output: dict, reviewer_output: dict) -> dict:
        """Replace LLM-assigned numeric scores with deterministic weighted scores."""
        if not self.structured_scoring_engine:
            return reviewer_output
        trace = self.structured_scoring_engine.score(scout_output, reviewer_output)
        updated = dict(reviewer_output)
        updated["market_score"] = int(round(float(trace["market"]["score"])))
        updated["product_score"] = int(round(float(trace["product"]["score"])))
        updated["technical_score"] = int(round(float(trace["technical"]["score"])))
        updated["execution_score"] = int(round(float(trace["execution"]["score"])))
        updated["defensibility_score"] = int(round(float(trace["defensibility"]["score"])))
        updated["structured_scoring"] = trace
        updated["score_source"] = (
            "Deterministic structured scoring (extraction -> normalization -> weighted aggregation)"
        )
        updated["score_reasoning"] = {
            "market_score": "Computed from TAM, growth, urgency, timing, and competition signals.",
            "product_score": "Computed from extracted product-confidence signals.",
            "technical_score": "Computed from extracted technical-confidence signals.",
            "execution_score": "Computed from extracted execution-confidence signals.",
            "defensibility_score": "Computed from extracted defensibility-confidence signals.",
        }
        return updated

    @staticmethod
    def _derive_verdict_from_scores(primary: dict) -> None:
        """Set primary['derived_verdict'] from blended core scores (mean of present numerics only)."""
        dims = ["market_score", "product_score", "technical_score", "execution_score"]
        nums: List[float] = []
        for d in dims:
            v = primary.get(d)
            if isinstance(v, (int, float)):
                nums.append(float(v))
        if not nums:
            return
        mean = sum(nums) / len(nums)
        if mean >= 8.0:
            primary["derived_verdict"] = "STRONG"
        elif mean >= 6.0:
            primary["derived_verdict"] = "MEDIUM"
        else:
            primary["derived_verdict"] = "WEAK"

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

    @staticmethod
    def _coerce_confidence_threshold(raw: Any, default: float = 0.5) -> float:
        """Parse settings threshold safely and clamp to [0, 1]."""
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, value))

    async def run_cycle(self, pipeline_run_id: Optional[str] = None) -> int:
        """
        Run one review cycle.
        Processes up to batch_size unreviewed entries.
        Runs all 3 reviewer personas in parallel for each startup.
        
        Returns:
            Number of entries reviewed in this cycle
        """
        self.logger.info(f"Starting review cycle at {datetime.now().isoformat()}")
        if not is_reviewers_enabled(self.tenant_user_id):
            self.logger.info("Review cycle skipped (reviewers disabled in settings)")
            self.last_cycle_stats = {
                "reviewed_count": 0,
                "skipped_low_confidence": 0,
                "candidates_seen": 0,
                "confidence_threshold": None,
                "reason": "agents_disabled",
            }
            return 0
        self._sync_thesis_to_reviewers()

        # Check budget before reviewing
        if self.cost_controller:
            allowed, reason = self.cost_controller.check_budget("reviewer", "reviewer_engine")
            if not allowed:
                self.logger.warning(f"Reviewer budget denied: {reason}")
                self.last_cycle_stats = {
                    "reviewed_count": 0,
                    "skipped_low_confidence": 0,
                    "candidates_seen": 0,
                    "confidence_threshold": None,
                    "reason": "budget_denied",
                }
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
        if effective_batch <= 0:
            self.logger.info("No unreviewed entries found")
            self.last_cycle_stats = {
                "reviewed_count": 0,
                "skipped_low_confidence": 0,
                "candidates_seen": 0,
                "confidence_threshold": None,
                "reason": "no_unreviewed",
            }
            return 0
        
        # Load confidence threshold from settings
        try:
            settings = load_settings(self.tenant_user_id)
        except Exception as e:
            self.logger.warning("Reviewer settings unavailable, using defaults: %s", e)
            settings = {"agent_config": {}}
        confidence_threshold = self._coerce_confidence_threshold(
            (settings.get("agent_config") or {}).get("confidence_threshold", 0.2),
            default=0.2,
        )

        # Apply calibration override if present
        try:
            from meta.calibrator import load_calibration_state
            cal_state = load_calibration_state(self.tenant_user_id)
            ct_override = cal_state.get("confidence_threshold_override")
            if ct_override is not None:
                confidence_threshold = self._coerce_confidence_threshold(ct_override, default=confidence_threshold)
                self.logger.debug(f"Using calibration override: confidence_threshold={ct_override}")
        except ImportError:
            pass

        # Look ahead beyond effective_batch so one low-confidence stale row cannot
        # block all reviewer throughput for the cycle.
        lookahead_limit = min(
            max(effective_batch * 8, 20),
            max(unreviewed_count, effective_batch),
            500,
        )
        unreviewed_startups = self.storage.get_unreviewed(limit=lookahead_limit)

        if not unreviewed_startups:
            self.logger.info("No unreviewed entries found")
            self.last_cycle_stats = {
                "reviewed_count": 0,
                "skipped_low_confidence": 0,
                "candidates_seen": 0,
                "confidence_threshold": confidence_threshold,
                "reason": "no_candidates",
            }
            return 0

        # Sort by confidence_score descending (highest confidence first)
        unreviewed_startups.sort(
            key=lambda s: s.scout_info.confidence_score, reverse=True
        )

        self.logger.info(
            "Found %s unreviewed entries (lookahead=%s, target_reviews=%s, threshold=%.2f, top_conf=%.2f, bottom_conf=%.2f)",
            len(unreviewed_startups),
            lookahead_limit,
            effective_batch,
            confidence_threshold,
            unreviewed_startups[0].scout_info.confidence_score if unreviewed_startups else 0,
            unreviewed_startups[-1].scout_info.confidence_score if unreviewed_startups else 0,
        )

        reviewed_count = 0
        skipped_low_confidence = 0
        
        # Process each startup
        for startup in unreviewed_startups:
            if reviewed_count >= effective_batch:
                break
            confidence_score = startup.scout_info.confidence_score
            if confidence_score < confidence_threshold:
                skipped_low_confidence += 1
                continue
            scout_output = self._build_scout_output_payload(startup)
            entry_id = scout_output["id"]
            scout_for_llm = enrich_scout_for_reviewer_llm(scout_output, self.tenant_user_id)

            try:
                self.logger.info(
                    f"Reviewing entry {entry_id}: {scout_output.get('name', 'Unknown')} "
                    f"with 3 reviewer personas"
                )
                
                # Run all 3 reviewers in parallel
                default_task = self.reviewer.review(scout_for_llm)
                skeptical_task = self.skeptical_reviewer.review(scout_for_llm)
                opportunist_task = self.opportunist_reviewer.review(scout_for_llm)
                
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
                        if self.use_structured_scoring:
                            res = self._apply_structured_scoring(scout_output, res)
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
                resolution_notes, disagreement_summary = apply_resolution_to_primary(
                    review_output, successful_results
                )
                self._refresh_derived_after_dimension_changes(review_output, successful_results)
                review_output["resolution_notes"] = resolution_notes
                review_output["disagreement_summary"] = disagreement_summary
                sig_primary = self._pick_primary_structured_signals(successful_results)
                if sig_primary is not None:
                    review_output["structured_signals"] = sig_primary

                self._derive_verdict_from_scores(review_output)
                self.logger.info(
                    "reviewer_engine verdict=%s derived_verdict=%s",
                    review_output.get("verdict"),
                    review_output.get("derived_verdict"),
                )
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
                review_output["aethria_view"] = build_aethria_view(
                    review_output=review_output,
                    scout_output=scout_output,
                    consensus=consensus,
                    resolution_notes=resolution_notes,
                ).model_dump(mode="json")

                # Build SingleReview list for storage
                from models import SingleReview
                single_reviews = []
                _valid_reviewer_types = ("DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer")
                for r in successful_results:
                    reviewer_label = r.get("reviewer_type", "DefaultReviewer")
                    if reviewer_label not in _valid_reviewer_types:
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
                        score_source=r.get("score_source"),
                        improvement_to_9=r.get("improvement_to_9") or None,
                        market_reasoning=r.get("market_reasoning") or None,
                        market_weaknesses=r.get("market_weaknesses") or None,
                        market_confidence=r.get("market_confidence"),
                        product_reasoning=r.get("product_reasoning") or None,
                        product_weaknesses=r.get("product_weaknesses") or None,
                        product_confidence=r.get("product_confidence"),
                        technical_reasoning=r.get("technical_reasoning") or None,
                        technical_weaknesses=r.get("technical_weaknesses") or None,
                        technical_confidence=r.get("technical_confidence"),
                        execution_reasoning=r.get("execution_reasoning") or None,
                        execution_weaknesses=r.get("execution_weaknesses") or None,
                        execution_confidence=r.get("execution_confidence"),
                        defensibility_reasoning=r.get("defensibility_reasoning") or None,
                        defensibility_weaknesses=r.get("defensibility_weaknesses") or None,
                        defensibility_confidence=r.get("defensibility_confidence"),
                        prompt_version=r.get("prompt_version"),
                        structured_scoring=r.get("structured_scoring"),
                        structured_signals=(
                            dict(r["structured_signals"])
                            if isinstance(r.get("structured_signals"), dict)
                            else None
                        ),
                    ))
                
                # Convert to ReviewInfo and save (primary fields from default reviewer)
                from utils.adapters import reviewer_output_to_review_info
                review_info = reviewer_output_to_review_info(review_output)
                review_info.reviewer_agent_id = self.agent_id
                review_info.reviews = single_reviews
                review_info.consensus_verdict = consensus["consensus_verdict"]
                review_info.reviewer_disagreement = consensus["reviewer_disagreement"]
                review_info.score_variance = consensus["score_variance"]
                
                gap_urls = [
                    str(u).strip()
                    for u in (scout_for_llm.get("_reviewer_gap_reference_urls") or [])
                    if isinstance(u, str) and str(u).strip()
                ]
                success = self.storage.add_review(
                    entry_id,
                    review_info,
                    pipeline_run_id=pipeline_run_id,
                    enrichment_review_output=review_output,
                    enrichment_gap_reference_urls=gap_urls or None,
                )
                
                if success:
                    reviewed_count += 1
                    verdict = review_output.get("verdict", "UNKNOWN")
                    avg_score = compute_overall_score(review_output) or 0.0
                    
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
            "Review cycle complete: reviewed=%s skipped_low_confidence=%s candidates_seen=%s",
            reviewed_count,
            skipped_low_confidence,
            len(unreviewed_startups),
        )
        self.last_cycle_stats = {
            "reviewed_count": reviewed_count,
            "skipped_low_confidence": skipped_low_confidence,
            "candidates_seen": len(unreviewed_startups),
            "confidence_threshold": confidence_threshold,
            "reason": "ok",
        }
        
        return reviewed_count

    async def run_startup(
        self,
        startup_id: str,
        ignore_confidence_threshold: bool = False,
        pipeline_run_id: Optional[str] = None,
        force_rerun: bool = False,
        *,
        bypass_agent_enabled_gate: bool = False,
    ) -> bool:
        """
        Review one specific startup id.
        Returns True when a review is saved.

        bypass_agent_enabled_gate: when True, run even if reviewers are disabled in settings
        (used for occasional on-demand company lookup only).
        """
        startup = self.storage.get_startup(startup_id)
        if startup is None:
            self.logger.warning("Startup not found for review: %s", startup_id)
            return False
        if startup.review_info is not None and not force_rerun:
            self.logger.info("Startup already reviewed: %s", startup_id)
            return True
        if not bypass_agent_enabled_gate and not is_reviewers_enabled(self.tenant_user_id):
            self.logger.info("run_startup skipped (reviewers disabled in settings): %s", startup_id)
            return False

        try:
            settings = load_settings(self.tenant_user_id)
        except Exception as e:
            self.logger.warning("Reviewer settings unavailable for run_startup, using defaults: %s", e)
            settings = {"agent_config": {}}
        confidence_threshold = self._coerce_confidence_threshold(
            (settings.get("agent_config") or {}).get("confidence_threshold", 0.2),
            default=0.2,
        )
        try:
            from meta.calibrator import load_calibration_state
            cal_state = load_calibration_state(self.tenant_user_id)
            ct_override = cal_state.get("confidence_threshold_override")
            if ct_override is not None:
                confidence_threshold = self._coerce_confidence_threshold(ct_override, default=confidence_threshold)
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

        scout_output = self._build_scout_output_payload(startup)
        scout_for_llm = enrich_scout_for_reviewer_llm(scout_output, self.tenant_user_id)

        try:
            default_task = self.reviewer.review(scout_for_llm)
            skeptical_task = self.skeptical_reviewer.review(scout_for_llm)
            opportunist_task = self.opportunist_reviewer.review(scout_for_llm)
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
                    if self.use_structured_scoring:
                        res = self._apply_structured_scoring(scout_output, res)
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
            resolution_notes, disagreement_summary = apply_resolution_to_primary(
                review_output, successful_results
            )
            self._refresh_derived_after_dimension_changes(review_output, successful_results)
            review_output["resolution_notes"] = resolution_notes
            review_output["disagreement_summary"] = disagreement_summary
            sig_primary = self._pick_primary_structured_signals(successful_results)
            if sig_primary is not None:
                review_output["structured_signals"] = sig_primary

            self._derive_verdict_from_scores(review_output)
            self.logger.info(
                "reviewer_engine verdict=%s derived_verdict=%s",
                review_output.get("verdict"),
                review_output.get("derived_verdict"),
            )
            if self.active_thesis and self.active_thesis.get("version_id"):
                review_output["fund_thesis_version_id"] = self.active_thesis["version_id"]
            self._apply_rule_based_thesis_alignment(review_output, scout_output)
            self._apply_resource_fund_thesis_alignment(
                review_output, scout_output, startup_id
            )
            consensus = self._compute_consensus(successful_results)
            review_output["aethria_view"] = build_aethria_view(
                review_output=review_output,
                scout_output=scout_output,
                consensus=consensus,
                resolution_notes=resolution_notes,
            ).model_dump(mode="json")

            from models import SingleReview
            from utils.adapters import reviewer_output_to_review_info
            single_reviews = []
            _valid_reviewer_types = ("DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer")
            for r in successful_results:
                reviewer_label = r.get("reviewer_type", "DefaultReviewer")
                if reviewer_label not in _valid_reviewer_types:
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
                    score_source=r.get("score_source"),
                    improvement_to_9=r.get("improvement_to_9") or None,
                    market_reasoning=r.get("market_reasoning") or None,
                    market_weaknesses=r.get("market_weaknesses") or None,
                    market_confidence=r.get("market_confidence"),
                    product_reasoning=r.get("product_reasoning") or None,
                    product_weaknesses=r.get("product_weaknesses") or None,
                    product_confidence=r.get("product_confidence"),
                    technical_reasoning=r.get("technical_reasoning") or None,
                    technical_weaknesses=r.get("technical_weaknesses") or None,
                    technical_confidence=r.get("technical_confidence"),
                    execution_reasoning=r.get("execution_reasoning") or None,
                    execution_weaknesses=r.get("execution_weaknesses") or None,
                    execution_confidence=r.get("execution_confidence"),
                    defensibility_reasoning=r.get("defensibility_reasoning") or None,
                    defensibility_weaknesses=r.get("defensibility_weaknesses") or None,
                    defensibility_confidence=r.get("defensibility_confidence"),
                    prompt_version=r.get("prompt_version"),
                    structured_scoring=r.get("structured_scoring"),
                    structured_signals=(
                        dict(r["structured_signals"])
                        if isinstance(r.get("structured_signals"), dict)
                        else None
                    ),
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
            gap_urls = [
                str(u).strip()
                for u in (scout_for_llm.get("_reviewer_gap_reference_urls") or [])
                if isinstance(u, str) and str(u).strip()
            ]
            return bool(
                self.storage.add_review(
                    startup_id,
                    review_info,
                    pipeline_run_id=pipeline_run_id,
                    enrichment_review_output=review_output,
                    enrichment_gap_reference_urls=gap_urls or None,
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
