import asyncio
import importlib

import pytest

from jobs.models import (
    AgentJob,
    JobExecutionBlocked,
    JobExecutionCancelled,
    JobType,
    PipelineCyclePayload,
)


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
    def __init__(self, job=None, *, heartbeat_result=True):
        self.job = job
        self.heartbeat_result = heartbeat_result
        self.succeeded = []
        self.retried = []
        self.blocked = []
        self.heartbeats = []

    async def claim_next(self, **kwargs):
        job, self.job = self.job, None
        return job

    async def heartbeat(self, **kwargs):
        self.heartbeats.append(kwargs)
        return self.heartbeat_result

    async def succeed(self, **kwargs):
        self.succeeded.append(kwargs)
        return True

    async def retry(self, **kwargs):
        self.retried.append(kwargs)
        return self.job or _job()

    async def block(self, **kwargs):
        self.blocked.append(kwargs)
        return self.job or _job()


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
async def test_worker_does_not_retry_a_cooperatively_cancelled_job():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job())

    async def handler(job):
        raise JobExecutionCancelled("cancelled between checkpoints")

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    assert await worker.process_one() is True
    assert repository.succeeded == []
    assert repository.retried == []


@pytest.mark.asyncio
async def test_worker_blocks_operator_action_without_retrying():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job())

    async def handler(job):
        raise JobExecutionBlocked(
            code="identity_review_required",
            detail="Ambiguous company identity.",
            recovery_action="Resolve the identity case and retry.",
        )

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    assert await worker.process_one() is True
    assert repository.retried == []
    assert repository.succeeded == []
    assert repository.blocked[0]["code"] == "identity_review_required"


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


@pytest.mark.asyncio
async def test_rejected_heartbeat_fences_handler_before_authoritative_publication():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job(), heartbeat_result=False)
    entered = asyncio.Event()
    published = []
    fences = []

    async def handler(job):
        fences.append(worker_module.current_lease_fence())
        entered.set()
        await asyncio.sleep(1)
        published.append(job.job_id)

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=0.001,
        lease_seconds=1,
    )

    await worker.execute(_job())

    assert entered.is_set()
    assert repository.heartbeats
    assert fences[0].lost is True
    assert published == []
    assert repository.succeeded == []
    assert repository.retried == []
    assert repository.blocked == []


@pytest.mark.asyncio
@pytest.mark.parametrize("transition", ["succeed", "retry", "block"])
async def test_rejected_terminal_transition_is_lease_loss_not_success(
    monkeypatch, transition
):
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job())
    outcomes = []
    fences = []

    monkeypatch.setattr(
        worker_module.metrics,
        "observe_durable_job_run",
        lambda **kwargs: outcomes.append(kwargs["outcome"]),
    )

    async def rejected(**kwargs):
        return False if transition == "succeed" else None

    setattr(repository, transition, rejected)

    if transition == "succeed":
        async def handler(_job):
            fences.append(worker_module.current_lease_fence())
            return None
    elif transition == "retry":
        async def handler(_job):
            fences.append(worker_module.current_lease_fence())
            raise RuntimeError("provider failed")
    else:
        async def handler(_job):
            fences.append(worker_module.current_lease_fence())
            raise JobExecutionBlocked(
                code="identity_review_required",
                detail="Ambiguous company identity.",
                recovery_action="Resolve identity and retry.",
            )

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    await worker.execute(_job())

    assert outcomes == ["lease_lost"]
    assert fences[0].lost is True


@pytest.mark.asyncio
async def test_missing_handler_rejected_retry_is_lease_loss(monkeypatch):
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository(_job())
    outcomes = []

    async def rejected(**_kwargs):
        return None

    repository.retry = rejected
    monkeypatch.setattr(
        worker_module.metrics,
        "observe_durable_job_run",
        lambda **kwargs: outcomes.append(kwargs["outcome"]),
    )
    worker = worker_module.DurableJobWorker(
        repository,
        handlers={},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    await worker.execute(_job())

    assert outcomes == ["lease_lost"]
