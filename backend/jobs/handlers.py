"""Durable job handlers that adapt AgentJob payloads to existing pipeline services."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any, Dict

from identity.models import IdentityAdmission, IdentityStatus, SourceChannel, SourceObservationInput
from identity.repository import IdentityRepository
from identity.service import IdentityService
from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    EvidenceRefreshPayload,
    JobExecutionBlocked,
    JobExecutionCancelled,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)
from jobs.lookup_outcomes import LookupAttemptDisposition, LookupAttemptOutcome
from jobs.fencing import assert_job_ownership
from evidence.repository import EvidenceRepository
from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from evaluation_v2.repository import EvaluationLifecycleError, EvaluationRepository
from fund_intelligence.repository import FundIntelligenceRepository
from monitoring.models import RefreshReason
from monitoring.repository import MonitoringRepository
from pipeline_runner import run_on_demand_lookup, run_one_pipeline_cycle
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState
from resolver.company_resolver import CompanyResolution, resolve_company
from authority.repository import AuthorityBlocked

_logger_handlers = logging.getLogger(__name__)


async def _raise_if_cancelled(repository: Any, job: AgentJob) -> None:
    await assert_job_ownership(repository, job)


async def _checkpoint(repository, job, stage, status, metadata):
    await _raise_if_cancelled(repository, job)
    await repository.write_checkpoint(
        user_id=job.user_id,
        job_id=job.job_id,
        pipeline_run_id=job.pipeline_run_id,
        stage=stage,
        attempt=max(1, job.attempts),
        status=status,
        output_metadata=metadata,
    )
    await _raise_if_cancelled(repository, job)


async def pipeline_cycle_handler(repository: Any, job: AgentJob) -> None:
    payload = PipelineCyclePayload.model_validate(job.payload)
    authority_service = getattr(repository, "authority_service", None)
    if authority_service is not None:
        try:
            await authority_service.require_legacy_pipeline_path(user_id=job.user_id)
        except AuthorityBlocked as exc:
            raise JobExecutionBlocked(code="AUTHORITY_CANONICAL_ONLY", detail=str(exc),
                                      recovery_action="Run the canonical pipeline path.") from exc
    await _checkpoint(repository, job, "pipeline_cycle", "started", {})
    try:
        evaluation_prerequisites = await load_evaluation_prerequisites(
            user_id=job.user_id,
            fund_intelligence_repository=FundIntelligenceRepository(repository.pool),
        )
    except EvaluationPrerequisiteError as exc:
        raise JobExecutionBlocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        ) from exc
    except AuthorityBlocked as exc:
        raise JobExecutionBlocked(code="AUTHORITY_CANONICAL_ONLY", detail=str(exc),
                                  recovery_action="Resume through canonical authority.") from exc
    try:
        async def _runtime_authority_fence() -> None:
            await _raise_if_cancelled(repository, job)
            if authority_service is not None:
                await authority_service.require_legacy_pipeline_path(user_id=job.user_id)

        result = await run_one_pipeline_cycle(
            job.user_id,
            manual_one_shot=payload.manual_one_shot,
            pipeline_run_id=job.pipeline_run_id,
            identity_repository=IdentityRepository(repository.pool),
            fund_intelligence_repository=FundIntelligenceRepository(repository.pool),
            evaluation_prerequisites=evaluation_prerequisites,
            ownership_check=_runtime_authority_fence,
        )
    except EvaluationPrerequisiteError as exc:
        raise JobExecutionBlocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        ) from exc
    if not isinstance(result, PipelineExecutionResult):
        raise RuntimeError("Pipeline cycle runner returned an invalid execution result")
    metadata = result.model_dump(mode="json", exclude_none=True)
    if result.state is PipelineExecutionState.BLOCKED:
        await _checkpoint(repository, job, "pipeline_cycle", "failed", metadata)
        raise JobExecutionBlocked(
            code=result.code,
            detail=result.detail,
            recovery_action=result.recovery_action or "Correct the prerequisite and retry.",
        )
    if result.state is PipelineExecutionState.FAILED_STAGE:
        await _checkpoint(repository, job, "pipeline_cycle", "failed", metadata)
        raise RuntimeError(f"{result.code}: {result.detail}")
    await _checkpoint(repository, job, "pipeline_cycle", "succeeded", metadata)


async def _execute_company_lookup(repository: Any, job: AgentJob) -> PipelineExecutionResult:
    payload = CompanyLookupPayload.model_validate(job.payload)
    await _raise_if_cancelled(repository, job)
    resolution = (
        CompanyResolution.model_validate(payload.resolution)
        if payload.resolution
        else None
    )
    if resolution is None and not payload.website and not payload.replace_startup_id:
        resolution = await asyncio.to_thread(
            resolve_company,
            payload.company_name,
            user_id=job.user_id,
            website_hint=None,
        )

    identity_repository = IdentityRepository(repository.pool)
    existing_opportunity = None
    if payload.replace_startup_id:
        existing_opportunity = (
            await identity_repository.get_opportunity_by_legacy_projection(
                user_id=job.user_id,
                legacy_startup_id=payload.replace_startup_id,
            )
        )

    if existing_opportunity is not None:
        admission = IdentityAdmission(
            user_id=job.user_id,
            observation_id=existing_opportunity.latest_observation_id,
            status=IdentityStatus.RESOLVED,
            company_id=existing_opportunity.company_id,
            opportunity_id=existing_opportunity.opportunity_id,
            confidence=1,
            created=False,
        )
    else:
        resolution_payload = resolution.model_dump(mode="json") if resolution else None
        provider_identifiers = {}
        if resolution:
            for key, kind in (
                ("linkedin_url", "linkedin"),
                ("crunchbase_url", "crunchbase"),
                ("dealroom_url", "dealroom"),
                ("yc_url", "yc"),
            ):
                value = getattr(resolution, key, None)
                if value:
                    provider_identifiers[kind] = value
        observation = SourceObservationInput(
            user_id=job.user_id,
            channel=SourceChannel.MANUAL_LOOKUP,
            observed_name=(resolution.canonical_name if resolution else payload.company_name),
            observed_domain=(
                payload.website or (resolution.website if resolution else None)
            ),
            provider_identifiers=provider_identifiers,
            external_event_key=f"lookup:{payload.lookup_id or job.job_id}",
            lookup_id=payload.lookup_id,
            legacy_startup_id=payload.replace_startup_id,
            source_metadata={
                "source": "durable_company_lookup",
                "job_id": job.job_id,
                "pipeline_run_id": job.pipeline_run_id,
                # A supplied website or protected resolution token represents an
                # analyst-confirmed dispatch selection. Handler-generated resolver
                # output must still satisfy the service's confidence rules.
                "operator_confirmed_identity": bool(
                    payload.website or payload.resolution
                ),
            },
            resolution_payload=resolution_payload,
        )
        await _raise_if_cancelled(repository, job)
        admission = await IdentityService(identity_repository).admit(observation)
        await _raise_if_cancelled(repository, job)

    identity_metadata = {
        "observation_id": admission.observation_id,
        "status": admission.status.value,
        "confidence": admission.confidence,
    }
    if admission.company_id:
        identity_metadata["company_id"] = admission.company_id
    if admission.opportunity_id:
        identity_metadata["opportunity_id"] = admission.opportunity_id
    if admission.identity_case_id:
        identity_metadata["identity_case_id"] = admission.identity_case_id
    await _checkpoint(repository, job, "identity", "succeeded", identity_metadata)
    if admission.blocks_evaluation or not admission.opportunity_id:
        raise JobExecutionBlocked(
            code="identity_review_required",
            detail="Company identity requires an operator ruling before evaluation.",
            recovery_action=(
                "Resolve the identity case, then retry this lookup job."
            ),
        )

    try:
        evaluation_prerequisites = await load_evaluation_prerequisites(
            user_id=job.user_id,
            fund_intelligence_repository=FundIntelligenceRepository(repository.pool),
        )
    except EvaluationPrerequisiteError as exc:
        raise JobExecutionBlocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        ) from exc

    async def checkpoint(stage: str, status: str, metadata: Dict[str, Any]) -> None:
        await _checkpoint(repository, job, stage, status, metadata)

    try:
        result = await run_on_demand_lookup(
            job.user_id,
            payload.company_name,
            website=payload.website,
            lookup_query=payload.lookup_query,
            lookup_input_type=payload.lookup_input_type,
            lookup_id=payload.lookup_id,
            additional_context=payload.additional_context,
            replace_startup_id=payload.replace_startup_id,
            resolution=resolution,
            pipeline_run_id=job.pipeline_run_id,
            checkpoint=checkpoint,
            ownership_check=lambda: _raise_if_cancelled(repository, job),
            evaluation_prerequisites=evaluation_prerequisites,
            fund_intelligence_repository=FundIntelligenceRepository(repository.pool),
            institutional_context={
                "observation_id": admission.observation_id,
                "company_id": admission.company_id,
                "opportunity_id": admission.opportunity_id,
                "thesis_version_id": evaluation_prerequisites.thesis_version_id,
                "policy_version_id": evaluation_prerequisites.policy.policy_version_id,
                "policy_hash": evaluation_prerequisites.policy.policy_hash,
            },
        )
    except EvaluationPrerequisiteError as exc:
        raise JobExecutionBlocked(
            code=exc.code,
            detail=exc.detail,
            recovery_action=exc.recovery_action,
        ) from exc
    if not isinstance(result, PipelineExecutionResult):
        raise RuntimeError("Company lookup runner returned an invalid execution result")
    result_metadata = result.model_dump(mode="json", exclude_none=True)
    startup_id = result.startup_id
    if startup_id:
        await _raise_if_cancelled(repository, job)
        await identity_repository.link_legacy_projection(
            user_id=job.user_id,
            opportunity_id=admission.opportunity_id,
            legacy_startup_id=startup_id,
        )
        await _raise_if_cancelled(repository, job)
        await _checkpoint(
            repository,
            job,
            "projection",
            "succeeded",
            {
                "opportunity_id": admission.opportunity_id,
                "startup_id": startup_id,
            },
        )
    if result.state is PipelineExecutionState.BLOCKED:
        await _checkpoint(repository, job, "lookup_result", "failed", result_metadata)
    elif result.state is PipelineExecutionState.FAILED_STAGE:
        await _checkpoint(repository, job, "lookup_result", "failed", result_metadata)
    elif result.state is PipelineExecutionState.COMPLETED:
        if not startup_id:
            raise RuntimeError("Completed company lookup did not produce a startup record")
        await _checkpoint(repository, job, "lookup_result", "succeeded", result_metadata)
        await _raise_if_cancelled(repository, job)
        # Scout's canonical claims are already persisted (identity admission bridges
        # them before Reviewer/Partner run); the legacy scout/reviewer/partner stages
        # never call the canonical evaluator, so the decision brief has no
        # recommendation for a fresh dispatch without this. Best-effort: a failure
        # here must not fail the (already-successful) legacy lookup.
        try:
            evaluation = await EvaluationRepository(
                repository.pool, authority_service=getattr(repository, "authority_service", None)
            ).evaluate(
                user_id=job.user_id,
                opportunity_id=admission.opportunity_id,
                actor_id=job.user_id,
                trigger_type="dispatch",
                policy=evaluation_prerequisites.policy,
                thesis_version_id=evaluation_prerequisites.thesis_version_id,
            )
        except EvaluationLifecycleError as exc:
            await _checkpoint(
                repository,
                job,
                "canonical_evaluation",
                "succeeded",
                {"skipped": True, "reason": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001 - must not fail a completed lookup
            _logger_handlers.exception(
                "canonical evaluation bridge failed opportunity_id=%s: %s",
                admission.opportunity_id,
                type(exc).__name__,
            )
            await _checkpoint(
                repository, job, "canonical_evaluation", "failed", {"error": type(exc).__name__}
            )
        else:
            await _checkpoint(
                repository,
                job,
                "canonical_evaluation",
                "succeeded",
                {"recommendation_id": evaluation.get("recommendation_id")},
            )
    else:
        await _checkpoint(repository, job, "lookup_result", "succeeded", result_metadata)
    return result


async def company_lookup_handler(
    repository: Any, job: AgentJob
) -> LookupAttemptOutcome:
    """Execute one lookup attempt with a lossless, central lifecycle record."""
    try:
        result = await _execute_company_lookup(repository, job)
    except JobExecutionCancelled as exc:
        exc.lookup_outcome = LookupAttemptOutcome.cancelled_for_job(
            job, detail="The lookup job was cancelled before completion."
        )
        raise
    except JobExecutionBlocked as exc:
        exc.lookup_outcome = LookupAttemptOutcome.blocked_for_job(
            job,
            code=exc.code,
            detail=exc.detail or "Lookup execution is blocked.",
            recovery_action=exc.recovery_action,
        )
        raise
    except Exception as exc:
        exc.lookup_outcome = LookupAttemptOutcome.failed_for_job(
            job,
            detail=str(exc).strip() or "Lookup attempt failed unexpectedly.",
            recovery_action="Retry the lookup after checking worker and provider availability.",
        )
        raise

    lookup_outcome = LookupAttemptOutcome.from_pipeline_result(job, result)
    if result.state is PipelineExecutionState.BLOCKED:
        raise JobExecutionBlocked(
            code=result.code,
            detail=result.detail,
            recovery_action=result.recovery_action or "Correct the prerequisite and retry.",
            lookup_outcome=lookup_outcome,
        )
    if result.state is PipelineExecutionState.FAILED_STAGE:
        exc = RuntimeError(f"{result.code}: {result.detail}")
        exc.lookup_outcome = lookup_outcome
        raise exc
    if lookup_outcome.disposition is LookupAttemptDisposition.CANCELLED:
        exc = JobExecutionCancelled(result.detail)
        exc.lookup_outcome = lookup_outcome
        raise exc
    return lookup_outcome


async def evidence_refresh_handler(repository: Any, job: AgentJob) -> None:
    payload = EvidenceRefreshPayload.model_validate(job.payload)
    reason = RefreshReason(payload.reason)
    monitoring = MonitoringRepository(repository.pool)
    await _checkpoint(repository, job, "material_change", "started", {"reason": reason.value})
    check = await monitoring.check_material_change(
        user_id=job.user_id,
        opportunity_id=payload.opportunity_id,
        job_id=job.job_id,
        reason=reason,
    )
    await _checkpoint(
        repository,
        job,
        "material_change",
        "succeeded",
        {
            "material_change": check["material_change"],
            "previous_materiality_digest": check.get(
                "previous_materiality_digest",
                check.get("previous_snapshot_hash"),
            ),
            "current_materiality_digest": check.get(
                "current_materiality_digest",
                check.get("current_snapshot_hash"),
            ),
        },
    )
    reasons_requiring_plan = {
        RefreshReason.HUMAN_REQUEST,
        RefreshReason.MISSING_POLICY_EVIDENCE,
        RefreshReason.STALE_DECISIVE_EVIDENCE,
        RefreshReason.POLICY_CHANGE,
        RefreshReason.CLAIM_CORRECTION,
    }
    if not check["material_change"] and reason not in reasons_requiring_plan:
        await monitoring.settle(
            user_id=job.user_id,
            budget_reservation_id=payload.budget_reservation_id,
            actual_cost_usd=0,
        )
        await _checkpoint(repository, job, "refresh_result", "succeeded", {"result": "no_material_change"})
        return

    missing = await monitoring.current_missing_evidence(
        user_id=job.user_id,
        opportunity_id=payload.opportunity_id,
    )
    plan = await EvidenceRepository(repository.pool).create_plan(
        user_id=job.user_id,
        opportunity_id=payload.opportunity_id,
        trigger_type=reason.value,
        missing_evidence=missing,
        search_questions=[f"What verifiable evidence resolves: {item}?" for item in missing[:10]],
        max_artifacts=5,
        budget_usd=0,
    )
    await _checkpoint(
        repository,
        job,
        "refresh_plan",
        "succeeded",
        {"evidence_plan_id": plan.evidence_plan_id, "missing_evidence_count": len(missing)},
    )
    await monitoring.settle(
        user_id=job.user_id,
        budget_reservation_id=payload.budget_reservation_id,
        actual_cost_usd=0,
    )


def build_handlers(repository: Any):
    return {
        JobType.PIPELINE_CYCLE: partial(pipeline_cycle_handler, repository),
        JobType.COMPANY_LOOKUP: partial(company_lookup_handler, repository),
        JobType.EVIDENCE_REFRESH: partial(evidence_refresh_handler, repository),
    }
