from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    EvaluationPrerequisites,
)
from pipeline_runner import run_on_demand_lookup, run_one_pipeline_cycle
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState


class _FakeScoutEngine:
    active_thesis = "unset"
    calls = 0
    outcome = None
    resolution = None

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")

    async def run_named_lookup(self, **kwargs):
        type(self).calls += 1
        type(self).resolution = kwargs.get("resolution")
        self.last_lookup_outcome = type(self).outcome
        return "startup-1"


class _FakeReviewerEngine:
    active_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"
    calls = 0
    result = True

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return type(self).result


class _FakePartnerEngine:
    fund_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"
    calls = 0
    result = True

    def __init__(self, *args, **kwargs):
        type(self).fund_thesis = kwargs.get("fund_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return type(self).result


class _FakeThesis:
    """Stand-in for an active FundThesis; only as_engine_context() is exercised."""

    version_id = "thesis-v1"
    CONTEXT = {"version_id": "thesis-v1", "mandate": "AI infra, seed/A"}

    def as_engine_context(self):
        return dict(self.CONTEXT)


def _prerequisites(
    user_id="user_123",
    *,
    policy_version_id="policy-live",
    policy_hash="hash-live",
):
    return EvaluationPrerequisites(
        user_id=user_id,
        thesis_context=_FakeThesis.CONTEXT,
        thesis_version_id="thesis-v1",
        compiled_scoring_policy={
            "policy_version_id": policy_version_id,
            "policy_hash": policy_hash,
        },
        partner_rules={"version": "rules-live"},
        fund_config={},
        policy=SimpleNamespace(
            policy_version_id=policy_version_id,
            policy_hash=policy_hash,
        ),
    )


def _wire_common_engines(monkeypatch):
    _FakeScoutEngine.calls = 0
    _FakeScoutEngine.outcome = None
    _FakeScoutEngine.resolution = None
    _FakeReviewerEngine.calls = 0
    _FakeReviewerEngine.result = True
    _FakePartnerEngine.calls = 0
    _FakePartnerEngine.result = True
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("pipeline_runner.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "pipeline_runner.SupabaseStartupsStorage",
        lambda client, user_id: SimpleNamespace(_client=client, _user_id=user_id),
    )
    monkeypatch.setattr("pipeline_runner.load_settings", lambda user_id: {"cost_budget": {"enabled": False}})
    monkeypatch.setattr("pipeline_runner.DealMemory", lambda user_id: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.ScoutEngine", _FakeScoutEngine)
    monkeypatch.setattr("pipeline_runner.ReviewerEngine", _FakeReviewerEngine)
    monkeypatch.setattr("pipeline_runner.PartnerEngine", _FakePartnerEngine)
    monkeypatch.setattr("pipeline_runner.PortfolioStore", lambda *args, **kwargs: SimpleNamespace())
    prerequisites = _prerequisites()

    async def load_prerequisites(**kwargs):
        assert kwargs["user_id"] == "user_123"
        return prerequisites

    monkeypatch.setattr(
        "pipeline_runner.load_evaluation_prerequisites", load_prerequisites
    )


@pytest.mark.asyncio
async def test_on_demand_lookup_evaluates_against_active_thesis(monkeypatch):
    """Lookup is open, but evaluation must be mandate-aware: when a thesis exists,
    its engine context flows into scout / reviewer / partner so alignment is scored."""
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    monkeypatch.setattr(
        "pipeline_runner._bootstrap_default_thesis_or_raise",
        lambda *a, **k: pytest.fail("should not bootstrap when an active thesis already exists"),
    )

    result = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-123")

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert _FakeScoutEngine.active_thesis == _FakeThesis.CONTEXT
    assert _FakeReviewerEngine.active_thesis == _FakeThesis.CONTEXT
    assert _FakePartnerEngine.fund_thesis == _FakeThesis.CONTEXT


@pytest.mark.asyncio
async def test_on_demand_lookup_forwards_resolution_and_records_stage_timings(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    resolution = SimpleNamespace(canonical_name="Acme")
    observed = []
    monkeypatch.setattr(
        "pipeline_runner.metrics.observe_pipeline_stage",
        lambda duration, **labels: observed.append(labels),
    )

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-timed-123",
        resolution=resolution,
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert _FakeScoutEngine.resolution is resolution
    assert [(item["stage"], item["outcome"]) for item in observed] == [
        ("scout", "success"),
        ("reviewer", "success"),
        ("partner", "success"),
    ]
    assert all(item["pipeline"] == "lookup" for item in observed)


@pytest.mark.asyncio
async def test_on_demand_lookup_blocks_when_no_mandate(monkeypatch):
    _wire_common_engines(monkeypatch)

    async def load_prerequisites(**kwargs):
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active fund thesis is required before evaluation.",
            recovery_action="Create and publish the fund thesis in Settings.",
        )

    monkeypatch.setattr(
        "pipeline_runner.load_evaluation_prerequisites", load_prerequisites
    )

    result = await run_on_demand_lookup(
        "user_123", "Perplexity AI", lookup_id="lookup-123"
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "thesis_required"
    assert _FakeScoutEngine.calls == 0
    assert _FakeReviewerEngine.calls == 0
    assert _FakePartnerEngine.calls == 0


@pytest.mark.asyncio
async def test_on_demand_lookup_rejects_empty_tenant_before_other_early_returns():
    with pytest.raises(RuntimeError, match="Missing explicit user_id"):
        await run_on_demand_lookup(" ", "")


@pytest.mark.asyncio
async def test_pipeline_cycle_rejects_empty_tenant_before_other_early_returns():
    with pytest.raises(RuntimeError, match="Missing explicit user_id"):
        await run_one_pipeline_cycle(" ")


@pytest.mark.asyncio
async def test_direct_lookup_selects_governed_repository(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr(
        "pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis()
    )
    governed_repository = object()
    calls = []
    prerequisites = _prerequisites(
        policy_version_id="governed-policy-live",
        policy_hash="governed-hash-live",
    )

    async def load_prerequisites(**kwargs):
        calls.append(kwargs)
        return prerequisites

    monkeypatch.setattr(
        "pipeline_runner.load_evaluation_prerequisites", load_prerequisites
    )

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-governed",
        fund_intelligence_repository=governed_repository,
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert calls == [
        {
            "user_id": "user_123",
            "fund_intelligence_repository": governed_repository,
        }
    ]


@pytest.mark.asyncio
async def test_direct_pipeline_cycle_gates_and_passes_governed_repository(monkeypatch):
    governed_repository = object()
    expected = EvaluationPrerequisiteError(
        code="published_policy_required",
        detail="A published policy is required.",
        recovery_action="Publish the fund scoring policy in Settings.",
    )
    calls = []

    async def load_prerequisites(**kwargs):
        calls.append(kwargs)
        raise expected

    async def run_inner(*args, **kwargs):
        raise AssertionError("periodic work must not start before the shared gate")

    monkeypatch.setattr(
        "pipeline_runner.load_evaluation_prerequisites", load_prerequisites
    )
    monkeypatch.setattr("pipeline_runner._run_one_pipeline_cycle_inner", run_inner)

    result = await run_one_pipeline_cycle(
        "user_123",
        fund_intelligence_repository=governed_repository,
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == expected.code
    assert result.detail == expected.detail
    assert result.recovery_action == expected.recovery_action
    assert calls == [
        {
            "user_id": "user_123",
            "fund_intelligence_repository": governed_repository,
        }
    ]


@pytest.mark.asyncio
async def test_direct_pipeline_cycle_reuses_supplied_prerequisites(monkeypatch):
    prerequisites = _prerequisites()
    calls = []

    async def load_prerequisites(**kwargs):
        raise AssertionError("supplied prerequisites must not load twice")

    async def run_inner(user_id, **kwargs):
        calls.append((user_id, kwargs))
        return PipelineExecutionResult.completed(
            code="pipeline_cycle_completed", detail="Cycle completed."
        )

    monkeypatch.setattr(
        "pipeline_runner.load_evaluation_prerequisites", load_prerequisites
    )
    monkeypatch.setattr("pipeline_runner._run_one_pipeline_cycle_inner", run_inner)

    result = await run_one_pipeline_cycle(
        "user_123",
        evaluation_prerequisites=prerequisites,
    )

    assert calls[0][0] == "user_123"
    assert calls[0][1]["evaluation_prerequisites"] is prerequisites
    assert result.state is PipelineExecutionState.COMPLETED


@pytest.mark.asyncio
async def test_periodic_consumes_certified_thesis_without_reloading_active_thesis(
    monkeypatch,
):
    prerequisites = _prerequisites()

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "pipeline_runner.load_settings",
        lambda user_id, *, use_cache=False: {
            "agent_config": {"scouts_enabled": True}
        },
    )
    storage = SimpleNamespace(remove_startups_without_references=lambda: 0)
    monkeypatch.setattr("pipeline_runner._build_storage_sync", lambda user_id: storage)
    monkeypatch.setattr(
        "pipeline_runner._load_active_thesis_sync",
        lambda _user_id: pytest.fail("certified thesis must not be reloaded"),
    )
    class Scout:
        scouts = []

        async def run_cycle(self, **_kwargs):
            return []

        def close(self):
            return None

    class Reviewer:
        last_cycle_stats = {}

        async def run_cycle(self, **_kwargs):
            return 0

        def close(self):
            return None

    class Partner:
        last_cycle_escalations = 0

        async def run_cycle(self, **_kwargs):
            return 0

        def close(self):
            return None

    engines = SimpleNamespace(
        scout_engine=Scout(),
        reviewer_engine=Reviewer(),
        partner_engine=Partner(),
        portfolio_store=SimpleNamespace(),
        cost_controller=None,
    )
    monkeypatch.setattr("pipeline_runner._build_pipeline_engines", lambda **_kwargs: engines)
    monkeypatch.setattr("pipeline_runner._prune_unreferenced_startups", lambda *_args: _async_none())
    monkeypatch.setattr(
        "pipeline_runner._admit_autonomous_discoveries",
        lambda **_kwargs: _async_none(),
    )
    monkeypatch.setattr("pipeline_runner._count_startups_sync", lambda _user_id: 0)

    class Portfolio:
        async def run_cycle(self):
            return None

    class Meta:
        async def run_cycle(self):
            return None

    monkeypatch.setattr("pipeline_runner.PortfolioEngine", lambda **_kwargs: Portfolio())
    monkeypatch.setattr("pipeline_runner.MetaAgent", lambda **_kwargs: Meta())

    identity_repository = SimpleNamespace(
        list_linked_legacy_startup_ids=lambda **_kwargs: _async_empty_list()
    )
    result = await run_one_pipeline_cycle(
        "user_123",
        manual_one_shot=True,
        identity_repository=identity_repository,
        evaluation_prerequisites=prerequisites,
    )

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.code == "pipeline_cycle_no_work"


async def _async_none():
    return None


async def _async_empty_list():
    return []


@pytest.mark.asyncio
async def test_lookup_consumes_certified_thesis_without_reloading_active_thesis(
    monkeypatch,
):
    _wire_common_engines(monkeypatch)
    prerequisites = _prerequisites()

    monkeypatch.setattr(
        "pipeline_runner._load_active_thesis_sync",
        lambda _user_id: pytest.fail("certified thesis must not be reloaded"),
    )

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        evaluation_prerequisites=prerequisites,
    )

    assert result.state is PipelineExecutionState.COMPLETED


@pytest.mark.asyncio
async def test_on_demand_lookup_cancelled_before_scout_does_not_start(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())

    result = await run_on_demand_lookup(
        "user_123",
        "Perplexity AI",
        lookup_id="lookup-123",
        is_cancelled=lambda: True,
    )

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.startup_id is None
    assert _FakeScoutEngine.calls == 0
    assert _FakeReviewerEngine.calls == 0
    assert _FakePartnerEngine.calls == 0


@pytest.mark.asyncio
async def test_on_demand_lookup_cancelled_after_scout_stops_before_review(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    checks = iter([False, False, True])

    result = await run_on_demand_lookup(
        "user_123",
        "Perplexity AI",
        lookup_id="lookup-123",
        is_cancelled=lambda: next(checks, True),
    )

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.startup_id == "startup-1"
    assert _FakeScoutEngine.calls == 1
    assert _FakeReviewerEngine.calls == 0
    assert _FakePartnerEngine.calls == 0


@pytest.mark.asyncio
async def test_on_demand_lookup_records_terminal_failure_when_review_exhausts_retries(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    _FakeReviewerEngine.result = False
    recorded = []
    states = []

    async def _record(user_id, lookup_id, message):
        recorded.append((user_id, lookup_id, message))

    monkeypatch.setattr("pipeline_runner._record_lookup_failure", _record)
    monkeypatch.setattr("pipeline_runner.upsert_pipeline_state", lambda *a, **k: states.append(k))

    result = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-review-fail")

    assert result.state is PipelineExecutionState.FAILED_STAGE
    assert result.failed_stage == "reviewer"
    assert result.startup_id == "startup-1"
    assert _FakeReviewerEngine.calls == 1
    assert _FakePartnerEngine.calls == 0
    assert recorded and recorded[0][:2] == ("user_123", "lookup-review-fail")
    assert "review" in recorded[0][2].lower()
    assert states[-1]["startup_id"] == "startup-1"
    assert states[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_on_demand_lookup_records_terminal_failure_when_partner_exhausts_retries(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    _FakePartnerEngine.result = False
    recorded = []
    states = []

    async def _record(user_id, lookup_id, message):
        recorded.append((user_id, lookup_id, message))

    monkeypatch.setattr("pipeline_runner._record_lookup_failure", _record)
    monkeypatch.setattr("pipeline_runner.upsert_pipeline_state", lambda *a, **k: states.append(k))

    result = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-partner-fail")

    assert result.state is PipelineExecutionState.FAILED_STAGE
    assert result.failed_stage == "partner"
    assert result.startup_id == "startup-1"
    assert _FakeReviewerEngine.calls == 1
    assert _FakePartnerEngine.calls == 1
    assert recorded and recorded[0][:2] == ("user_123", "lookup-partner-fail")
    assert "decision" in recorded[0][2].lower()
    assert states[-1]["startup_id"] == "startup-1"
    assert states[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_add_context_rerun_regenerates_and_persists_memo(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    patches = []
    prepared = []
    startup = SimpleNamespace(startup_id="startup-1")
    storage = SimpleNamespace(
        _client=SimpleNamespace(),
        _user_id="user_123",
        prepare_rerun_startup=lambda startup_id, **kwargs: prepared.append((startup_id, kwargs)) or startup_id,
        get_startup=lambda startup_id: startup,
        update_startup_partial=lambda startup_id, patch: patches.append((startup_id, patch)) or True,
    )
    monkeypatch.setattr("pipeline_runner.SupabaseStartupsStorage", lambda client, user_id: storage)

    class _MemoGenerator:
        def generate_memo(self, current, **kwargs):
            assert current is startup
            assert kwargs["tenant_user_id"] == "user_123"
            assert kwargs["for_display"] is True
            return "# Regenerated memo\n\nNew pilot evidence incorporated."

    monkeypatch.setattr("pipeline_runner.MemoGenerator", _MemoGenerator)
    monkeypatch.setattr("pipeline_runner._build_rerun_operator_context", lambda context: context)

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-rerun-1",
        additional_context="https://acme.example/news",
        replace_startup_id="startup-1",
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert _FakeScoutEngine.calls == 0
    assert prepared[0][0] == "startup-1"
    assert patches == [
        (
            "startup-1",
            {"investment_memo_markdown": "# Regenerated memo\n\nNew pilot evidence incorporated."},
        )
    ]


@pytest.mark.asyncio
async def test_duplicate_lookup_persists_terminal_existing_startup_outcome(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    _FakeScoutEngine.outcome = {
        "status": "ALREADY_IN_DEAL_FLOW",
        "startup_id": "startup-1",
        "message": "This company is already in your deal flow.",
    }
    outcomes = []

    def record(table, payload, *, user_id):
        outcomes.append((table, payload, user_id))
        return payload["id"]

    monkeypatch.setattr("pipeline_runner.list_upsert", record)

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-existing-1",
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert outcomes == [
        (
            "lookup_job_outcomes",
            {
                "id": "lookup-existing-1",
                "lookup_id": "lookup-existing-1",
                "status": "already_in_deal_flow",
                "code": "lookup_completed",
                "detail": "This company is already in your deal flow.",
                "startup_id": "startup-1",
                "message": "This company is already in your deal flow.",
            },
            "user_123",
        )
    ]


@pytest.mark.asyncio
async def test_lookup_emits_durable_stage_checkpoints_without_handoff_sleeps(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    checkpoints = []

    async def checkpoint(stage, status, metadata):
        checkpoints.append((stage, status, metadata))

    async def no_sleep(*args, **kwargs):
        pytest.fail("lookup stage handoff must not sleep for storage visibility")

    monkeypatch.setattr("pipeline_runner.asyncio.sleep", no_sleep)

    result = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-checkpoints-1",
        pipeline_run_id="fd1e14c8-b1c5-4c25-af07-ad0ac487b5be",
        checkpoint=checkpoint,
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.startup_id == "startup-1"
    assert [(stage, status) for stage, status, _ in checkpoints] == [
        ("accepted", "succeeded"),
        ("scout", "succeeded"),
        ("reviewer", "succeeded"),
        ("partner", "succeeded"),
        ("completed", "succeeded"),
    ]
    assert all("startup" not in metadata for _, _, metadata in checkpoints)
    assert checkpoints[0][2] == {
        "lookup_id": "lookup-checkpoints-1",
        "pipeline_run_id": "fd1e14c8-b1c5-4c25-af07-ad0ac487b5be",
        "thesis_version_id": "thesis-v1",
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
    }
