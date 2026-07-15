"""Durable job handlers that adapt AgentJob payloads to existing pipeline services."""

from __future__ import annotations

from functools import partial
from typing import Any, Dict

from jobs.models import AgentJob, CompanyLookupPayload, JobType, PipelineCyclePayload
from pipeline_runner import run_on_demand_lookup, run_one_pipeline_cycle
from resolver.company_resolver import CompanyResolution


async def _checkpoint(repository, job, stage, status, metadata):
    await repository.write_checkpoint(
        user_id=job.user_id,
        job_id=job.job_id,
        pipeline_run_id=job.pipeline_run_id,
        stage=stage,
        attempt=max(1, job.attempts),
        status=status,
        output_metadata=metadata,
    )


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
    resolution = CompanyResolution.model_validate(payload.resolution) if payload.resolution else None

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
