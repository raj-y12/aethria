import importlib
import json
from collections import deque

import pytest

from jobs.lookup_outcomes import LookupAttemptOutcome
from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)


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


def _lookup_job(*, status=JobStatus.QUEUED, attempts=0, max_attempts=3):
    return AgentJob(
        job_id="74d53f3f-1795-4636-bda7-c55fbf420dc4",
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:lookup-contract-1",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-contract-1",
        ),
        status=status,
        attempts=attempts,
        max_attempts=max_attempts,
        pipeline_run_id="pipeline-contract-1",
        lease_owner="worker-a" if status is JobStatus.RUNNING else None,
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
async def test_enqueue_lookup_commits_initial_accepted_attempt_with_job():
    repository_module = importlib.import_module("jobs.repository")
    lookup = _lookup_job()
    connection = _Connection(fetchrows=[_row(lookup)])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    accepted = await repository.enqueue(lookup)

    assert accepted.job_id == lookup.job_id
    outcome_call = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    payload = json.loads(outcome_call[2][2])
    assert payload["attempt"] == 1
    assert payload["disposition"] == "accepted"


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
async def test_claim_lookup_persists_accepted_attempt_in_same_transaction():
    repository_module = importlib.import_module("jobs.repository")
    claimed_row = _row(
        _lookup_job(status=JobStatus.RUNNING, attempts=1),
        status="running",
        attempts=1,
        lease_owner="worker-a",
    )
    connection = _Connection(fetchrows=[claimed_row])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    claimed = await repository.claim_next(worker_id="worker-a", lease_seconds=60)

    assert claimed.attempts == 1
    outcome_call = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    payload = json.loads(outcome_call[2][2])
    assert payload["attempt"] == 1
    assert payload["disposition"] == "accepted"


@pytest.mark.asyncio
async def test_reclaimed_lookup_terminalizes_expired_attempt_before_new_acceptance():
    repository_module = importlib.import_module("jobs.repository")
    reclaimed = _row(
        _lookup_job(status=JobStatus.RUNNING, attempts=2),
        status="running",
        attempts=2,
        lease_owner="worker-b",
        previous_status="running",
        previous_attempts=1,
        previous_lease_owner="worker-a",
    )
    connection = _Connection(fetchrows=[reclaimed])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    claimed = await repository.claim_next(worker_id="worker-b", lease_seconds=60)

    assert claimed.attempts == 2
    payloads = [
        json.loads(call[2][2])
        for call in connection.calls
        if "lookup_job_outcomes" in call[1].lower()
    ]
    assert [(item["attempt"], item["disposition"]) for item in payloads] == [
        (1, "retryable_failure"),
        (2, "accepted"),
    ]
    assert payloads[0]["code"] == "lookup_attempt_lease_expired"


@pytest.mark.asyncio
async def test_exhausted_expired_lease_is_dead_lettered_instead_of_sticking_running():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetches=[
            [
                {
                    "job_id": _job().job_id,
                    "user_id": "user-a",
                    "job_type": "pipeline_cycle",
                }
            ]
        ]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    recovered = await repository.dead_letter_exhausted_leases()

    assert recovered == 1
    sql = connection.calls[0][1].lower()
    assert "status = 'running'" in sql
    assert "lease_expires_at <= now()" in sql
    assert "attempts >= max_attempts" in sql
    assert "status = 'dead_letter'" in sql
    assert any("domain_outbox" in call[1].lower() for call in connection.calls)


@pytest.mark.asyncio
async def test_exhausted_lookup_lease_dead_letters_its_attempt_atomically():
    repository_module = importlib.import_module("jobs.repository")
    exhausted = _row(
        _lookup_job(status=JobStatus.DEAD_LETTER, attempts=3, max_attempts=3),
        status="dead_letter",
        attempts=3,
        max_attempts=3,
        last_error="Worker lease expired after the final attempt",
    )
    connection = _Connection(fetches=[[exhausted]])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    assert await repository.dead_letter_exhausted_leases() == 1

    outcome_call = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    payload = json.loads(outcome_call[2][2])
    assert payload["attempt"] == 3
    assert payload["disposition"] == "terminal_failure"
    assert payload["code"] == "lookup_attempt_lease_expired"


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
@pytest.mark.parametrize(
    "operation",
    ["heartbeat", "succeed", "retry", "fail", "block", "cancel_owned"],
)
async def test_owned_job_mutations_reject_an_expired_lease(operation):
    repository_module = importlib.import_module("jobs.repository")
    running = _lookup_job(status=JobStatus.RUNNING, attempts=1)
    repository = repository_module.DurableJobRepository(
        _Pool(_Connection(fetchrows=[None]))
    )
    common = {
        "user_id": running.user_id,
        "job_id": running.job_id,
        "worker_id": "worker-a",
    }

    if operation == "heartbeat":
        await repository.heartbeat(**common, lease_seconds=60)
    elif operation == "succeed":
        await repository.succeed(**common)
    elif operation == "retry":
        await repository.retry(**common, error="retry")
    elif operation == "fail":
        await repository.fail(**common, error="failed")
    elif operation == "block":
        await repository.block(
            **common,
            code="identity_review_required",
            detail="Identity review is required.",
            recovery_action="Resolve the identity case.",
        )
    else:
        await repository.cancel_owned(
            **common,
            lookup_outcome=LookupAttemptOutcome.cancelled_for_job(
                running,
                detail="The lookup was cancelled.",
            ),
        )

    sql = repository.pool.connection.calls[0][1].lower()
    assert "lease_expires_at > now()" in sql


