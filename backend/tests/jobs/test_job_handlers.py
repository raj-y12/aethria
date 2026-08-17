import importlib
import json
from pathlib import Path
from types import SimpleNamespace

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
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState


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


class _Repository:
    pool = object()

    def __init__(self, latest_checkpoint=None):
        self.checkpoints = []
        self._latest_checkpoint = latest_checkpoint

    async def write_checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)

    async def get_latest_checkpoint(self, **kwargs):
        return self._latest_checkpoint


@pytest.fixture(autouse=True)
def _capture_lookup_attempt_outcomes(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    captured = []

    async def persist(outcome):
        captured.append(outcome)
        return outcome

    monkeypatch.setattr(handlers, "_persist_lookup_attempt", persist, raising=False)
    return captured


@pytest.mark.asyncio
async def test_cycle_handler_passes_job_tenant_and_stable_pipeline_run(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    calls = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))
        return PipelineExecutionResult.completed(
            code="pipeline_cycle_completed", detail="Cycle completed."
        )

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
    assert calls[0][1]["fund_intelligence_repository"].pool is repository.pool
    assert calls[0][1]["evaluation_prerequisites"] == _prerequisites()
    assert callable(calls[0][1]["ownership_check"])
    assert [item["stage"] for item in repository.checkpoints] == [
        "pipeline_cycle",
        "pipeline_cycle",
    ]


@pytest.mark.asyncio
async def test_lookup_handler_writes_pipeline_checkpoints_and_reconstructs_resolution(
    monkeypatch, _capture_lookup_attempt_outcomes
):
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
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="s1",
            projection_id="opportunity-1",
        )

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

    terminal_outcome = await handlers.company_lookup_handler(repository, job)

    assert calls[0][0:2] == ("user-a", "Acme")
    assert calls[0][2]["pipeline_run_id"] == job.pipeline_run_id
    assert calls[0][2]["resolution"].canonical_name == "Acme"
    assert calls[0][2]["evaluation_prerequisites"] == _prerequisites()
    assert calls[0][2]["fund_intelligence_repository"].pool is repository.pool
    assert callable(calls[0][2]["ownership_check"])
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
    assert repository.checkpoints[-1]["output_metadata"]["state"] == "completed"
    assert _capture_lookup_attempt_outcomes == []
    assert terminal_outcome.disposition.value == "succeeded"


@pytest.mark.asyncio
async def test_lookup_handler_resumes_from_prior_scout_checkpoint_on_retry(
    monkeypatch, _capture_lookup_attempt_outcomes
):
    """A retry after a mid-pipeline failure (e.g. Reviewer) must resume from the
    startup Scout already created, not re-scout and create an orphan duplicate
    that collides with the opportunity already linked to the first one."""
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository(
        latest_checkpoint=SimpleNamespace(output_metadata={"startup_id": "prior-startup-1"})
    )
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
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="prior-startup-1",
            projection_id="opportunity-1",
        )

    async def load(**kwargs):
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
        ),
        attempts=2,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.company_lookup_handler(repository, job)

    assert calls[0][2]["replace_startup_id"] == "prior-startup-1"


@pytest.mark.asyncio
async def test_lookup_handler_does_not_resume_on_first_attempt(
    monkeypatch, _capture_lookup_attempt_outcomes
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository(
        latest_checkpoint=SimpleNamespace(output_metadata={"startup_id": "should-not-be-used"})
    )
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
        return PipelineExecutionResult.completed(
            code="lookup_completed", detail="Lookup completed.",
            startup_id="s1", projection_id="opportunity-1",
        )

    async def load(**kwargs):
        return _prerequisites()

    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup-1",
        payload=CompanyLookupPayload(user_id="user-a", company_name="Acme", lookup_id="lookup-1"),
        attempts=1,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.company_lookup_handler(repository, job)

    assert calls[0][2]["replace_startup_id"] is None


@pytest.mark.asyncio
async def test_lookup_handler_never_overrides_an_explicit_replace_startup_id(
    monkeypatch, _capture_lookup_attempt_outcomes
):
    """An operator-initiated re-review must not be clobbered by the automatic
    retry-resume logic even if it happens to run on attempts > 1."""
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository(
        latest_checkpoint=SimpleNamespace(output_metadata={"startup_id": "wrong-startup"})
    )
    calls = []

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **kwargs):
            return type(
                "Opportunity",
                (),
                {"opportunity_id": "opportunity-1", "company_id": "company-1", "latest_observation_id": "observation-1"},
            )()

        async def link_legacy_projection(self, **kwargs):
            return object()

    async def run(user_id, company_name, **kwargs):
        calls.append((user_id, company_name, kwargs))
        return PipelineExecutionResult.completed(
            code="lookup_completed", detail="Lookup completed.",
            startup_id="explicit-startup", projection_id="opportunity-1",
        )

    async def load(**kwargs):
        return _prerequisites()

    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "IdentityRepository", lambda pool: IdentityRepository())
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup-1",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-1",
            replace_startup_id="explicit-startup",
            additional_context="Operator-supplied context.",
        ),
        attempts=2,
        status="running",
        lease_owner="worker-a",
    )

    await handlers.company_lookup_handler(repository, job)

    assert calls[0][2]["replace_startup_id"] == "explicit-startup"


