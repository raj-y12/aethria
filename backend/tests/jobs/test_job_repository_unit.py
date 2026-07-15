import importlib
import json
from collections import deque

import pytest

from jobs.models import AgentJob, JobStatus, JobType, PipelineCyclePayload


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, *, fetchrows=(), fetches=()):
        self.fetchrows = deque(fetchrows)
        self.fetches = deque(fetches)
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.popleft() if self.fetchrows else None

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self.fetches.popleft() if self.fetches else []

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "OK"


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


def _job():
    return AgentJob(
        job_id="64d53f3f-1795-4636-bda7-c55fbf420dc3",
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle:user-a:1",
        payload=PipelineCyclePayload(user_id="user-a", manual_one_shot=True),
        pipeline_run_id="4fb44a3f-dfde-4b52-b53e-47a9493ac93d",
    )


def _row(job=None, **overrides):
    data = (job or _job()).model_dump(mode="json")
    data["payload"] = json.dumps(data["payload"])
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_enqueue_commits_job_outbox_and_notify_in_one_transaction():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[_row()])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    accepted = await repository.enqueue(_job())

    assert accepted.job_id == _job().job_id
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "insert into public.agent_jobs" in sql
    assert "insert into public.domain_outbox" in sql
    assert "pg_notify" in sql


@pytest.mark.asyncio
async def test_enqueue_idempotency_returns_existing_job_without_duplicate_outbox():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[None, _row()])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    accepted = await repository.enqueue(_job())

    assert accepted.job_id == _job().job_id
    executed_sql = [call[1].lower() for call in connection.calls if call[0] == "execute"]
    assert not any("domain_outbox" in sql for sql in executed_sql)
    assert not any("pg_notify" in sql for sql in executed_sql)


@pytest.mark.asyncio
async def test_claim_uses_skip_locked_and_recovers_expired_leases():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetchrows=[
            _row(
                status="running",
                attempts=1,
                lease_owner="worker-a",
            )
        ]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    claimed = await repository.claim_next(worker_id="worker-a", lease_seconds=60)

    assert claimed.lease_owner == "worker-a"
    sql = connection.calls[0][1].lower()
    assert "for update skip locked" in sql
    assert "lease_expires_at <=" in sql
    assert "attempts = candidate.attempts + 1" in sql


@pytest.mark.asyncio
async def test_heartbeat_and_stale_completion_require_current_lease_owner():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[{"job_id": _job().job_id}, None])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    assert await repository.heartbeat(
        user_id="user-a", job_id=_job().job_id, worker_id="worker-a", lease_seconds=60
    ) is True
    assert await repository.succeed(
        user_id="user-a", job_id=_job().job_id, worker_id="stale-worker"
    ) is False
    success_sql = connection.calls[1][1].lower()
    assert "lease_owner = $3" in success_sql
    assert "status = 'running'" in success_sql


@pytest.mark.asyncio
async def test_checkpoint_upsert_is_idempotent_and_tenant_scoped():
    repository_module = importlib.import_module("jobs.repository")
    checkpoint_row = {
        "checkpoint_id": "bf35b114-5e4b-46e6-ab0e-c784239e6983",
        "job_id": _job().job_id,
        "user_id": "user-a",
        "pipeline_run_id": _job().pipeline_run_id,
        "stage": "reviewer",
        "attempt": 1,
        "status": "succeeded",
        "output_metadata": json.dumps({"startup_id": "startup-1"}),
        "error": None,
        "created_at": _job().created_at,
        "updated_at": _job().updated_at,
    }
    connection = _Connection(fetchrows=[checkpoint_row])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    checkpoint = await repository.write_checkpoint(
        user_id="user-a",
        job_id=_job().job_id,
        pipeline_run_id=_job().pipeline_run_id,
        stage="reviewer",
        attempt=1,
        status="succeeded",
        output_metadata={"startup_id": "startup-1"},
    )

    assert checkpoint.user_id == "user-a"
    sql = connection.calls[0][1].lower()
    assert "on conflict (user_id, job_id, stage, attempt, status)" in sql


@pytest.mark.asyncio
async def test_retry_is_bounded_and_dead_letters_after_max_attempts():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetchrows=[_row(status="dead_letter", attempts=3, last_error="provider failed")]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.retry(
        user_id="user-a",
        job_id=_job().job_id,
        worker_id="worker-a",
        error="provider failed",
    )

    assert result.status is JobStatus.DEAD_LETTER
    sql = connection.calls[0][1].lower()
    assert "case when attempts >= max_attempts" in sql
    assert "dead_letter" in sql


@pytest.mark.asyncio
async def test_cancel_is_tenant_scoped_and_idempotent():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[_row(status="cancelled")])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel(user_id="user-a", job_id=_job().job_id)

    assert result.status is JobStatus.CANCELLED
    sql = connection.calls[0][1].lower()
    assert "user_id = $2" in sql
    assert "status not in ('succeeded', 'cancelled')" in sql


@pytest.mark.asyncio
async def test_repeated_cancel_does_not_publish_a_second_outbox_event():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[None, _row(status="cancelled")])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel(user_id="user-a", job_id=_job().job_id)

    assert result.status is JobStatus.CANCELLED
    assert not any(
        call[0] == "execute" and "domain_outbox" in call[1].lower()
        for call in connection.calls
    )


@pytest.mark.asyncio
async def test_create_pool_requires_direct_dsn_and_uses_bounded_sizes(monkeypatch):
    postgres = importlib.import_module("jobs.postgres")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    with pytest.raises(postgres.DurableJobConfigurationError):
        await postgres.create_pool(create_pool_fn=lambda **kwargs: None)

    seen = []

    async def create(**kwargs):
        seen.append(kwargs)
        return "pool"

    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setenv("DURABLE_JOB_DB_POOL_MIN", "1")
    monkeypatch.setenv("DURABLE_JOB_DB_POOL_MAX", "4")
    assert await postgres.create_pool(create_pool_fn=create) == "pool"
    assert seen == [
        {
            "dsn": "postgresql://example/db",
            "min_size": 1,
            "max_size": 4,
            "command_timeout": 30.0,
        }
    ]
