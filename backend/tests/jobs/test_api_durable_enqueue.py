from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jobs.models import (
    AgentJob,
    JobCancellationDisposition,
    JobCancellationResult,
    JobStatus,
    JobType,
)
from jobs.lookup_outcomes import LookupAttemptOutcome, LookupOutcomeStoreUnavailable
from security.rate_limiter import InMemorySecurityStore


def test_direct_postgres_runtime_requires_durable_services(monkeypatch):
    import api

    monkeypatch.delenv("USE_SUPABASE_STORAGE", raising=False)
    monkeypatch.setattr(api, "database_dsn", lambda: "postgresql://local/aethria")
    monkeypatch.setattr(api.env_config, "use_supabase_storage", lambda: False)

    assert api._durable_jobs_required() is True


def test_explicit_local_compatibility_switch_does_not_disable_configured_postgres(
    monkeypatch,
):
    import api

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(api, "database_dsn", lambda: "postgresql://local/aethria")
    monkeypatch.setattr(api.env_config, "use_supabase_storage", lambda: False)

    assert api._durable_jobs_required() is True


@pytest.mark.asyncio
async def test_durable_startup_fails_closed_when_pool_creation_fails(monkeypatch):
    import api

    async def fail_pool_creation():
        raise ConnectionRefusedError("local database is unavailable")

    async def no_op_cleanup(_app):
        return None

    monkeypatch.setattr(api, "create_durable_job_pool", fail_pool_creation)
    monkeypatch.setattr(api, "_stop_durable_job_services", no_op_cleanup)
    monkeypatch.setattr(api, "_durable_jobs_required", lambda: True)

    with pytest.raises(RuntimeError, match="durable_job_store_unavailable:ConnectionRefusedError"):
        await api._start_durable_job_services(
            SimpleNamespace(state=SimpleNamespace())
        )


class _Repository:
    def __init__(self):
        self.enqueued = []
        self.cancelled = []
        self.atomic_outcomes = []

    async def enqueue(self, job):
        self.enqueued.append(job)
        return job

    async def get_by_idempotency_key(self, *, user_id, idempotency_key):
        for job in self.enqueued:
            if job.user_id == user_id and job.idempotency_key == idempotency_key:
                return job
        return None

    async def cancel(self, *, user_id, job_id):
        self.cancelled.append((user_id, job_id))
        for job in self.enqueued:
            if job.user_id == user_id and job.job_id == job_id:
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
                self.atomic_outcomes.append(
                    LookupAttemptOutcome.cancelled_for_job(
                        job, detail="The lookup job was cancelled by the operator."
                    )
                )
                return JobCancellationResult(
                    disposition=JobCancellationDisposition.TRANSITIONED,
                    job=job.model_copy(update={"status": JobStatus.CANCELLED}),
                )
        return JobCancellationResult(
            disposition=JobCancellationDisposition.NOT_FOUND,
        )

    async def tenant_queue_depths(self, *, user_id):
        assert user_id == "user_a"
        return {
            "pipeline_cycle:queued": 2,
            "company_lookup:running": 1,
            "company_lookup:retry_wait": 3,
            "company_lookup:dead_letter": 1,
            "outbox:pending": 4,
        }

    async def global_queue_depths(self):
        return await self.tenant_queue_depths(user_id="user_a")


class _FailingStatusRepository(_Repository):
    async def tenant_queue_depths(self, *, user_id):
        raise RuntimeError("database temporarily unavailable")


class _BackgroundTask:
    def __init__(self, *, done=False, error=None, cancelled=False):
        self._done = done
        self._error = error
        self._cancelled = cancelled

    def done(self):
        return self._done

    def cancelled(self):
        return self._cancelled

    def exception(self):
        return self._error


class _DurableWorker:
    def __init__(self, task=None):
        self._runner = task or _BackgroundTask()

    def notify(self):
        pass


class _DurableOutboxPublisher:
    def __init__(self, task=None):
        self._runner = task or _BackgroundTask()


def _configure_auth(monkeypatch, api):
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )


