import importlib

import pytest

from jobs.models import AgentJob, CompanyLookupPayload, JobType, PipelineCyclePayload


class _Repository:
    def __init__(self):
        self.checkpoints = []

    async def write_checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
async def test_cycle_handler_passes_job_tenant_and_stable_pipeline_run(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    calls = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))

    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle-1",
        payload=PipelineCyclePayload(user_id="user-a", manual_one_shot=True),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.pipeline_cycle_handler(repository, job)

    assert calls == [
        (
            "user-a",
            {"manual_one_shot": True, "pipeline_run_id": job.pipeline_run_id},
        )
    ]
    assert [item["stage"] for item in repository.checkpoints] == [
        "pipeline_cycle",
        "pipeline_cycle",
    ]


@pytest.mark.asyncio
async def test_lookup_handler_writes_pipeline_checkpoints_and_reconstructs_resolution(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    calls = []

    async def run(user_id, company_name, **kwargs):
        calls.append((user_id, company_name, kwargs))
        await kwargs["checkpoint"]("scout", "succeeded", {"startup_id": "s1"})
        return "s1"

    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup-1",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-1",
            resolution={"query": "Acme", "canonical_name": "Acme", "resolution_status": "FOUND"},
        ),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.company_lookup_handler(repository, job)

    assert calls[0][0:2] == ("user-a", "Acme")
    assert calls[0][2]["pipeline_run_id"] == job.pipeline_run_id
    assert calls[0][2]["resolution"].canonical_name == "Acme"
    assert repository.checkpoints[0]["stage"] == "scout"
    assert repository.checkpoints[-1]["stage"] == "lookup_result"
