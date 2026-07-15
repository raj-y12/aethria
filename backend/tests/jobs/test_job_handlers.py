import importlib

import pytest

from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    JobExecutionCancelled,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)


class _Repository:
    pool = object()

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

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **kwargs):
            return None

        async def link_legacy_projection(self, **kwargs):
            return object()

    class IdentityService:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            return type(
                "Admission",
                (),
                {
                    "observation_id": "observation-1",
                    "status": type("Status", (), {"value": "resolved"})(),
                    "company_id": "company-1",
                    "opportunity_id": "opportunity-1",
                    "identity_case_id": None,
                    "confidence": 1.0,
                    "blocks_evaluation": False,
                },
            )()

    async def run(user_id, company_name, **kwargs):
        calls.append((user_id, company_name, kwargs))
        await kwargs["checkpoint"]("scout", "succeeded", {"startup_id": "s1"})
        return "s1"

    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
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
    assert repository.checkpoints[0]["stage"] == "identity"
    assert repository.checkpoints[1]["stage"] == "scout"
    assert repository.checkpoints[-1]["stage"] == "lookup_result"


@pytest.mark.asyncio
async def test_lookup_handler_observes_cancellation_between_checkpoints(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:cancelled",
        payload=CompanyLookupPayload(user_id="user-a", company_name="Acme"),
        attempts=1,
        status=JobStatus.RUNNING,
    )

    async def get_job(**kwargs):
        return job.model_copy(update={"status": JobStatus.CANCELLED})

    repository.get_job = get_job

    with pytest.raises(JobExecutionCancelled):
        await handlers.company_lookup_handler(repository, job)