def _configure_durable(monkeypatch, api, repository):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(api, "_durable_job_repository", repository, raising=False)
    monkeypatch.setattr(api, "_durable_job_worker", _DurableWorker(), raising=False)
    monkeypatch.setattr(
        api,
        "_durable_outbox_publisher",
        _DurableOutboxPublisher(),
        raising=False,
    )
    monkeypatch.setattr(api, "_durable_job_error", None, raising=False)
    _configure_auth(monkeypatch, api)


def test_lookup_endpoint_accepts_a_durable_company_job(monkeypatch):
    import api

    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)

    response = TestClient(api.app).post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme https://acme.example", "lookup_id": "lookup-acme-123"},
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["job_id"] == repository.enqueued[0].job_id
    assert body["accepted_at"]
    assert body["lookup_id"] == "lookup-acme-123"
    job = repository.enqueued[0]
    assert job.job_type is JobType.COMPANY_LOOKUP
    assert job.user_id == "user_a"
    assert job.payload.lookup_id == "lookup-acme-123"
    assert job.payload.website == "acme.example"


def test_lookup_serializes_resolution_into_durable_payload(monkeypatch):
    import api
    from resolver.company_resolver import CompanyResolution

    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)
    resolution = CompanyResolution(
        query="Acme",
        canonical_name="Acme",
        resolution_status="FOUND",
        website="https://acme.example",
    )
    token = api._cache_lookup_resolution("user_a", resolution)

    response = TestClient(api.app).post(
        "/api/startups/lookup",
        json={
            "lookup_input": "Acme",
            "lookup_id": "lookup-acme-456",
            "resolution_token": token,
        },
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    serialized = repository.enqueued[0].payload.resolution
    assert isinstance(serialized, dict)
    assert serialized["canonical_name"] == "Acme"
    assert serialized["website"] == "https://acme.example"


def test_manual_agent_trigger_accepts_a_durable_cycle_job(monkeypatch):
    import api

    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)
    monkeypatch.setattr(
        api,
        "load_settings",
        lambda user_id: {"agent_config": {"scouts_enabled": False}},
    )
    monkeypatch.setattr(api, "get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(api, "get_active_thesis", lambda client, user_id: SimpleNamespace())

    response = TestClient(api.app).post(
        "/api/agents/trigger", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["job_id"] == repository.enqueued[0].job_id
    assert body["accepted_at"]
    job = repository.enqueued[0]
    assert job.job_type is JobType.PIPELINE_CYCLE
    assert job.payload.manual_one_shot is True


def test_supabase_mode_fails_closed_when_durable_store_is_unavailable(monkeypatch):
    import api

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(api, "_durable_job_repository", None, raising=False)
    monkeypatch.setattr(
        api,
        "_durable_job_error",
        "Durable jobs require DATABASE_URL or SUPABASE_DB_URL",
        raising=False,
    )
    _configure_auth(monkeypatch, api)

    client = TestClient(api.app)
    first = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme", "lookup_id": "lookup-store-001"},
        headers={"Authorization": "Bearer t"},
    )
    second = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme", "lookup_id": "lookup-store-001"},
        headers={"Authorization": "Bearer t"},
    )

    assert first.status_code == 503
    assert first.json() == {
        "status": "unavailable",
        "reason": "durable_job_store_unavailable",
    }
    assert second.status_code == 503
    assert second.json()["reason"] == "durable_job_store_unavailable"


