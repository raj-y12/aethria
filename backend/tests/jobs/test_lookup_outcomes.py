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


def test_latest_attempt_uses_attempt_before_timestamp_and_never_old_terminal_state(
    monkeypatch,
):
    import jobs.lookup_outcomes as outcomes

    now = utcnow()
    old_terminal = outcomes.LookupAttemptOutcome.from_pipeline_result(
        _job(attempt=1),
        PipelineExecutionResult.stage_failure(
            stage="scout",
            code="scout_lookup_failed",
            detail="Scout failed.",
            recovery_action="Retry.",
        ),
    ).model_copy(update={"recorded_at": now})
    new_accepted = outcomes.LookupAttemptOutcome.accepted_for_job(
        _job(attempt=2)
    ).model_copy(update={"recorded_at": now - timedelta(days=1)})
    monkeypatch.setattr(
        outcomes,
        "list_get_all_strict",
        lambda *_args, **_kwargs: [
            old_terminal.model_dump(mode="json"),
            new_accepted.model_dump(mode="json"),
        ],
    )
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")

    latest = outcomes.latest_lookup_attempt("user-a", "lookup-acme-1")

    assert latest == new_accepted


def test_store_write_unavailability_is_never_swallowed(monkeypatch):
    import jobs.lookup_outcomes as outcomes

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(
        outcomes,
        "list_upsert",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("down")),
    )

    with pytest.raises(outcomes.LookupOutcomeStoreUnavailable, match="write"):
        outcomes.record_lookup_attempt(
            outcomes.LookupAttemptOutcome.accepted_for_job(_job())
        )


def test_store_read_unavailability_is_never_coerced_to_missing(monkeypatch):
    import jobs.lookup_outcomes as outcomes

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(
        outcomes,
        "list_get_all_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("down")),
    )

    with pytest.raises(outcomes.LookupOutcomeStoreUnavailable, match="read"):
        outcomes.latest_lookup_attempt("user-a", "lookup-acme-1")


def test_latest_attempt_rejects_data_tenant_that_disagrees_with_storage_scope(
    monkeypatch,
):
    import jobs.lookup_outcomes as outcomes

    mismatched = outcomes.LookupAttemptOutcome.accepted_for_job(
        _job().model_copy(
            update={
                "user_id": "user-b",
                "payload": CompanyLookupPayload(
                    user_id="user-b",
                    company_name="Acme",
                    lookup_id="lookup-acme-1",
                ),
            }
        )
    )
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(
        outcomes,
        "list_get_all_strict",
        lambda *_args, **_kwargs: [mismatched.model_dump(mode="json")],
    )

    with pytest.raises(outcomes.LookupOutcomeCorrupt, match="tenant"):
        outcomes.latest_lookup_attempt("user-a", "lookup-acme-1")