@pytest.mark.asyncio
async def test_lookup_handler_returns_block_outcome_to_atomic_worker_transition(
    monkeypatch, _capture_lookup_attempt_outcomes
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:blocked-outcome",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.example",
        ),
        attempts=1,
        status=JobStatus.RUNNING,
        lease_owner="worker-a",
    )

    async def execute(_repository, _job):
        raise JobExecutionBlocked(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish policy and retry.",
        )

    monkeypatch.setattr(handlers, "_execute_company_lookup", execute)

    with pytest.raises(JobExecutionBlocked) as exc:
        await handlers.company_lookup_handler(repository, job)

    assert _capture_lookup_attempt_outcomes == []
    assert exc.value.lookup_outcome.disposition.value == "blocked"
    assert exc.value.lookup_outcome.attempt == 1


@pytest.mark.asyncio
async def test_lookup_handler_links_produced_projection_but_never_succeeds_failed_stage(
    monkeypatch,
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    links = []

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **_kwargs):
            return None

        async def link_legacy_projection(self, **kwargs):
            links.append(kwargs)
            return object()

    class IdentityService:
        def __init__(self, _repository):
            pass

        async def admit(self, _observation):
            return SimpleNamespace(
                observation_id="observation-1",
                status=SimpleNamespace(value="resolved"),
                company_id="company-1",
                opportunity_id="opportunity-1",
                identity_case_id=None,
                confidence=1.0,
                blocks_evaluation=False,
            )

    async def load(**_kwargs):
        return _prerequisites()

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.stage_failure(
            stage="reviewer",
            code="reviewer_stage_failed",
            detail="Reviewer could not complete.",
            recovery_action="Inspect Reviewer logs and retry.",
            startup_id="startup-1",
        )

    monkeypatch.setattr(handlers, "IdentityRepository", lambda _pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_on_demand_lookup", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup-reviewer-failed",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.example",
        ),
        attempts=1,
        status="running",
    )

    with pytest.raises(RuntimeError, match="reviewer_stage_failed"):
        await handlers.company_lookup_handler(repository, job)

    assert links == [
        {
            "user_id": "user-a",
            "opportunity_id": "opportunity-1",
            "legacy_startup_id": "startup-1",
        }
    ]
    assert repository.checkpoints[-1]["stage"] == "lookup_result"
    assert repository.checkpoints[-1]["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected_exception"),
    [
        (
            PipelineExecutionResult.blocked(
                code="openai_api_key_required",
                detail="OpenAI is not configured.",
                recovery_action="Configure OPENAI_API_KEY and retry.",
            ),
            JobExecutionBlocked,
        ),
        (
            PipelineExecutionResult.stage_failure(
                stage="reviewer",
                code="reviewer_stage_failed",
                detail="Reviewer did not complete.",
                recovery_action="Inspect Reviewer logs and retry.",
            ),
            RuntimeError,
        ),
    ],
)
async def test_cycle_handler_never_marks_blocked_or_failed_runner_result_succeeded(
    monkeypatch, result, expected_exception
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()

    async def load(**_kwargs):
        return _prerequisites()

    async def run(*_args, **_kwargs):
        return result

    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key=f"cycle-{result.code}",
        payload=PipelineCyclePayload(user_id="user-a"),
        attempts=1,
        status="running",
    )

    with pytest.raises(expected_exception):
        await handlers.pipeline_cycle_handler(repository, job)

    assert repository.checkpoints[-1]["status"] == "failed"
    assert repository.checkpoints[-1]["output_metadata"]["state"] == result.state.value


@pytest.mark.asyncio
async def test_cycle_handler_records_intentional_skip_without_claiming_evaluation_completion(
    monkeypatch,
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()

    async def load(**_kwargs):
        return _prerequisites()

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.skipped(
            code="agents_disabled", detail="No agent stages are enabled."
        )

    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle-skipped",
        payload=PipelineCyclePayload(user_id="user-a"),
        attempts=1,
        status="running",
    )

    await handlers.pipeline_cycle_handler(repository, job)

    terminal = repository.checkpoints[-1]
    assert terminal["stage"] == "pipeline_cycle"
    assert terminal["output_metadata"]["state"] == PipelineExecutionState.SKIPPED.value
    assert terminal["output_metadata"]["code"] == "agents_disabled"


