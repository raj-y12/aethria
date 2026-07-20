import importlib

import pytest

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    EvaluationPrerequisites,
)
from evaluation_v2.policy import evaluation_policy_from_compiled
from jobs.models import (
    AgentJob,
    CompanyLookupPayload,
    EvidenceRefreshPayload,
    JobExecutionBlocked,
    JobExecutionCancelled,
    JobStatus,
    JobType,
    PipelineCyclePayload,
)


def _prerequisites():
    policy = evaluation_policy_from_compiled(
        {
            "policy_version_id": "policy-live",
            "policy_hash": "hash-live",
            "dimensions": {
                "market": {"weight": 100, "criteria": [{"id": "market"}]}
            },
        },
        partner_rules={
            "version": "rules-v2",
            "decision_safety": {
                "evidence_eligibility": {
                    "allowed_assertion_classes": ["externally_verified"],
                    "allowed_relationships": ["supports"],
                    "require_verified_evidence": True,
                    "min_support_strength": 0.5,
                    "min_source_quality": 0.4,
                    "blocked_trust_classes": ["model", "unknown"],
                },
                "critical_risk_claim_types": ["critical_risk"],
                "hard_exclusion_claim_types": ["mandate_exclusion"],
            },
        },
    )
    return EvaluationPrerequisites(thesis_version_id="thesis-live", policy=policy)


class _Repository:
    pool = object()

    def __init__(self):
        self.checkpoints = []

    async def write_checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
async def test_cycle_handler_passes_job_tenant_and_stable_pipeline_run(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    calls = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))

    async def load(**kwargs):
        assert kwargs["user_id"] == "user-a"
        return _prerequisites()

    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle-1",
        payload=PipelineCyclePayload(user_id="user-a", manual_one_shot=True),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.pipeline_cycle_handler(repository, job)

    assert calls[0][0] == "user-a"
    assert calls[0][1]["manual_one_shot"] is True
    assert calls[0][1]["pipeline_run_id"] == job.pipeline_run_id
    assert calls[0][1]["identity_repository"].pool is repository.pool
    assert calls[0][1]["evaluation_prerequisites"] == _prerequisites()
    assert [item["stage"] for item in repository.checkpoints] == [
        "pipeline_cycle",
        "pipeline_cycle",
    ]


@pytest.mark.asyncio
async def test_lookup_handler_writes_pipeline_checkpoints_and_reconstructs_resolution(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    calls = []

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **kwargs):
            return None

        async def link_legacy_projection(self, **kwargs):
            return object()

    class IdentityService:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            return type(
                "Admission",
                (),
                {
                    "observation_id": "observation-1",
                    "status": type("Status", (), {"value": "resolved"})(),
                    "company_id": "company-1",
                    "opportunity_id": "opportunity-1",
                    "identity_case_id": None,
                    "confidence": 1.0,
                    "blocks_evaluation": False,
                },
            )()

    async def run(user_id, company_name, **kwargs):
        calls.append((user_id, company_name, kwargs))
        await kwargs["checkpoint"]("scout", "succeeded", {"startup_id": "s1"})
        return "s1"

    async def load(**kwargs):
        assert kwargs["user_id"] == "user-a"
        return _prerequisites()

    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup-1",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-1",
            resolution={"query": "Acme", "canonical_name": "Acme", "resolution_status": "FOUND"},
        ),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.company_lookup_handler(repository, job)

    assert calls[0][0:2] == ("user-a", "Acme")
    assert calls[0][2]["pipeline_run_id"] == job.pipeline_run_id
    assert calls[0][2]["resolution"].canonical_name == "Acme"
    assert calls[0][2]["evaluation_prerequisites"] == _prerequisites()
    assert calls[0][2]["institutional_context"] == {
        "observation_id": "observation-1",
        "company_id": "company-1",
        "opportunity_id": "opportunity-1",
        "thesis_version_id": "thesis-live",
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
    }
    assert repository.checkpoints[0]["stage"] == "identity"
    assert repository.checkpoints[1]["stage"] == "scout"
    assert repository.checkpoints[-1]["stage"] == "lookup_result"


