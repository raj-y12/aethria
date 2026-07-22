from fastapi.testclient import TestClient

from jobs.lookup_outcomes import LookupOutcomeStoreUnavailable
from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    JobCancellationDisposition,
    JobCancellationResult,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)
from security.rate_limiter import InMemorySecurityStore


def _job(*, user_id="user-a", status=JobStatus.DEAD_LETTER):
    return AgentJob(
        job_id="64d53f3f-1795-4636-bda7-c55fbf420dc3",
        user_id=user_id,
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key=f"cycle:{user_id}:1",
        payload=PipelineCyclePayload(user_id=user_id, manual_one_shot=True),
        status=status,
        attempts=3,
        max_attempts=3,
        last_error="postgres://secret@host/provider stack trace",
    )


def _lookup_job(*, user_id="user-a", status=JobStatus.DEAD_LETTER):
    return AgentJob(
        job_id="74d53f3f-1795-4636-bda7-c55fbf420dc4",
        user_id=user_id,
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key=f"lookup:{user_id}:lookup-contract-1",
        payload=CompanyLookupPayload(
            user_id=user_id,
            company_name="Acme",
            lookup_id="lookup-contract-1",
        ),
        status=status,
        attempts=3,
        max_attempts=3,
        pipeline_run_id="pipeline-contract-1",
        last_error="provider unavailable",
    )


class _Repository:
    def __init__(self, jobs):
        self.jobs = {job.job_id: job for job in jobs}
        self.atomic_outcomes = []

    async def get_job(self, *, user_id, job_id):
        job = self.jobs.get(job_id)
        return job if job is not None and job.user_id == user_id else None

    async def list_jobs(self, *, user_id, statuses=None, limit=50):
        allowed = {JobStatus(status) for status in statuses} if statuses else set(JobStatus)
        return [
            job
            for job in self.jobs.values()
            if job.user_id == user_id and job.status in allowed
        ][:limit]

    async def requeue(self, *, user_id, job_id):
        job = await self.get_job(user_id=user_id, job_id=job_id)
        if job is None or job.status not in {
            JobStatus.FAILED,
            JobStatus.DEAD_LETTER,
            JobStatus.BLOCKED,
            JobStatus.RETRY_WAIT,
        }:
            return None
        updated = job.model_copy(
            update={
                "status": JobStatus.QUEUED,
                "max_attempts": max(job.max_attempts, job.attempts + 1),
                "last_error": None,
            }
        )
        self.jobs[job_id] = updated
        if updated.job_type is JobType.COMPANY_LOOKUP:
            from jobs.lookup_outcomes import LookupAttemptOutcome

            self.atomic_outcomes.append(
                LookupAttemptOutcome.accepted_for_job(updated)
            )
        return updated

    async def cancel(self, *, user_id, job_id):
        job = await self.get_job(user_id=user_id, job_id=job_id)
        if job is None:
            return JobCancellationResult(
                disposition=JobCancellationDisposition.NOT_FOUND,
            )
        if job.status is JobStatus.SUCCEEDED:
            return JobCancellationResult(
                disposition=JobCancellationDisposition.REJECTED,
                job=job,
            )
        if job.status is JobStatus.CANCELLED:
            return JobCancellationResult(
                disposition=JobCancellationDisposition.ALREADY_CANCELLED,
                job=job,
            )
        updated = job.model_copy(update={"status": JobStatus.CANCELLED})
        self.jobs[job_id] = updated
        if updated.job_type is JobType.COMPANY_LOOKUP:
            from jobs.lookup_outcomes import LookupAttemptOutcome

            self.atomic_outcomes.append(
                LookupAttemptOutcome.cancelled_for_job(
                    job, detail="The lookup job was cancelled by the operator."
                )
            )
        return JobCancellationResult(
            disposition=JobCancellationDisposition.TRANSITIONED,
            job=updated,
        )


def _client(monkeypatch, repository, *, user_id="user-a"):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda token: user_id)
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.durable_job_repository = repository
    return TestClient(api.app)


def test_get_job_is_tenant_scoped_and_hides_raw_errors(monkeypatch):
    repository = _Repository([_job()])
    own = _client(monkeypatch, repository).get(
        "/api/jobs/64d53f3f-1795-4636-bda7-c55fbf420dc3",
        headers={"Authorization": "Bearer t"},
    )

    assert own.status_code == 200
    assert own.json()["status"] == "dead_letter"
    assert own.json()["error"] == "Execution failed after all retry attempts."
    assert "postgres" not in own.text

    other = _client(monkeypatch, repository, user_id="user-b").get(
        "/api/jobs/64d53f3f-1795-4636-bda7-c55fbf420dc3",
        headers={"Authorization": "Bearer t"},
    )
    assert other.status_code == 404