@pytest.mark.asyncio
async def test_stale_lookup_finalizer_cannot_publish_terminal_outcome():
    repository_module = importlib.import_module("jobs.repository")
    job = _lookup_job(status=JobStatus.RUNNING, attempts=1)
    outcome = LookupAttemptOutcome.cancelled_for_job(
        job, detail="A competing owner cancelled this attempt."
    )
    connection = _Connection(fetchrows=[None])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    transitioned = await repository.succeed(
        user_id=job.user_id,
        job_id=job.job_id,
        worker_id="stale-worker",
        lookup_outcome=outcome,
    )

    assert transitioned is False
    assert not any("lookup_job_outcomes" in call[1].lower() for call in connection.calls)


@pytest.mark.asyncio
async def test_owned_lookup_cancellation_and_outcome_finalize_atomically():
    repository_module = importlib.import_module("jobs.repository")
    running = _lookup_job(status=JobStatus.RUNNING, attempts=1)
    cancelled = _row(
        running.model_copy(update={"status": JobStatus.CANCELLED}),
        status="cancelled",
        attempts=1,
        lease_owner=None,
    )
    outcome = LookupAttemptOutcome.cancelled_for_job(
        running, detail="Lookup was cancelled at a safe boundary."
    )
    connection = _Connection(fetchrows=[cancelled])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel_owned(
        user_id=running.user_id,
        job_id=running.job_id,
        worker_id="worker-a",
        lookup_outcome=outcome,
    )

    assert result.status is JobStatus.CANCELLED
    mutation_sql = connection.calls[0][1].lower()
    assert "lease_owner = $3" in mutation_sql
    assert "status = 'running'" in mutation_sql
    persisted = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    assert json.loads(persisted[2][2])["disposition"] == "cancelled"


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

    assert result.disposition.value == "transitioned"
    assert result.job is not None
    assert result.job.status is JobStatus.CANCELLED
    sql = connection.calls[0][1].lower()
    assert "user_id = $2" in sql
    assert "status not in ('succeeded', 'cancelled')" in sql
    assert "coalesce(jobs.completed_at, now())" in sql


@pytest.mark.asyncio
async def test_cancel_queued_lookup_uses_pre_transition_planned_attempt_atomically():
    repository_module = importlib.import_module("jobs.repository")
    cancelled = _row(
        _lookup_job(status=JobStatus.CANCELLED, attempts=2),
        status="cancelled",
        attempts=2,
        previous_status="queued",
        previous_attempts=2,
    )
    connection = _Connection(fetchrows=[cancelled])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel(
        user_id="user-a", job_id=_lookup_job().job_id
    )

    assert result.disposition.value == "transitioned"
    assert result.job is not None
    assert result.job.status is JobStatus.CANCELLED
    outcome_call = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    payload = json.loads(outcome_call[2][2])
    assert payload["attempt"] == 3
    assert payload["disposition"] == "cancelled"


@pytest.mark.asyncio
async def test_repeated_cancel_does_not_publish_a_second_outbox_event():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetchrows=[None, _row(status="cancelled")])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel(user_id="user-a", job_id=_job().job_id)

    assert result.disposition.value == "already_cancelled"
    assert result.job is not None
    assert result.job.status is JobStatus.CANCELLED
    assert not any(
        call[0] == "execute" and "domain_outbox" in call[1].lower()
        for call in connection.calls
    )


@pytest.mark.asyncio
async def test_cancel_reports_when_running_to_succeeded_race_loses_transition():
    repository_module = importlib.import_module("jobs.repository")
    succeeded = _row(
        _lookup_job(status=JobStatus.SUCCEEDED, attempts=1),
        status="succeeded",
        attempts=1,
    )
    connection = _Connection(fetchrows=[None, succeeded])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.cancel(
        user_id="user-a",
        job_id=_lookup_job().job_id,
    )

    assert result.disposition.value == "rejected"
    assert result.job is not None
    assert result.job.status is JobStatus.SUCCEEDED
    assert not any(
        call[0] == "execute"
        and (
            "lookup_job_outcomes" in call[1].lower()
            or "domain_outbox" in call[1].lower()
        )
        for call in connection.calls
    )


