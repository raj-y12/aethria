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
    JobExecutionBlocked,
    JobExecutionCancelled,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)
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


def build_handlers(repository: Any):
    return {
        JobType.PIPELINE_CYCLE: partial(pipeline_cycle_handler, repository),
        JobType.COMPANY_LOOKUP: partial(company_lookup_handler, repository),
    }
