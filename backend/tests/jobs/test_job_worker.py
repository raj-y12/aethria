import asyncio
import importlib
import threading

import pytest

from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    JobExecutionBlocked,
    JobExecutionCancelled,
    JobType,
    PipelineCyclePayload,
)
from jobs.lookup_outcomes import LookupAttemptOutcome
from pipeline_execution import PipelineExecutionResult


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


def _lookup_job():
    return AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:atomic-outcome",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-atomic-outcome",
        ),
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
async def test_worker_loop_retries_after_transient_claim_failure():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository()
    attempts = 0
    worker = worker_module.DurableJobWorker(
        repository,
        handlers={},
        worker_id="worker-a",
        poll_interval_seconds=0.05,
    )

    async def claim_next(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database temporarily unavailable")
        worker._stopping.set()
        worker.notify()
        return None

    repository.claim_next = claim_next

    runner = asyncio.create_task(worker._run())
    await asyncio.wait_for(runner, timeout=0.5)

    assert attempts == 2
    assert runner.exception() is None


@pytest.mark.asyncio
async def test_worker_loop_retries_after_transient_lease_recovery_failure():
    worker_module = importlib.import_module("jobs.worker")
    repository = _Repository()
    recovery_attempts = 0
    worker = worker_module.DurableJobWorker(
        repository,
        handlers={},
        worker_id="worker-a",
        poll_interval_seconds=0.05,
    )

    async def recover_exhausted_leases():
        nonlocal recovery_attempts
        recovery_attempts += 1
        if recovery_attempts == 1:
            raise RuntimeError("database temporarily unavailable")

    async def claim_next(**_kwargs):
        worker._stopping.set()
        worker.notify()
        return None

    repository.dead_letter_exhausted_leases = recover_exhausted_leases
    repository.claim_next = claim_next

    runner = asyncio.create_task(worker._run())
    await asyncio.wait_for(runner, timeout=0.5)

    assert recovery_attempts == 2
    assert runner.exception() is None


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


@pytest.mark.asyncio
async def test_lookup_terminal_outcome_is_handed_to_conditional_success_transition():
    worker_module = importlib.import_module("jobs.worker")
    job = _lookup_job()
    repository = _Repository(job)
    outcome = LookupAttemptOutcome.from_pipeline_result(
        job,
        PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="startup-1",
        ),
    )

    async def handler(_job):
        return outcome

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.COMPANY_LOOKUP: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    await worker.execute(job)

    assert repository.succeeded[0]["lookup_outcome"] == outcome


@pytest.mark.asyncio
async def test_lookup_cooperative_cancellation_uses_owned_atomic_transition():
    worker_module = importlib.import_module("jobs.worker")
    job = _lookup_job()
    repository = _Repository(job)
    repository.cancelled_owned = []

    async def cancel_owned(**kwargs):
        repository.cancelled_owned.append(kwargs)
        return job.model_copy(update={"status": "cancelled"})

    repository.cancel_owned = cancel_owned
    outcome = LookupAttemptOutcome.cancelled_for_job(
        job, detail="Lookup was cancelled at a safe boundary."
    )

    async def handler(_job):
        exc = JobExecutionCancelled("cancelled")
        exc.lookup_outcome = outcome
        raise exc

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.COMPANY_LOOKUP: handler},
        worker_id="worker-a",
        heartbeat_seconds=60,
    )

    await worker.execute(job)

    assert repository.cancelled_owned[0]["lookup_outcome"] == outcome
    assert repository.succeeded == []
    assert repository.retried == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "targeted_update",
        "row_upsert",
        "direct_insert",
        "direct_update",
        "direct_upsert",
        "direct_delete",
    ],
)
async def test_rejected_heartbeat_fences_a_to_thread_storage_write_after_cancel(
    monkeypatch,
    mutation,
):
    """Cancelling the task cannot cancel its already-running worker thread."""
    worker_module = importlib.import_module("jobs.worker")
    pipeline_module = importlib.import_module("pipeline_runner")
    repository = _Repository(_job(), heartbeat_result=False)
    thread_entered = threading.Event()
    release_thread = threading.Event()
    thread_finished = threading.Event()
    writes = []
    errors = []

    class _Query:
        def update(self, *_args, **_kwargs):
            return self

        def insert(self, *_args, **_kwargs):
            return self

        def upsert(self, *_args, **_kwargs):
            return self

        def delete(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            writes.append("canonical-write")

    class _Client:
        def table(self, _name):
            return _Query()

    monkeypatch.setattr(pipeline_module, "get_service_client", lambda: _Client())

    async def handler(_job):
        storage = await asyncio.to_thread(
            pipeline_module._build_storage_sync,
            "user-a",
        )

        def delayed_write():
            thread_entered.set()
            release_thread.wait(timeout=2)
            try:
                if mutation == "targeted_update":
                    storage._update_startup_columns(
                        "startup-1", {"updated_at": "after-lease-loss"}
                    )
                elif mutation == "row_upsert":
                    storage.upsert_startup_dict({"startup_id": "startup-1"})
                else:
                    operation = mutation.removeprefix("direct_")
                    query = storage._client.table("pipeline-authority")
                    getattr(query, operation)({"status": "after-lease-loss"}).execute()
            except Exception as exc:  # expected once the storage fence exists
                errors.append(exc)
            finally:
                thread_finished.set()

        await asyncio.to_thread(delayed_write)

    worker = worker_module.DurableJobWorker(
        repository,
        handlers={JobType.PIPELINE_CYCLE: handler},
        worker_id="worker-a",
        heartbeat_seconds=0.001,
        lease_seconds=1,
    )

    await worker.execute(_job())
    assert thread_entered.is_set()
    release_thread.set()
    assert await asyncio.to_thread(thread_finished.wait, 1)

    assert writes == []
    assert errors and "lease" in str(errors[0]).lower()
