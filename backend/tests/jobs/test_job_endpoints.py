from fastapi.testclient import TestClient

from jobs.models import AgentJob, JobStatus, JobType, PipelineCyclePayload
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


class _Repository:
    def __init__(self, jobs):
        self.jobs = {job.job_id: job for job in jobs}

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
        return updated

    async def cancel(self, *, user_id, job_id):
        job = await self.get_job(user_id=user_id, job_id=job_id)
        if job is None:
            return None
        if job.status is JobStatus.SUCCEEDED:
            return job
        updated = job.model_copy(update={"status": JobStatus.CANCELLED})
        self.jobs[job_id] = updated
        return updated


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
