"""Durable job handlers that adapt AgentJob payloads to existing pipeline services."""

from __future__ import annotations

import asyncio
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
from evidence.repository import EvidenceRepository
from monitoring.models import RefreshReason
from monitoring.repository import MonitoringRepository
from pipeline_runner import run_on_demand_lookup, run_one_pipeline_cycle
from resolver.company_resolver import CompanyResolution, resolve_company


async def _raise_if_cancelled(repository: Any, job: AgentJob) -> None:
    getter = getattr(repository, "get_job", None)
    if getter is None:
        return
    current = await getter(user_id=job.user_id, job_id=job.job_id)
    if current is not None and current.status is JobStatus.CANCELLED:
        raise JobExecutionCancelled(f"Job {job.job_id} was cancelled")


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
    await _checkpoint(repository, job, "pipeline_cycle", "started", {})
    await run_one_pipeline_cycle(
        job.user_id,
        manual_one_shot=payload.manual_one_shot,
        pipeline_run_id=job.pipeline_run_id,
        identity_repository=IdentityRepository(repository.pool),
    )
    await _checkpoint(repository, job, "pipeline_cycle", "succeeded", {})


async def company_lookup_handler(repository: Any, job: AgentJob) -> None:
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
        admission = await IdentityService(identity_repository).admit(observation)

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

    async def checkpoint(stage: str, status: str, metadata: Dict[str, Any]) -> None:
        await _checkpoint(repository, job, stage, status, metadata)

    startup_id = await run_on_demand_lookup(
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
        institutional_context={
            "observation_id": admission.observation_id,
            "company_id": admission.company_id,
            "opportunity_id": admission.opportunity_id,
        },
    )
    if startup_id is not None:
        await identity_repository.link_legacy_projection(
            user_id=job.user_id,
            opportunity_id=admission.opportunity_id,
            legacy_startup_id=startup_id,
        )
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
    await _checkpoint(
        repository,
        job,
        "lookup_result",
        "succeeded" if startup_id else "failed",
        {"startup_id": startup_id} if startup_id else {},
    )
    if startup_id is None:
        raise RuntimeError("Company lookup completed without a startup record")


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
            "previous_snapshot_hash": check.get("previous_snapshot_hash"),
            "current_snapshot_hash": check.get("current_snapshot_hash"),
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