@pytest.mark.asyncio
async def test_lookup_handler_observes_cancellation_between_checkpoints(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:cancelled",
        payload=CompanyLookupPayload(user_id="user-a", company_name="Acme"),
        attempts=1,
        status=JobStatus.RUNNING,
    )

    async def get_job(**kwargs):
        return job.model_copy(update={"status": JobStatus.CANCELLED})

    repository.get_job = get_job

    with pytest.raises(JobExecutionCancelled):
        await handlers.company_lookup_handler(repository, job)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["thesis_required", "published_policy_required"])
async def test_lookup_handler_preserves_identity_then_blocks_before_legacy_lookup(
    monkeypatch, code
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    events = []

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **kwargs):
            return None

    class IdentityService:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            events.append("identity")
            return type(
                "Admission",
                (),
                {
                    "observation_id": "observation-1",
                    "status": type("Status", (), {"value": "resolved"})(),
                    "company_id": "company-1",
                    "opportunity_id": "opportunity-1",
                    "identity_case_id": None,
                    "confidence": 1.0,
                    "blocks_evaluation": False,
                },
            )()

    async def load(**kwargs):
        events.append("prerequisites")
        raise EvaluationPrerequisiteError(
            code=code,
            detail=f"{code} detail",
            recovery_action="Correct the fund configuration in Settings.",
        )

    async def run(*args, **kwargs):
        raise AssertionError("legacy lookup must not run without prerequisites")

    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key=f"lookup-{code}",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.example",
        ),
        attempts=1,
        status="running",
    )

    with pytest.raises(JobExecutionBlocked) as exc:
        await handlers.company_lookup_handler(repository, job)

    assert exc.value.code == code
    assert events == ["identity", "prerequisites"]
    assert repository.checkpoints[-1]["stage"] == "identity"


@pytest.mark.asyncio
async def test_cycle_handler_blocks_before_legacy_cycle_when_policy_is_missing(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()

    async def load(**kwargs):
        raise EvaluationPrerequisiteError(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish the fund scoring policy in Settings.",
        )

    async def run(*args, **kwargs):
        raise AssertionError("pipeline cycle must not run without prerequisites")

    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle-policy-missing",
        payload=PipelineCyclePayload(user_id="user-a", manual_one_shot=True),
        attempts=1,
        status="running",
    )

    with pytest.raises(JobExecutionBlocked) as exc:
        await handlers.pipeline_cycle_handler(repository, job)

    assert exc.value.code == "published_policy_required"
    assert [item["stage"] for item in repository.checkpoints] == ["pipeline_cycle"]


@pytest.mark.asyncio
async def test_evidence_refresh_stops_after_cheap_no_change_check(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    settled = []

    class MonitoringRepository:
        def __init__(self, pool):
            pass

        async def check_material_change(self, **kwargs):
            return {
                "material_change": False,
                "previous_snapshot_hash": "same",
                "current_snapshot_hash": "same",
            }

        async def settle(self, **kwargs):
            settled.append(kwargs)

    monkeypatch.setattr(handlers, "MonitoringRepository", MonitoringRepository)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.EVIDENCE_REFRESH,
        idempotency_key="refresh-1",
        payload=EvidenceRefreshPayload(
            user_id="user-a",
            opportunity_id="opportunity-1",
            reason="monitor_due",
            budget_reservation_id="reservation-1",
        ),
        attempts=1,
        status="running",
    )

    await handlers.evidence_refresh_handler(repository, job)

    assert settled[0]["actual_cost_usd"] == 0
    assert [item["stage"] for item in repository.checkpoints] == [
        "material_change",
        "material_change",
        "refresh_result",
    ]