def test_lookup_cancel_cancels_the_matching_durable_job(monkeypatch):
    import api

    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)
    job = AgentJob(
        user_id="user_a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user_a:lookup-cancel-001",
        payload={
            "user_id": "user_a",
            "company_name": "Acme",
            "lookup_id": "lookup-cancel-001",
        },
    )
    repository.enqueued.append(job)

    response = TestClient(api.app).post(
        "/api/startups/lookup/cancel",
        json={"lookup_id": "lookup-cancel-001"},
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 202
    assert repository.cancelled == [("user_a", job.job_id)]
    assert repository.atomic_outcomes[0].attempt == 1
    assert repository.atomic_outcomes[0].disposition.value == "cancelled"
    assert response.json()["job_ids"] == [job.job_id]


def test_primary_lookup_cancel_surfaces_atomic_outcome_store_failure(monkeypatch):
    import api

    monkeypatch.setattr(api, "_cancelled_lookup_ids", set())
    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)
    job = AgentJob(
        user_id="user_a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user_a:lookup-cancel-failure",
        payload={
            "user_id": "user_a",
            "company_name": "Acme",
            "lookup_id": "lookup-cancel-failure",
        },
    )
    repository.enqueued.append(job)

    async def fail_atomic_cancel(**_kwargs):
        raise LookupOutcomeStoreUnavailable("atomic outcome write failed")

    repository.cancel = fail_atomic_cancel
    response = TestClient(api.app, raise_server_exceptions=False).post(
        "/api/startups/lookup/cancel",
        json={"lookup_id": "lookup-cancel-failure"},
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "lookup_outcome_store_unavailable"
    assert api._is_lookup_cancelled("user_a", "lookup-cancel-failure") is False


def test_primary_lookup_cancel_does_not_mark_running_job_that_won_success_race(
    monkeypatch,
):
    import api

    monkeypatch.setattr(api, "_cancelled_lookup_ids", set())
    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)
    job = AgentJob(
        user_id="user_a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user_a:lookup-cancel-race",
        payload={
            "user_id": "user_a",
            "company_name": "Acme",
            "lookup_id": "lookup-cancel-race",
        },
        status=JobStatus.RUNNING,
        attempts=1,
    )
    repository.enqueued.append(job)

    async def finish_before_cancel(**_kwargs):
        return JobCancellationResult(
            disposition=JobCancellationDisposition.REJECTED,
            job=job.model_copy(update={"status": JobStatus.SUCCEEDED}),
        )

    repository.cancel = finish_before_cancel
    response = TestClient(api.app).post(
        "/api/startups/lookup/cancel",
        json={"lookup_id": "lookup-cancel-race"},
        headers={"Authorization": "Bearer t"},
    )

    assert response.status_code == 409
    assert response.json()["status"] == "conflict"
    assert response.json()["cancelled"] == []
    assert repository.atomic_outcomes == []
    assert api._is_lookup_cancelled("user_a", "lookup-cancel-race") is False


def test_system_status_reports_durable_job_and_outbox_counts(monkeypatch):
    import api

    repository = _Repository()
    _configure_durable(monkeypatch, api, repository)

    response = TestClient(api.app).get(
        "/api/system/status", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["durable_jobs"]["ready"] is True
    assert body["durable_jobs"]["counts"]["pipeline_cycle:queued"] == 2
    assert body["durable_jobs"]["counts"]["company_lookup:retry_wait"] == 3
    assert body["durable_jobs"]["counts"]["company_lookup:dead_letter"] == 1
    assert body["durable_jobs"]["counts"]["outbox:pending"] == 4


def test_system_status_is_degraded_when_durable_counts_cannot_be_read(monkeypatch):
    import api

    _configure_durable(monkeypatch, api, _FailingStatusRepository())

    response = TestClient(api.app).get(
        "/api/system/status", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["durable_jobs"]["error"] == "durable_status_read_failed"
    assert body["durable_jobs"]["runtime_ready"] is True
    assert body["durable_jobs"]["runtime"] == {
        "worker": "running",
        "outbox_publisher": "running",
    }


def test_system_status_is_degraded_when_durable_worker_task_stops(monkeypatch):
    import api

    _configure_durable(monkeypatch, api, _Repository())
    monkeypatch.setattr(
        api,
        "_durable_job_worker",
        _DurableWorker(_BackgroundTask(done=True, error=RuntimeError("connection lost"))),
        raising=False,
    )

    response = TestClient(api.app).get(
        "/api/system/status", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["durable_jobs"]["ready"] is True
    assert body["durable_jobs"]["runtime_ready"] is False
    assert body["durable_jobs"]["error"] == "durable_background_task_stopped"
    assert body["durable_jobs"]["runtime"] == {
        "worker": "failed",
        "outbox_publisher": "running",
    }
