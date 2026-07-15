import asyncio
import importlib

import pytest

from jobs.models import AgentJob, JobType, PipelineCyclePayload


def _job(user_id="user-a"):
    return AgentJob(
        user_id=user_id,
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key=f"cycle:{user_id}:1",
        payload=PipelineCyclePayload(user_id=user_id),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )


class _Repository:
    def __init__(self, job=None):
        self.job = job
        self.succeeded = []
        self.retried = []
        self.heartbeats = []

    async def claim_next(self, **kwargs):
        job, self.job = self.job, None
        return job

    async def heartbeat(self, **kwargs):
        self.heartbeats.append(kwargs)
        return True

    async def succeed(self, **kwargs):
        self.succeeded.append(kwargs)
        return True

    async def retry(self, **kwargs):
        self.retried.append(kwargs)
        return None


@pytest.mark.asyncio
async def test_worker_claims_one_parent_job_and_completes_it_once():
    worker_module = importlib.import_module("jobs.worker")
    job = _job()
    repository = _Repository(job)
    handled = []

    async def handler(job):
        handled.append(job.job_id)

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    assert await worker.process_one() is True
    assert handled == [job.job_id]
    assert len(repository.succeeded) == 1
    assert repository.retried == []


@pytest.mark.asyncio
async def test_worker_retries_handler_failure_and_stops_heartbeat():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job())

    async def handler(job):
        await asyncio.sleep(0.02)
        raise RuntimeError("provider unavailable")

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=0.005,
        lease_seconds=1,
    )

    assert await worker.process_one() is True
    assert len(repository.retried) == 1
    assert "provider unavailable" in repository.retried[0]["error"]
    assert repository.heartbeats


@pytest.mark.asyncio
async def test_worker_enforces_per_tenant_concurrency():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository()
    active = 0
    maximum = 0

    async def handler(job):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.02)
        active -= 1

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        global_concurrency=4,
        per_tenant_concurrency=1,
    )

    await asyncio.gather(worker.execute(_job("user-a")), worker.execute(_job("user-a")))
    assert maximum == 1


@pytest.mark.asyncio
async def test_worker_poll_backstop_wakes_when_notified():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository()
    worker = worker_module.DurableJobWorker(
        repository,
        handlers={},
        worker_id="worker-a",
        poll_interval_seconds=30,
    )

    waiter = asyncio.create_task(worker.wait_for_work())
    await asyncio.sleep(0)
    worker.notify()
    await asyncio.wait_for(waiter, timeout=0.2)
