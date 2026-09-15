"""Runner compatibility callbacks for an already completed authoritative analysis.

These callbacks never invoke the retired Reviewer personas or Partner mapper.
The refresh callback runs the shared core only when explicitly invalidated.
"""
import asyncio
import logging
from copy import deepcopy
from types import SimpleNamespace

from pipeline_execution import StageExecutionResult
from tenant_context import require_user_id
from .prompts import REVIEWER_PROMPT
from .model_gateway import AnalysisBlocked


class CompletedAnalysisStage:
    analysis_contract_version = "investment-analysis-v1"

    def __init__(self, *, stage: str, user_id: str, storage, load, refresh, model: str, settings: dict, batch_size: int = 3, active_thesis: dict | None = None):
        self.stage = stage
        self.tenant_user_id = require_user_id(user_id, context="CompletedAnalysisStage")
        self.storage = storage
        self.load = load
        self.refresh = refresh
        self.model = model
        self.settings = settings
        self.active_thesis = deepcopy(active_thesis)
        self.batch_size = batch_size
        self.agent_id = f"investment-{stage}"
        self.reviewer = SimpleNamespace(SYSTEM_PROMPT=REVIEWER_PROMPT)
        self.last_cycle_stats = {}
        self.last_cycle_escalations = 0
        self.founder_persister = None

    async def run_startup(self, startup_id, pipeline_run_id=None, force_rerun=False, **kwargs):
        record = await self.load(startup_id)
        analysis = ((record or {}).get("evaluation", {}).get("judgment_audit") or {}).get("investment_analysis")
        source_run = ((analysis or {}).get("reviewer", {}).get("lineage") or {}).get("pipeline_run_id")
        if self.stage == "reviewer" and (not analysis or (force_rerun and source_run != pipeline_run_id)):
            await self.refresh(startup_id, pipeline_run_id)
            record = await self.load(startup_id)
            analysis = ((record or {}).get("evaluation", {}).get("judgment_audit") or {}).get("investment_analysis")
        return bool(analysis and analysis.get(self.stage))

    async def run_cycle(self, pipeline_run_id=None, **kwargs):
        # The core atomically wrote both compatibility stages. Backlog entries
        # without analysis are refreshed once by the Reviewer callback.
        candidates = await asyncio.to_thread(
            self.storage.get_unreviewed if self.stage == "reviewer" else self.storage.get_undecided,
            limit=self.batch_size,
        )
        if not candidates:
            return StageExecutionResult.skipped_result(stage=self.stage, code="analysis_projection_current",
                                                       detail="No outstanding analysis projection.")
        succeeded = 0
        blocked = 0
        warnings = []
        for startup in candidates:
            try:
                succeeded += bool(await self.run_startup(startup.startup_id, pipeline_run_id=pipeline_run_id))
            except AnalysisBlocked as exc:
                blocked += 1
                warnings.append({"code": exc.code, "startup_id": startup.startup_id})
                logging.getLogger(__name__).warning("Investment analysis blocked: %s", exc.code)
            except Exception:
                logging.getLogger(__name__).exception("Investment analysis stage failed")
        self.last_cycle_stats = {"reviewed_count": succeeded, "candidates_seen": len(candidates)}
        if blocked == len(candidates):
            return StageExecutionResult.blocked_result(stage=self.stage, code="investment_analysis_blocked",
                detail="Investment analysis is blocked for all candidates.", recovery_action="Resolve the named blocks and retry in a new run.",
                attempted=len(candidates), blocked=blocked, warnings=warnings)
        if succeeded != len(candidates):
            return StageExecutionResult.failed_result(stage=self.stage, code="investment_analysis_incomplete",
                detail="Investment analysis has not completed for all candidates.", recovery_action="Retry the shared analysis pipeline.",
                attempted=len(candidates), failed=len(candidates)-succeeded-blocked, blocked=blocked, succeeded=succeeded, warnings=warnings)
        return StageExecutionResult.completed(stage=self.stage, code="analysis_projection_current",
            detail="Completed investment analysis projected.", attempted=len(candidates), succeeded=succeeded)

    def _sync_thesis_to_reviewers(self):
        # Tenant context is loaded at the shared analysis boundary.
        return None

    async def preview_persona_review(self, *args, **kwargs):
        # Legacy persona calibration is not an authority over the new contract.
        return None

    def close(self):
        return None
