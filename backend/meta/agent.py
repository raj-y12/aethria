"""
MetaAgent — the main orchestrator for self-optimisation cycles.
Backed by Supabase meta_cycle_counters and meta_reports (explicit user_id per tenant).
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from utils.timeutil import utcnow

from tenant_context import TenantContext, require_user_id
from meta.analyser import MetaAnalyser
from meta.mutator import PromptMutator, _append_to_json_list
from meta.reweighter import ScoutReweighter
from meta.calibrator import ThresholdCalibrator
from supabase_doc_store import doc_get_int, doc_set_int
from utils.job_schedule import claim_due_jobs
from pipeline_execution import MetaCycleResult, StageExecutionResult

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPORTS_PATH = _BACKEND_DIR / "data" / "meta" / "meta_reports.json"
_CYCLE_COUNTER_TABLE = "meta_cycle_counters"


class MetaAgent:
    """Orchestrates the full Meta-Agent optimisation cycle."""

    def __init__(self, scout_engine=None, reviewer_engine=None, user_id: str = ""):
        uid = require_user_id(user_id, context="MetaAgent")
        self.user_id = uid
        self.tenant = TenantContext(user_id=uid)
        self.scout_engine = scout_engine
        self.reviewer_engine = reviewer_engine
        self.logger = logging.getLogger("meta.agent")
        self.min_reviews = int(os.getenv("META_AGENT_MIN_REVIEWS", "20"))
        self.min_decisions = int(os.getenv("META_AGENT_MIN_DECISIONS", "10"))
        self.interval = int(os.getenv("META_AGENT_INTERVAL_SECONDS", "86400"))
        self.enabled = os.getenv("META_AGENT_ENABLED", "true").lower() == "true"
        self._no_action_reasons: List[str] = []

    def _increment_cycle(self) -> int:
        cycle = doc_get_int(_CYCLE_COUNTER_TABLE, user_id=self.user_id) + 1
        doc_set_int(_CYCLE_COUNTER_TABLE, cycle, user_id=self.user_id)
        return cycle

    async def run_cycle(self, *, force: bool = False) -> MetaCycleResult:
        if not self.enabled:
            self.logger.info("[MetaAgent] Disabled via META_AGENT_ENABLED=false")
            return MetaCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="meta",
                    code="meta_disabled",
                    detail="The Meta stage is disabled for this tenant.",
                )
            )
        try:
            due = await asyncio.to_thread(
                claim_due_jobs,
                self.user_id,
                {"meta": 0 if force else self.interval},
            )
        except Exception as exc:
            self.logger.error("[MetaAgent] Schedule claim failed: %s", exc, exc_info=True)
            return MetaCycleResult(
                outcome=StageExecutionResult.failed_result(
                    stage="meta",
                    code="meta_schedule_unavailable",
                    detail="The Meta schedule could not be claimed.",
                    recovery_action=(
                        "Restore the durable schedule store and retry the Meta cycle."
                    ),
                    attempted=1,
                    failed=1,
                )
            )
        if "meta" not in due:
            self.logger.debug("[MetaAgent] Daily interval has not elapsed")
            return MetaCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="meta",
                    code="meta_not_due",
                    detail="The Meta analysis interval has not elapsed.",
                )
            )
        # The whole cycle is blocking doc-store/analysis I/O — one hop off the
        # serving event loop rather than dozens of per-call thread hops.
        try:
            report = await asyncio.to_thread(self._run_cycle_sync)
            if not isinstance(report, dict):
                raise RuntimeError("Meta analysis returned no report")
        except Exception as exc:
            self.logger.error("[MetaAgent] Analysis cycle failed: %s", exc, exc_info=True)
            return MetaCycleResult(
                outcome=StageExecutionResult.failed_result(
                    stage="meta",
                    code="meta_cycle_failed",
                    detail="The Meta analysis cycle did not produce a report.",
                    recovery_action=(
                        "Inspect Meta analysis and persistence logs, restore the "
                        "failed dependency, and retry."
                    ),
                    attempted=1,
                    failed=1,
                )
            )
        return MetaCycleResult(
            outcome=StageExecutionResult.completed(
                stage="meta",
                code="meta_completed",
                detail="The Meta analysis cycle produced an analysis-only report.",
                attempted=1,
                succeeded=1,
            ),
            report=report,
        )

    def _run_cycle_sync(self) -> Optional[Dict]:
        self.logger.info(
            "event=tenant_context user_id=%s module=meta_agent",
            self.user_id[:24],
        )
        cycle_number = self._increment_cycle()
        self._no_action_reasons = []
        self.logger.info("[MetaAgent] Starting cycle %s", cycle_number)

        analyser = MetaAnalyser(self.user_id)
        signal = analyser.analyse()

        sufficiency = signal.get("data_sufficiency", {})
        total_reviews = sufficiency.get("total_reviews", 0)
        total_decisions = sufficiency.get("total_decisions", 0)

        mutations = []
        weight_updates = []
        calibrations = []

        if total_reviews < self.min_reviews or total_decisions < self.min_decisions:
            self.logger.info(
                "[MetaAgent] Insufficient data for cycle %s: %s reviews (min %s), %s decisions (min %s)",
                cycle_number,
                total_reviews,
                self.min_reviews,
                total_decisions,
                self.min_decisions,
            )
            self._no_action_reasons.append(
                f"Insufficient data: {total_reviews} reviews (need {self.min_reviews}), "
                f"{total_decisions} decisions (need {self.min_decisions})"
            )
        else:
            mutator = PromptMutator(signal, cycle_number, self.user_id)
            try:
                mutation_targets = mutator.decide()

                reweighter = ScoutReweighter(signal, cycle_number, self.user_id)
                weight_updates = reweighter.decide()

                calibrator = ThresholdCalibrator(signal, cycle_number, self.user_id)
                calibrations = calibrator.decide()

                if mutation_targets:
                    mutations = mutator.apply(mutation_targets, self.scout_engine, self.reviewer_engine)
                else:
                    self._no_action_reasons.append("No prompt mutations needed")

                if not weight_updates:
                    self._no_action_reasons.append("Scout weights stable")

                if not calibrations:
                    self._no_action_reasons.append("No calibration changes needed")
            finally:
                mutator.close()

        now = utcnow()
        report = {
            "cycle_number": cycle_number,
            "ran_at": now.isoformat(),
            "signal_summary": signal,
            "analysis_only": True,
            "production_mutations_applied": 0,
            "prompt_proposals": mutations,
            "mutations_applied": [],
            "weight_proposals": weight_updates,
            "calibration_proposals": calibrations,
            # Compatibility aliases for existing report readers. These are proposals,
            # not proof that production state changed.
            "weight_updates": weight_updates,
            "calibration_changes": calibrations,
            "no_action_reasons": self._no_action_reasons,
            "next_cycle_at": (now + timedelta(seconds=self.interval)).isoformat(),
        }
        _append_to_json_list(_REPORTS_PATH, report, self.user_id)

        self.logger.info(
            "[MetaAgent] Cycle %s complete. %s prompt_proposals, %s reweightings, %s calibrations.",
            cycle_number,
            len(mutations),
            len(weight_updates),
            len(calibrations),
        )

        return report