def test_list_jobs_maps_queued_to_accepted_and_filters_status(monkeypatch):
    accepted = _job(status=JobStatus.QUEUED).model_copy(
        update={"job_id": "9a1c03b1-0e78-4b65-b97e-781510c97638"}
    )
    repository = _Repository([_job(), accepted])

    response = _client(monkeypatch, repository).get(
        "/api/jobs?status=accepted,dead_letter&limit=10",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 200
    assert {job["status"] for job in response.json()["jobs"]} == {
        "accepted",
        "dead_letter",
    }


def test_blocked_job_exposes_safe_machine_code_and_recovery_action(monkeypatch):
    blocked = _job(status=JobStatus.BLOCKED).model_copy(
        update={
            "block_code": "identity_review_required",
            "block_detail": "postgres://secret@host/raw ambiguity payload",
            "recovery_action": "Resolve the identity case, then retry this job.",
        }
    )
    response = _client(monkeypatch, _Repository([blocked])).get(
        f"/api/jobs/{blocked.job_id}", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 200
    assert response.json()["block_code"] == "identity_review_required"
    assert "Resolve the identity case" in response.json()["recovery_action"]
    assert "secret" not in response.text


def test_retry_reuses_same_job_and_adds_one_safe_attempt(monkeypatch):
    repository = _Repository([_job()])
    response = _client(monkeypatch, repository).post(
        "/api/jobs/64d53f3f-1795-4636-bda7-c55fbf420dc3/retry",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "64d53f3f-1795-4636-bda7-c55fbf420dc3"
    assert response.json()["status"] == "accepted"
    assert response.json()["attempts"] == 3
    assert response.json()["max_attempts"] == 4


def test_lookup_retry_uses_repository_atomic_outcome_before_returning_accepted(monkeypatch):
    import routers.jobs as jobs_router

    async def persist(_outcome):
        raise AssertionError("router must not publish outside the job transaction")

    monkeypatch.setattr(jobs_router, "_persist_lookup_attempt", persist, raising=False)
    repository = _Repository([_lookup_job()])

    response = _client(monkeypatch, repository).post(
        "/api/jobs/74d53f3f-1795-4636-bda7-c55fbf420dc4/retry",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    assert repository.atomic_outcomes[0].lookup_id == "lookup-contract-1"
    assert repository.atomic_outcomes[0].attempt == 4
    assert repository.atomic_outcomes[0].disposition.value == "accepted"


def test_lookup_retry_explicitly_fails_if_attempt_status_cannot_be_persisted(monkeypatch):
    repository = _Repository([_lookup_job()])

    async def fail_atomic_requeue(**_kwargs):
        raise LookupOutcomeStoreUnavailable("atomic lookup outcome write failed")

    repository.requeue = fail_atomic_requeue

    response = _client(monkeypatch, repository).post(
        "/api/jobs/74d53f3f-1795-4636-bda7-c55fbf420dc4/retry",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "lookup_outcome_store_unavailable"


def test_lookup_cancel_uses_repository_atomic_outcome_without_router_write(monkeypatch):
    import routers.jobs as jobs_router

    async def persist(_outcome):
        raise AssertionError("router must not publish outside the job transaction")

    monkeypatch.setattr(jobs_router, "_persist_lookup_attempt", persist, raising=False)
    repository = _Repository([_lookup_job(status=JobStatus.RUNNING)])

    response = _client(monkeypatch, repository).post(
        "/api/jobs/74d53f3f-1795-4636-bda7-c55fbf420dc4/cancel",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    assert repository.atomic_outcomes[0].disposition.value == "cancelled"
    assert repository.atomic_outcomes[0].attempt == 3


def test_succeeded_job_cannot_be_retried_or_cancelled(monkeypatch):
    succeeded = _job(status=JobStatus.SUCCEEDED)
    repository = _Repository([succeeded])
    client = _client(monkeypatch, repository)

    retry = client.post(
        f"/api/jobs/{succeeded.job_id}/retry", headers={"Authorization": "Bearer t"}
    )
    cancel = client.post(
        f"/api/jobs/{succeeded.job_id}/cancel", headers={"Authorization": "Bearer t"}
    )

    assert retry.status_code == 409
    assert cancel.status_code == 409
    assert "secret" not in retry.text + cancel.text


def test_cancel_is_idempotent(monkeypatch):
    running = _job(status=JobStatus.RUNNING)
    repository = _Repository([running])
    client = _client(monkeypatch, repository)

    first = client.post(
        f"/api/jobs/{running.job_id}/cancel", headers={"Authorization": "Bearer t"}
    )
    second = client.post(
        f"/api/jobs/{running.job_id}/cancel", headers={"Authorization": "Bearer t"}
    )

    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == second.json()["status"] == "cancelled"


def test_cancel_returns_conflict_when_running_job_succeeds_during_transition(
    monkeypatch,
):
    running = _job(status=JobStatus.RUNNING)
    repository = _Repository([running])

    async def finish_before_cancel(*, user_id, job_id):
        succeeded = running.model_copy(update={"status": JobStatus.SUCCEEDED})
        repository.jobs[job_id] = succeeded
        return JobCancellationResult(
            disposition=JobCancellationDisposition.REJECTED,
            job=succeeded,
        )

    repository.cancel = finish_before_cancel
    response = _client(monkeypatch, repository).post(
        f"/api/jobs/{running.job_id}/cancel",
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Job state changed; refresh before cancelling"