@pytest.mark.asyncio
async def test_manual_requeue_adds_one_attempt_without_changing_job_identity():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetchrows=[
            _row(
                status="queued",
                attempts=3,
                max_attempts=4,
                last_error=None,
                completed_at=None,
            )
        ]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.requeue(user_id="user-a", job_id=_job().job_id)

    assert result.job_id == _job().job_id
    assert result.status is JobStatus.QUEUED
    assert result.max_attempts == 4
    sql = connection.calls[0][1].lower()
    assert "status in ('failed', 'dead_letter', 'blocked', 'retry_wait')" in sql
    assert "max_attempts = greatest(max_attempts, attempts + 1)" in sql


@pytest.mark.asyncio
async def test_lookup_requeue_and_new_accepted_attempt_share_one_transaction():
    repository_module = importlib.import_module("jobs.repository")
    queued = _row(
        _lookup_job(status=JobStatus.QUEUED, attempts=3, max_attempts=4),
        status="queued",
        attempts=3,
        max_attempts=4,
    )
    connection = _Connection(fetchrows=[queued])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.requeue(
        user_id="user-a", job_id=_lookup_job().job_id
    )

    assert result.status is JobStatus.QUEUED
    outcome_call = next(
        call for call in connection.calls if "lookup_job_outcomes" in call[1].lower()
    )
    payload = json.loads(outcome_call[2][2])
    assert payload["attempt"] == 4
    assert payload["disposition"] == "accepted"


@pytest.mark.asyncio
async def test_lookup_outcome_write_failure_aborts_requeue_transaction():
    repository_module = importlib.import_module("jobs.repository")

    class FailingConnection(_Connection):
        async def execute(self, sql, *args):
            self.calls.append(("execute", sql, args))
            if "lookup_job_outcomes" in sql.lower():
                raise ConnectionError("lookup outcome insert failed")
            return "OK"

    queued = _row(
        _lookup_job(status=JobStatus.QUEUED, attempts=3, max_attempts=4),
        status="queued",
        attempts=3,
        max_attempts=4,
    )
    connection = FailingConnection(fetchrows=[queued])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    with pytest.raises(Exception, match="lookup outcome"):
        await repository.requeue(user_id="user-a", job_id=_lookup_job().job_id)


@pytest.mark.asyncio
async def test_block_is_structured_tenant_scoped_and_preserves_monotonic_attempt():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetchrows=[
            _row(
                status="blocked",
                attempts=1,
                block_code="identity_review_required",
                block_detail="Ambiguous company identity.",
                recovery_action="Resolve identity case and retry.",
            )
        ]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    result = await repository.block(
        user_id="user-a",
        job_id=_job().job_id,
        worker_id="worker-a",
        code="identity_review_required",
        detail="Ambiguous company identity.",
        recovery_action="Resolve identity case and retry.",
    )

    assert result.status is JobStatus.BLOCKED
    assert result.block_code == "identity_review_required"
    sql = connection.calls[0][1].lower()
    assert "attempts = greatest(attempts - 1, 0)" not in sql
    assert "user_id = $2" in sql
    assert any("agent_job.blocked" in str(call) for call in connection.calls)


@pytest.mark.asyncio
async def test_tenant_queue_depths_scope_jobs_and_outbox_to_the_authenticated_user():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetches=[[{"job_type": "pipeline_cycle", "status": "queued", "count": 2}]]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    counts = await repository.tenant_queue_depths(user_id="user-a")

    assert counts == {"pipeline_cycle:queued": 2}
    sql = connection.calls[0][1].lower()
    assert sql.count("user_id = $1") == 2
    assert connection.calls[0][2] == ("user-a",)


@pytest.mark.asyncio
async def test_global_queue_depths_are_explicitly_named_for_operator_metrics():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(fetches=[[]])
    repository = repository_module.DurableJobRepository(_Pool(connection))

    await repository.global_queue_depths()

    assert connection.calls[0][2] == ()


@pytest.mark.asyncio
async def test_governed_policy_projection_reads_only_the_tenant_active_version():
    repository_module = importlib.import_module("jobs.repository")
    connection = _Connection(
        fetchrows=[
            {
                "governed_policy_version_id": "version-2",
                "policy_hash": "hash-2",
                "policy_patch": json.dumps({"scoringWeights": []}),
            }
        ]
    )
    repository = repository_module.DurableJobRepository(_Pool(connection))

    projection = await repository.get_current_governed_policy_projection(
        user_id="user-a"
    )

    assert projection == {
        "governed_policy_version_id": "version-2",
        "published_policy_id": "version-2",
        "policy_hash": "hash-2",
        "fund_config": {"scoringWeights": []},
    }
    sql = connection.calls[0][1].lower()
    assert "where user_id=$1 and status='published'" in sql


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

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://supabase-host/db")
    seen.clear()
    assert await postgres.create_pool(create_pool_fn=create) == "pool"
    assert seen[0]["dsn"] == "postgresql://supabase-host/db"
