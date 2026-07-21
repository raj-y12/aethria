import importlib
import json
from pathlib import Path

import pytest

from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites
from identity.models import IdentityAdmission, IdentityStatus, OpportunityRecord
from jobs.models import AgentJob, CompanyLookupPayload, JobExecutionBlocked, JobType
from utils.timeutil import utcnow
from pipeline_execution import PipelineExecutionResult


def _prerequisites():
    compiled = {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {
            "market": {"weight": 100, "criteria": [{"id": "market"}]}
        },
    }
    partner_rules = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "resources/config/partner_rules/v3.json"
        ).read_text()
    )
    partner_rules["version"] = "rules-v3"
    policy = evaluation_policy_from_compiled(
        compiled,
        partner_rules=partner_rules,
    )
    return EvaluationPrerequisites(
        user_id="user-a",
        thesis_context={"version_id": "thesis-live"},
        thesis_version_id="thesis-live",
        compiled_scoring_policy=compiled,
        partner_rules=partner_rules,
        fund_config={},
        policy=policy,
    )


@pytest.fixture(autouse=True)
def _admit_evaluation_prerequisites(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")

    async def load(**kwargs):
        assert kwargs["user_id"] == "user-a"
        return _prerequisites()

    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)

    async def persist(outcome):
        return outcome

    monkeypatch.setattr(handlers, "_persist_lookup_attempt", persist)


class _JobRepository:
    pool = object()

    def __init__(self):
        self.checkpoints = []

    async def write_checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)


class _IdentityRepository:
    def __init__(self):
        self.linked = []
        self.existing_projection = None

    async def link_legacy_projection(self, **kwargs):
        self.linked.append(kwargs)
        now = utcnow()
        return OpportunityRecord(
            user_id=kwargs["user_id"],
            opportunity_id=kwargs["opportunity_id"],
            company_id="company-1",
            first_observation_id="observation-1",
            latest_observation_id="observation-1",
            legacy_startup_id=kwargs["legacy_startup_id"],
            created_at=now,
            updated_at=now,
        )

    async def get_opportunity_by_legacy_projection(self, **kwargs):
        return self.existing_projection


def _job(*, resolution=None, replace_startup_id=None):
    return AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:acme",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.com",
            lookup_id="lookup-acme",
            replace_startup_id=replace_startup_id,
            resolution=resolution,
        ),
        status="running",
        attempts=1,
        lease_owner="worker-a",
    )


@pytest.mark.asyncio
async def test_identity_is_admitted_before_legacy_scout_and_projection_is_linked(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    job_repository = _JobRepository()
    identity_repository = _IdentityRepository()
    order = []
    captured = {}

    class _Service:
        def __init__(self, repository):
            assert repository is identity_repository

        async def admit(self, observation):
            order.append("identity")
            captured["observation"] = observation
            return IdentityAdmission(
                user_id="user-a",
                observation_id="observation-1",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
                created=True,
            )

    async def run(*args, **kwargs):
        order.append("legacy")
        captured["lookup_kwargs"] = kwargs
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="11111111-1111-4111-8111-111111111111",
            projection_id="opportunity-1",
        )

    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: identity_repository)
    monkeypatch.setattr(handlers, "IdentityService", _Service)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)

    await handlers.company_lookup_handler(job_repository, _job())

    assert order == ["identity", "legacy"]
    observation = captured["observation"]
    assert observation.user_id == "user-a"
    assert observation.channel.value == "manual_lookup"
    assert observation.source_metadata["operator_confirmed_identity"] is True
    assert captured["lookup_kwargs"]["institutional_context"] == {
        "observation_id": "observation-1",
        "company_id": "company-1",
        "opportunity_id": "opportunity-1",
        "thesis_version_id": "thesis-live",
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
    }
    assert captured["lookup_kwargs"]["evaluation_prerequisites"] == _prerequisites()
    assert identity_repository.linked[0]["opportunity_id"] == "opportunity-1"
    assert [item["stage"] for item in job_repository.checkpoints][-2:] == [
        "projection",
        "lookup_result",
    ]


@pytest.mark.asyncio
async def test_ambiguous_identity_blocks_before_scout(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    job_repository = _JobRepository()
    identity_repository = _IdentityRepository()
    scout_called = False

    class _Service:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            return IdentityAdmission(
                user_id="user-a",
                observation_id="observation-1",
                status=IdentityStatus.AMBIGUOUS,
                identity_case_id="case-1",
                confidence=0.8,
                blocks_evaluation=True,
            )

    async def run(*args, **kwargs):
        nonlocal scout_called
        scout_called = True

    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: identity_repository)
    monkeypatch.setattr(handlers, "IdentityService", _Service)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)

    with pytest.raises(JobExecutionBlocked) as blocked:
        await handlers.company_lookup_handler(job_repository, _job())

    assert blocked.value.code == "identity_review_required"
    assert scout_called is False
    identity_checkpoint = job_repository.checkpoints[-1]
    assert identity_checkpoint["output_metadata"] == {
        "observation_id": "observation-1",
        "identity_case_id": "case-1",
        "status": "ambiguous",
        "confidence": 0.8,
    }


@pytest.mark.asyncio
async def test_legacy_failure_leaves_authoritative_identity_for_recovery(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    job_repository = _JobRepository()
    identity_repository = _IdentityRepository()

    class _Service:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            return IdentityAdmission(
                user_id="user-a",
                observation_id="observation-1",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
            )

    async def run(*args, **kwargs):
        raise RuntimeError("legacy storage unavailable")

    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: identity_repository)
    monkeypatch.setattr(handlers, "IdentityService", _Service)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)

    with pytest.raises(RuntimeError, match="legacy storage unavailable"):
        await handlers.company_lookup_handler(job_repository, _job())

    assert any(item["stage"] == "identity" for item in job_repository.checkpoints)
    assert identity_repository.linked == []


@pytest.mark.asyncio
async def test_rerun_reuses_opportunity_already_linked_to_legacy_startup(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    job_repository = _JobRepository()
    identity_repository = _IdentityRepository()
    now = utcnow()
    identity_repository.existing_projection = OpportunityRecord(
        user_id="user-a",
        opportunity_id="opportunity-1",
        company_id="company-1",
        first_observation_id="observation-1",
        latest_observation_id="observation-1",
        legacy_startup_id="11111111-1111-4111-8111-111111111111",
        created_at=now,
        updated_at=now,
    )
    admitted = False

    class _Service:
        def __init__(self, repository):
            pass

        async def admit(self, observation):
            nonlocal admitted
            admitted = True

    async def run(*args, **kwargs):
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="11111111-1111-4111-8111-111111111111",
            projection_id="opportunity-1",
        )

    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: identity_repository)
    monkeypatch.setattr(handlers, "IdentityService", _Service)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)

    await handlers.company_lookup_handler(
        job_repository,
        _job(replace_startup_id="11111111-1111-4111-8111-111111111111"),
    )

    assert admitted is False
    assert identity_repository.linked[0]["opportunity_id"] == "opportunity-1"