@pytest.mark.asyncio
async def test_lookup_handler_observes_cancellation_between_checkpoints(
    monkeypatch, _capture_lookup_attempt_outcomes
):
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

    with pytest.raises(JobExecutionCancelled) as exc:
        await handlers.company_lookup_handler(repository, job)

    assert _capture_lookup_attempt_outcomes == []
    assert exc.value.lookup_outcome.disposition.value == "cancelled"


@pytest.mark.asyncio
async def test_lookup_handler_rejects_a_stale_owner_before_identity_write(
    monkeypatch,
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    admissions = []
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:stale-owner",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.example",
        ),
        attempts=1,
        status=JobStatus.RUNNING,
        lease_owner="worker-a",
    )

    async def get_job(**_kwargs):
        return job.model_copy(update={"lease_owner": "worker-b"})

    class IdentityService:
        def __init__(self, _repository):
            pass

        async def admit(self, _observation):
            admissions.append("admitted")
            raise AssertionError("stale worker reached identity authority")

    repository.get_job = get_job
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)

    with pytest.raises(RuntimeError, match="lease"):
        await handlers.company_lookup_handler(repository, job)

    assert admissions == []


@pytest.mark.asyncio
async def test_lookup_handler_detects_mid_handler_lease_loss_before_checkpoint_write(
    monkeypatch,
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:user-a:mid-handler-lease-loss",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            website="https://acme.example",
        ),
        attempts=1,
        status=JobStatus.RUNNING,
        lease_owner="worker-a",
    )
    reads = 0

    async def get_job(**_kwargs):
        nonlocal reads
        reads += 1
        if reads == 1:
            return job
        return job.model_copy(update={"lease_owner": "worker-b"})

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **_kwargs):
            return None

    class IdentityService:
        def __init__(self, _repository):
            pass

        async def admit(self, _observation):
            return SimpleNamespace(
                observation_id="observation-1",
                status=SimpleNamespace(value="resolved"),
                company_id="company-1",
                opportunity_id="opportunity-1",
                identity_case_id=None,
                confidence=1.0,
                blocks_evaluation=False,
            )

    async def load(**_kwargs):
        raise AssertionError("stale worker reached prerequisite loading")

    repository.get_job = get_job
    monkeypatch.setattr(handlers, "IdentityRepository", lambda _pool: IdentityRepository())
    monkeypatch.setattr(handlers, "IdentityService", IdentityService)
    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)

    with pytest.raises(RuntimeError, match="lease"):
        await handlers.company_lookup_handler(repository, job)

    assert repository.checkpoints == []


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["thesis_required", "published_policy_required"])
async def test_lookup_handler_preserves_identity_then_blocks_before_legacy_lookup(
    monkeypatch, code, _capture_lookup_attempt_outcomes
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
    assert _capture_lookup_attempt_outcomes == []
    assert exc.value.lookup_outcome.disposition.value == "blocked"


@pytest.mark.asyncio
async def test_lookup_handler_records_retryable_failure_for_unexpected_pre_run_error(
    monkeypatch, _capture_lookup_attempt_outcomes
):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()

    def resolve(*_args, **_kwargs):
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(handlers, "resolve_company", resolve)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.COMPANY_LOOKUP,
        idempotency_key="lookup:resolver-failure",
        payload=CompanyLookupPayload(
            user_id="user-a",
            company_name="Acme",
            lookup_id="lookup-resolver-failure",
        ),
        attempts=1,
        max_attempts=3,
        status=JobStatus.RUNNING,
    )

    with pytest.raises(RuntimeError, match="resolver unavailable") as exc:
        await handlers.company_lookup_handler(repository, job)

    assert _capture_lookup_attempt_outcomes == []
    assert exc.value.lookup_outcome.disposition.value == "retryable_failure"


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
async def test_cycle_handler_preserves_late_prerequisite_failure(monkeypatch):
    handlers = importlib.import_module("jobs.handlers")
    repository = _Repository()

    async def load(**_kwargs):
        return _prerequisites()

    async def run(*_args, **_kwargs):
        raise EvaluationPrerequisiteError(
            code="certified_inputs_changed",
            detail="Certified inputs changed before engine handoff.",
            recovery_action="Reload prerequisites and retry the cycle.",
        )

    monkeypatch.setattr(handlers, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(handlers, "run_one_pipeline_cycle", run)
    job = AgentJob(
        user_id="user-a",
        job_type=JobType.PIPELINE_CYCLE,
        idempotency_key="cycle-late-prerequisite-failure",
        payload=PipelineCyclePayload(user_id="user-a"),
        attempts=1,
        status="running",
    )

    with pytest.raises(JobExecutionBlocked) as exc:
        await handlers.pipeline_cycle_handler(repository, job)

    assert exc.value.code == "certified_inputs_changed"
    assert exc.value.detail == "Certified inputs changed before engine handoff."
    assert exc.value.recovery_action == "Reload prerequisites and retry the cycle."


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
