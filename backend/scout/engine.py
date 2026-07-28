"""
Scout execution engine.
Runs all Scouts in parallel on a configurable interval.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from utils.timeutil import utcnow

from resolver.company_resolver import (
    CompanyResolution,
    build_fallback_scout_payload,
    resolve_company,
)
from resolver.founder_resolver import FounderResolution, resolve_founders
from scout.scouts import (
    MarketDrivenScout,
    BuilderTechnicalScout,
    PainPointScout,
    ContrarianScout,
)
from scout.base import Scout
from scout.schema import ScoutOutput
from utils.founder_enrichment import (
    apply_founder_resolution_to_payload,
    is_founder_resolution_enabled,
)
from utils.storage import Storage
from tenant_context import require_user_id
from utils.settings_loader import get_runtime_limits, is_scouts_enabled
from utils.prompt_version import hash_prompt
from pipeline_execution import ScoutCycleResult, StageExecutionResult


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
            tenant_user_id: Explicit Clerk user id (settings, retrieval, meta weights).
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
        # When the unreviewed queue is thin, run multiple parallel scout waves per cycle
        # so the pipeline keeps getting fresh leads (reviewer-style ramp, inverted for inbound).
        self.scout_ramp_threshold = int(os.getenv("SCOUT_RAMP_THRESHOLD", "5"))
        self.scout_ramp_max_waves = max(
            1, min(int(os.getenv("SCOUT_RAMP_MAX_WAVES", "2")), 4)
        )
        self.logger = logging.getLogger("scout.engine")
        self.running = False
        # Outcome of the most recent run_named_lookup: resolver status, message, and
        # debug detail. Lets pipeline_runner surface a transparent failure message
        # (what was searched, what was missing) instead of a generic error.
        self.last_lookup_outcome: Optional[Dict[str, Any]] = None

    def set_active_thesis(self, thesis: Optional[Dict[str, Any]]) -> None:
        self.active_thesis = thesis
        for s in self.scouts:
            s.set_fund_thesis(thesis)

    def close(self) -> None:
        """Release each scout's OpenAI client and worker thread (called at cycle end)."""
        for s in self.scouts:
            try:
                s.close()
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.debug("Scout close failed: %s", exc)

    def _sync_thesis_to_scouts(self) -> None:
        for s in self.scouts:
            s.set_fund_thesis(self.active_thesis)

    def _select_scouts_for_wave(self) -> List[Scout]:
        """Pick which scouts run this wave (meta weights or all four)."""
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
            weight_list = [
                weights.get(scout_type_to_name.get(s.scout_type, ""), 0.25) for s in self.scouts
            ]
            if any(w != 0.25 for w in weight_list):
                scouts_per_cycle = 4
                choices = random.choices(
                    range(len(self.scouts)), weights=weight_list, k=scouts_per_cycle * 2
                )
                selected_indices: set = set()
                for c in choices:
                    selected_indices.add(c)
                    if len(selected_indices) >= scouts_per_cycle:
                        break
                if len(selected_indices) < 2:
                    all_indices = list(range(len(self.scouts)))
                    random.shuffle(all_indices)
                    for idx in all_indices:
                        selected_indices.add(idx)
                        if len(selected_indices) >= 2:
                            break
                return [self.scouts[i] for i in selected_indices]
            return self.scouts
        except ImportError:
            return self.scouts
    
    async def run_cycle(
        self,
        pipeline_run_id: Optional[str] = None,
        *,
        persist_discoveries: bool = True,
    ) -> ScoutCycleResult:
        """
        Run one discovery cycle with all Scouts in parallel.
        
        Returns one immutable payload containing both valid discoveries and a
        lossless terminal account of every selected Scout persona.
        """
        self.logger.info(f"Starting discovery cycle at {utcnow().isoformat()}")
        if not is_scouts_enabled(self.tenant_user_id):
            self.logger.info("Discovery cycle skipped (scouts disabled in settings)")
            return ScoutCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="scout",
                    code="scout_disabled",
                    detail="The Scout stage is disabled for this tenant.",
                )
            )
        try:
            max_discoveries = int(get_runtime_limits(self.tenant_user_id).get("max_agents_per_run", 10))
        except Exception:
            max_discoveries = 10
        max_discoveries = max(1, max_discoveries)
        self._sync_thesis_to_scouts()

        unreviewed: Optional[int] = None
        if self.storage is not None:
            try:
                # Sync Supabase I/O off the serving event loop: a blocked loop
                # stalls every in-flight API response and SSE stream.
                unreviewed = await asyncio.to_thread(self.storage.count_unreviewed)
            except Exception as e:
                self.logger.debug("Could not get unreviewed count: %s", e)

        # Backpressure: skip discovery when too many unreviewed (let reviewers catch up)
        if unreviewed is not None and unreviewed > self.backpressure_threshold:
            self.logger.warning(
                f"Backpressure: {unreviewed} unreviewed exceeds threshold "
                f"({self.backpressure_threshold}), skipping scout cycle"
            )
            return ScoutCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="scout",
                    code="scout_backpressure",
                    detail=(
                        "The Scout stage deferred discovery while the Reviewer "
                        "backlog is above its configured threshold."
                    ),
                )
            )

        waves = 1
        if (
            unreviewed is not None
            and unreviewed <= self.scout_ramp_threshold
            and self.scout_ramp_max_waves > 1
        ):
            waves = self.scout_ramp_max_waves
            self.logger.info(
                "Scout ramp: unreviewed=%s <= threshold=%s, running %s parallel waves this cycle",
                unreviewed,
                self.scout_ramp_threshold,
                waves,
            )

        discoveries: List[ScoutOutput] = []
        attempted_count = 0
        failed_count = 0
        persistence_failed_count = 0
        blocked_count = 0
        skipped_count = 0
        diagnostics: List[Dict[str, Any]] = []
        for wave_idx in range(waves):
            remaining_slots = max_discoveries - len(discoveries)
            if remaining_slots <= 0:
                break
            selected_scouts = self._select_scouts_for_wave()
            selected_scouts = selected_scouts[:remaining_slots]
            if not selected_scouts:
                continue
            if self.cost_controller:
                allowed, reason = self.cost_controller.check_budget("scout", "scout_engine")
                if not allowed:
                    blocked_count += len(selected_scouts)
                    attempted_count += len(selected_scouts)
                    self.logger.warning(
                        "Scout budget denied (wave %s/%s): %s", wave_idx + 1, waves, reason
                    )
                    break

            attempted_count += len(selected_scouts)

            if self.deal_memory:
                memory_context = self.deal_memory.get_memory_context_for_scout()
                for scout in self.scouts:
                    scout.set_dynamic_context(memory_context)

            tasks = [scout._discover_with_validation() for scout in selected_scouts]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                scout = selected_scouts[i]

                if isinstance(result, Exception):
                    failed_count += 1
                    diagnostics.append({
                        "scout_type": scout.scout_type,
                        "kind": "model_failure",
                        "reason": "request_error",
                    })
                    self.logger.error(
                        f"[{scout.scout_type}] Discovery failed with exception: {result}"
                    )
                elif result is None:
                    failed_count += 1
                    diagnostic = getattr(scout, "last_discovery_diagnostic", None)
                    diagnostics.append({
                        "scout_type": scout.scout_type,
                        **(diagnostic if isinstance(diagnostic, dict) else {
                            "kind": "unknown_failure",
                        }),
                    })
                    self.logger.warning(
                        "[%s] Discovery returned None diagnostic=%s",
                        scout.scout_type,
                        getattr(scout, "last_discovery_diagnostic", None),
                    )
                else:
                    if self.deal_memory:
                        thesis = result.get("primary_thesis", "")
                        if self.deal_memory.is_duplicate_thesis(thesis):
                            self.logger.info(
                                f"[{scout.scout_type}] Skipping duplicate thesis: "
                                f"{result['name']}"
                            )
                            skipped_count += 1
                            continue

                    try:
                        result = dict(result)
                        result["prompt_version"] = hash_prompt(getattr(scout, "system_prompt", ""))
                    except Exception:
                        result = dict(result)

                    result["pipeline_run_id"] = pipeline_run_id
                    self.logger.info(
                        f"[{scout.scout_type}] Discovered: {result['name']} "
                        f"(confidence: {result['confidence']:.2f})"
                    )

                    if self.cost_controller:
                        self.cost_controller.record_usage(
                            "scout",
                            scout.scout_type,
                            scout._last_token_usage,
                            model=self.model,
                        )

                    if self.storage and persist_discoveries:
                        try:
                            persisted_id = await asyncio.to_thread(
                                self.storage.add_discovery, result, pipeline_run_id=pipeline_run_id
                            )
                            if not str(persisted_id or "").strip():
                                raise RuntimeError(
                                    "discovery persistence returned no startup id"
                                )
                            result["persisted_startup_id"] = str(
                                persisted_id or result.get("id") or ""
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to persist discovery {result.get('id')}: {e}"
                            )
                            failed_count += 1
                            persistence_failed_count += 1
                            continue

                    discoveries.append(result)

                    if self.deal_memory:
                        try:
                            self.deal_memory.record_scout_discovery(
                                result.get("sector", ""),
                                result.get("primary_thesis", ""),
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to record in deal memory: {e}")

        self.logger.info(
            "Cycle complete: %s discoveries successful across %s wave(s) (scouts=%s)",
            len(discoveries),
            waves,
            len(self.scouts),
        )

        succeeded_count = len(discoveries)
        if persistence_failed_count:
            outcome = StageExecutionResult.failed_result(
                stage="scout",
                code="scout_persistence_failures",
                detail=(
                    f"Scout produced {succeeded_count} eligible discovery(ies), "
                    f"but {persistence_failed_count} could not be persisted."
                ),
                recovery_action=(
                    "Inspect Scout storage and Supabase connectivity, then retry "
                    "the affected cycle."
                ),
                attempted=attempted_count,
                succeeded=succeeded_count,
                failed=failed_count,
                blocked=blocked_count,
                skipped=skipped_count,
            )
        elif blocked_count and succeeded_count:
            outcome = StageExecutionResult.failed_result(
                stage="scout",
                code="scout_partial_budget_block",
                detail=(
                    f"Scout produced {succeeded_count} eligible discovery(ies), "
                    f"but {blocked_count} persona attempt(s) were blocked by the "
                    "cost budget."
                ),
                recovery_action=(
                    "Increase the Scout budget or wait for the budget window to "
                    "reset, then retry the affected cycle."
                ),
                attempted=attempted_count,
                succeeded=succeeded_count,
                failed=failed_count,
                blocked=blocked_count,
                skipped=skipped_count,
            )
        elif succeeded_count and failed_count:
            outcome = StageExecutionResult.completed(
                stage="scout",
                code="scout_completed_with_warnings",
                detail=(
                    f"Scout produced {succeeded_count} eligible discovery(ies) "
                    f"from {attempted_count} persona attempt(s); some attempts "
                    "were unavailable and will be retried on the next cycle."
                ),
                attempted=attempted_count,
                succeeded=succeeded_count,
                skipped=skipped_count + failed_count,
                warnings=diagnostics,
            )
        elif failed_count:
            outcome = StageExecutionResult.skipped_result(
                stage="scout",
                code="scout_no_eligible_work",
                detail=(
                    f"No Scout persona produced an eligible, reference-validated "
                    f"discovery ({failed_count} attempt(s) unavailable). The next "
                    "scheduled cycle will retry Scout."
                ),
                attempted=attempted_count,
                skipped=skipped_count + failed_count,
                warnings=diagnostics,
            )
        elif blocked_count:
            outcome = StageExecutionResult.blocked_result(
                stage="scout",
                code="scout_budget_blocked",
                detail="Scout budget denied all selected personas in this cycle.",
                recovery_action=(
                    "Increase the Scout budget or wait for the budget window to "
                    "reset, then retry."
                ),
                attempted=attempted_count,
                blocked=blocked_count,
                skipped=skipped_count,
            )
        elif succeeded_count:
            outcome = StageExecutionResult.completed(
                stage="scout",
                code="scout_completed",
                detail=f"Scout completed {succeeded_count} discovery attempt(s).",
                attempted=attempted_count,
                succeeded=succeeded_count,
                skipped=skipped_count,
            )
        else:
            outcome = StageExecutionResult.skipped_result(
                stage="scout",
                code="scout_no_eligible_work",
                detail="No Scout persona produced a distinct eligible discovery.",
                attempted=attempted_count,
                skipped=skipped_count,
            )
        return ScoutCycleResult(
            outcome=outcome,
            discoveries=discoveries,
            diagnostics=diagnostics,
        )

    async def _resolve_founders_for_lookup(
        self,
        company: str,
        *,
        resolution: Optional[CompanyResolution],
        website: Optional[str],
    ) -> Optional[FounderResolution]:
        """Run the deterministic founder stage; never fail the lookup because of it."""
        if not is_founder_resolution_enabled():
            return None
        aliases: List[str] = []
        location: Optional[str] = None
        known: List[str] = []
        if resolution is not None:
            for alias in (resolution.canonical_name, resolution.query):
                if alias and alias not in aliases:
                    aliases.append(alias)
            known = list(resolution.founder_names)
        try:
            founder_resolution = await asyncio.to_thread(
                resolve_founders,
                company,
                user_id=self.tenant_user_id,
                website=website,
                aliases=aliases,
                location=location,
                known_founder_names=known,
            )
        except Exception as e:
            self.logger.warning("Founder resolver failed for %s: %s", company, e)
            return None
        self.logger.info(
            "[lookup] founder resolver company=%s %s",
            company,
            founder_resolution.summary_line(),
        )
        return founder_resolution

    async def run_named_lookup(
        self,
        company_name: str,
        scout_type: str = "market_driven",
        website: Optional[str] = None,
        lookup_query: Optional[str] = None,
        lookup_input_type: Optional[str] = None,
        lookup_id: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
        resolution: Optional[CompanyResolution] = None,
        additional_context: Optional[str] = None,
    ) -> Optional[str]:
        """
        On-demand lookup, staged:
          1. Resolve company identity (Company Resolver — deterministic, layered searches)
          2. Resolve founders (Founder Resolver — deterministic, seeded with stage 1 identity)
          3. Scout/enrich the resolved company (LLM, seeded with resolver evidence)
          4. Persist (review + scoring happen later and never delete the row)
        Weak evidence is persisted as PARTIAL/LOW_CONFIDENCE/NEEDS_REVIEW; only a lookup
        with genuinely no credible evidence anywhere returns None (status NOT_FOUND),
        and even then last_lookup_outcome explains what was searched and missing.
        Returns startup_id on success, else None.
        """
        company = (company_name or "").strip()
        self.last_lookup_outcome = None
        self.last_lookup_startup = None
        if not company:
            return None
        selected = next((s for s in self.scouts if s.scout_type == scout_type), None)
        if selected is None:
            selected = self.scouts[0] if self.scouts else None
        if selected is None:
            return None

        self._sync_thesis_to_scouts()

        # ── Stage 1: resolve company identity ────────────────────────────────
        if resolution is None:
            try:
                resolution = await asyncio.to_thread(
                    resolve_company,
                    company,
                    user_id=self.tenant_user_id,
                    website_hint=website,
                )
            except Exception as e:
                self.logger.warning("Company resolver failed for %s: %s", company, e)
                resolution = None
        if resolution is not None:
            self.logger.info(
                "[lookup] resolver company=%s %s queries=%d",
                company,
                resolution.summary_line(),
                len(resolution.queries_used),
            )
            if resolution.resolution_status == "NOT_FOUND":
                searched = len(resolution.queries_used)
                self.last_lookup_outcome = {
                    "status": "NOT_FOUND",
                    "message": (
                        f'No credible evidence found for "{company}" across {searched} '
                        "search queries (web, LinkedIn, Crunchbase, founders, funding). "
                        "If the company exists, add its website to the lookup "
                        f'(example: "{company} company-website.com").'
                    ),
                    "resolution": resolution.model_dump(mode="json"),
                }
                self.logger.warning(
                    "[lookup] NOT_FOUND company=%s queries_used=%s",
                    company,
                    resolution.queries_used,
                )
                return None

        # Resolver-discovered website only steers the scout when identity is solid;
        # the user-provided hint always wins.
        effective_website = (website or "").strip() or None
        if (
            not effective_website
            and resolution is not None
            and resolution.website
            and resolution.resolution_status == "FOUND"
        ):
            effective_website = resolution.website

        # ── Stage 2: resolve founders (deterministic, anchored on stage 1) ───
        founder_resolution = await self._resolve_founders_for_lookup(
            company, resolution=resolution, website=effective_website
        )

        # ── Stage 3: enrich via scout LLM (seeded with resolver evidence) ────
        result = await selected.discover_company(
            company,
            website=effective_website,
            resolution=resolution,
            additional_context=additional_context,
        )
        if result is None and resolution is not None:
            # Demo-safe fallback: the resolver found real evidence but profile
            # generation failed — persist a NEEDS_REVIEW row instead of vanishing.
            result = build_fallback_scout_payload(
                resolution, scout_type=selected.scout_type, company_name=company
            )
            if result is not None:
                self.logger.warning(
                    "[lookup] scout stage failed for %s; persisting resolver-evidence "
                    "fallback row as NEEDS_REVIEW (%d sources)",
                    company,
                    len(resolution.evidence_sources),
                )
        if result is None:
            self.last_lookup_outcome = {
                "status": "FAILED",
                "message": (
                    f'Lookup for "{company}" found no usable evidence and profile '
                    "generation failed. Try adding the company website to disambiguate."
                ),
                "resolution": resolution.model_dump(mode="json") if resolution else None,
            }
            return None

        try:
            payload = dict(result)
            if resolution is not None and not payload.get("company_resolution"):
                payload["resolution_status"] = resolution.resolution_status
                payload["company_resolution"] = resolution.model_dump(mode="json")
            payload = apply_founder_resolution_to_payload(payload, founder_resolution)
            payload["prompt_version"] = hash_prompt(getattr(selected, "system_prompt", ""))
            payload["origin_type"] = "on_demand_lookup"
            payload["lookup_query"] = (lookup_query or company).strip()
            payload["lookup_input_type"] = (lookup_input_type or "company_name").strip()
            payload["lookup_website"] = (website or "").strip() or None
            if lookup_id and str(lookup_id).strip():
                payload["lookup_id"] = str(lookup_id).strip()
            from models import Startup
            from utils.adapters import financials_from_scout_output, scout_output_to_scout_info

            handoff_startup = Startup(
                startup_id=str(payload.get("id") or ""),
                scout_info=scout_output_to_scout_info(payload),
                financials=financials_from_scout_output(payload),
            )
            pr = (pipeline_run_id or "").strip() or None
            persisted_id = str(payload.get("id") or "")
            if self.storage:
                persisted_id = await asyncio.to_thread(
                    self.storage.add_discovery,
                    payload,
                    pipeline_run_id=pr,
                )
            already_exists = bool(persisted_id and persisted_id != str(payload.get("id") or ""))
            if not already_exists and persisted_id:
                handoff_startup.startup_id = persisted_id
                handoff_startup.scout_info.startup_id = persisted_id
                self.last_lookup_startup = handoff_startup
            self.last_lookup_outcome = {
                "status": (
                    "ALREADY_IN_DEAL_FLOW"
                    if already_exists
                    else payload.get("resolution_status") or "FOUND"
                ),
                "startup_id": persisted_id,
                "message": (
                    "This company is already in your deal flow."
                    if already_exists
                    else None
                ),
            }
            self.logger.info(
                "[lookup] persisted company=%s startup_id=%s resolution_status=%s",
                company,
                persisted_id,
                self.last_lookup_outcome["status"],
            )
            return persisted_id or None
        except Exception as e:
            self.logger.error("Failed named lookup persistence for %s: %s", company, e)
            self.last_lookup_outcome = {
                "status": "FAILED",
                "message": f'Lookup for "{company}" could not be saved. Try again.',
            }
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
                cycle_count += 1
                self.logger.info(f"=== Discovery Cycle #{cycle_count} ===")
                from uuid import uuid4

                cycle_result = await self.run_cycle(pipeline_run_id=str(uuid4()))
                outcome = cycle_result.outcome
                self.logger.info(
                    "Scout cycle state=%s code=%s attempted=%s succeeded=%s failed=%s blocked=%s skipped=%s",
                    outcome.state.value,
                    outcome.code,
                    outcome.attempted,
                    outcome.succeeded,
                    outcome.failed,
                    outcome.blocked,
                    outcome.skipped,
                )
                
                # Log discoveries in a structured way
                if cycle_result.discoveries:
                    self.logger.info("Discoveries:")
                    for disc in cycle_result.discoveries:
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
