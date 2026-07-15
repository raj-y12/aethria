import importlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


def _jobs():
    return importlib.import_module("jobs.models")


def test_pipeline_cycle_job_round_trips_with_explicit_tenant():
    jobs = _jobs()
    payload = jobs.PipelineCyclePayload(
        user_id="user-a", manual_one_shot=True, source="api_trigger"
    )
    job = jobs.AgentJob(
        user_id="user-a",
        job_type=jobs.JobType.PIPELINE_CYCLE,
        idempotency_key="cycle:user-a:manual:1",
        payload=payload,
    )

    assert job.status is jobs.JobStatus.QUEUED
    assert job.pipeline_run_id
    assert jobs.AgentJob.model_validate(job.model_dump()) == job


def test_company_lookup_payload_preserves_current_inputs_and_resolution():
    jobs = _jobs()
    payload = jobs.CompanyLookupPayload(
        user_id="user-a",
        company_name="Acme",
        website="acme.example",
        lookup_id="lookup-acme-1",
        additional_context="Met at event",
        resolution={"canonical_name": "Acme", "resolution_status": "FOUND"},
    )

    assert payload.model_dump(mode="json")["resolution"] == {
        "canonical_name": "Acme",
        "resolution_status": "FOUND",
    }


@pytest.mark.parametrize("model_name", ["PipelineCyclePayload", "CompanyLookupPayload"])
def test_job_payloads_reject_blank_tenant(model_name):
    jobs = _jobs()
    model = getattr(jobs, model_name)
    kwargs = {"user_id": "   "}
    if model_name == "CompanyLookupPayload":
        kwargs["company_name"] = "Acme"

    with pytest.raises((ValidationError, ValueError)):
        model(**kwargs)


def test_agent_job_rejects_payload_tenant_mismatch():
    jobs = _jobs()

    with pytest.raises(ValidationError, match="payload tenant"):
        jobs.AgentJob(
            user_id="user-a",
            job_type=jobs.JobType.PIPELINE_CYCLE,
            idempotency_key="cycle-1",
            payload=jobs.PipelineCyclePayload(user_id="user-b"),
        )


def test_agent_job_rejects_payload_type_mismatch():
    jobs = _jobs()

    with pytest.raises(ValidationError, match="payload type"):
        jobs.AgentJob(
            user_id="user-a",
            job_type=jobs.JobType.COMPANY_LOOKUP,
            idempotency_key="lookup-1",
            payload=jobs.PipelineCyclePayload(user_id="user-a"),
        )


def test_checkpoint_and_outbox_contracts_are_tenant_scoped_and_json_safe():
    jobs = _jobs()
    checkpoint = jobs.JobCheckpoint(
        job_id="26b2fbaf-9cc3-4b48-bcca-e42a563e670b",
        user_id="user-a",
        pipeline_run_id="009e3bad-5f27-4341-a5f0-bae619aaef08",
        stage="reviewer",
        attempt=1,
        status=jobs.CheckpointStatus.SUCCEEDED,
        output_metadata={"startup_id": "startup-1"},
    )
    event = jobs.DomainOutboxEvent(
        event_id="d5d70e3a-c0a7-47c7-9a6e-f983d560c910",
        user_id="user-a",
        aggregate_type="agent_job",
        aggregate_id=checkpoint.job_id,
        event_type="agent_job.checkpointed",
        event_version=1,
        payload={"stage": checkpoint.stage},
    )

    assert checkpoint.model_dump(mode="json")["status"] == "succeeded"
    assert event.model_dump(mode="json")["event_version"] == 1


def test_lease_fields_validate_attempt_and_expiry_shape():
    jobs = _jobs()
    now = datetime.now(timezone.utc)
    payload = jobs.PipelineCyclePayload(user_id="user-a")

    with pytest.raises(ValidationError):
        jobs.AgentJob(
            user_id="user-a",
            job_type="pipeline_cycle",
            idempotency_key="cycle-1",
            payload=payload,
            attempts=4,
            max_attempts=3,
            lease_owner="worker-a",
            lease_expires_at=now,
        )


def test_blocked_execution_has_machine_code_and_operator_recovery_action():
    jobs = _jobs()
    error = jobs.JobExecutionBlocked(
        code="identity_review_required",
        detail="Two verified company identities matched.",
        recovery_action="Resolve the identity case, then retry the job.",
    )

    assert error.code == "identity_review_required"
    assert "Resolve" in error.recovery_action
    assert "identity_review_required" in str(error)


def test_agent_job_round_trips_structured_block_fields():
    jobs = _jobs()
    job = jobs.AgentJob(
        user_id="user-a",
        job_type=jobs.JobType.PIPELINE_CYCLE,
        idempotency_key="cycle:block",
        payload=jobs.PipelineCyclePayload(user_id="user-a"),
        status=jobs.JobStatus.BLOCKED,
        block_code="identity_review_required",
        block_detail="Operator decision required.",
        recovery_action="Resolve case and retry.",
    )

    assert jobs.AgentJob.model_validate(job.model_dump()) == job


def test_evidence_refresh_job_uses_typed_tenant_payload():
    jobs = _jobs()
    payload = jobs.EvidenceRefreshPayload(
        user_id="user-a",
        opportunity_id="opportunity-1",
        reason="human_request",
        budget_reservation_id="reservation-1",
    )
    job = jobs.AgentJob(
        user_id="user-a",
        job_type=jobs.JobType.EVIDENCE_REFRESH,
        idempotency_key="refresh:opportunity-1:1",
        payload=payload,
    )

    restored = jobs.AgentJob.model_validate(job.model_dump(mode="json"))
    assert isinstance(restored.payload, jobs.EvidenceRefreshPayload)
