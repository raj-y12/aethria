from datetime import timedelta

import pytest

from jobs.models import AgentJob, CompanyLookupPayload, JobStatus, JobType
from pipeline_execution import PipelineExecutionResult
from utils.timeutil import utcnow


def _job(*, attempt: int = 1, max_attempts: int = 3) -> AgentJob:
    return AgentJob(
        job_id="job-lookup-1",
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:lookup-acme-1",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-acme-1",
        ),
        status=JobStatus.RUNNING,
        attempts=attempt,
        max_attempts=max_attempts,
        pipeline_run_id="pipeline-run-1",
    )


def test_attempt_identity_binds_tenant_lookup_job_pipeline_and_attempt():
    from jobs.lookup_outcomes import LookupAttemptOutcome

    first = LookupAttemptOutcome.accepted_for_job(_job(attempt=1))
    retry = LookupAttemptOutcome.accepted_for_job(_job(attempt=2))
    other_pipeline = LookupAttemptOutcome.accepted_for_job(
        _job(attempt=1).model_copy(update={"pipeline_run_id": "pipeline-run-2"})
    )

    assert first.id != retry.id
    assert first.id != other_pipeline.id
    assert first.model_dump(mode="json") == {
        "id": first.id,
        "user_id": "user-a",
        "lookup_id": "lookup-acme-1",
        "job_id": "job-lookup-1",
        "pipeline_run_id": "pipeline-run-1",
        "attempt": 1,
        "status": "accepted",
        "disposition": "accepted",
        "code": "lookup_attempt_accepted",
        "detail": "Lookup attempt accepted for execution.",
        "recovery_action": None,
        "failed_stage": None,
        "startup_id": None,
        "recorded_at": first.recorded_at.isoformat(),
    }


@pytest.mark.parametrize(
    ("attempt", "max_attempts", "expected_disposition"),
    [(1, 3, "retryable_failure"), (3, 3, "terminal_failure")],
)
def test_failed_stage_records_retryability_without_losing_pipeline_metadata(
    attempt, max_attempts, expected_disposition
):
    from jobs.lookup_outcomes import LookupAttemptOutcome

    result = PipelineExecutionResult.stage_failure(
        stage="reviewer",
        code="reviewer_stage_failed",
        detail="Reviewer could not complete.",
        recovery_action="Inspect Reviewer logs and retry.",
        startup_id="startup-1",
    )

    outcome = LookupAttemptOutcome.from_pipeline_result(
        _job(attempt=attempt, max_attempts=max_attempts), result
    )

    assert outcome.status.value == "failed_stage"
    assert outcome.disposition.value == expected_disposition
    assert outcome.failed_stage == "reviewer"
    assert outcome.startup_id == "startup-1"


@pytest.mark.asyncio
async def test_lookup_outcome_storage_is_owned_by_the_async_durable_repository():
    from jobs.repository import DurableJobRepository

    class Connection:
        def __init__(self):
            self.data = []

        async def execute(self, *_args):
            self.data.append(_args)

        async def fetch(self, *_args):
            import json

            return [{"data": json.loads(value[3])} for value in self.data]

    class Acquire:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, *_args):
            return None

    connection = Connection()
    class Pool:
        def acquire(self):
            return Acquire(connection)

    repository = DurableJobRepository(Pool())
    from jobs.lookup_outcomes import LookupAttemptOutcome

    outcome = LookupAttemptOutcome.accepted_for_job(_job())
    await repository.record_lookup_outcome(outcome)
    assert await repository.latest_lookup_attempt(
        user_id="user-a", lookup_id="lookup-acme-1"
    ) == outcome


@pytest.mark.asyncio
async def test_durable_lookup_write_failure_is_explicit():
    from jobs.lookup_outcomes import LookupAttemptOutcome, LookupOutcomeStoreUnavailable
    from jobs.repository import DurableJobRepository

    class Connection:
        async def execute(self, *_args):
            raise ConnectionError("down")

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

    with pytest.raises(LookupOutcomeStoreUnavailable, match="write"):
        await DurableJobRepository(Pool()).record_lookup_outcome(
            LookupAttemptOutcome.accepted_for_job(_job())
        )


@pytest.mark.asyncio
async def test_durable_lookup_read_failure_is_explicit():
    from jobs.lookup_outcomes import LookupOutcomeStoreUnavailable
    from jobs.repository import DurableJobRepository

    class Connection:
        async def fetch(self, *_args):
            raise ConnectionError("down")

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

    with pytest.raises(LookupOutcomeStoreUnavailable, match="read"):
        await DurableJobRepository(Pool()).latest_lookup_attempt(
            user_id="user-a", lookup_id="lookup-acme-1"
        )


@pytest.mark.asyncio
async def test_durable_lookup_read_rejects_cross_tenant_data():
    from jobs.lookup_outcomes import LookupAttemptOutcome, LookupOutcomeCorrupt
    from jobs.repository import DurableJobRepository

    mismatched = LookupAttemptOutcome.accepted_for_job(
        _job().model_copy(update={"user_id": "user-b"})
    )

    class Connection:
        async def fetch(self, *_args):
            return [{"data": mismatched.model_dump(mode="json")}]

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *_args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

    with pytest.raises(LookupOutcomeCorrupt, match="tenant"):
        await DurableJobRepository(Pool()).latest_lookup_attempt(
            user_id="user-a", lookup_id="lookup-acme-1"
        )
