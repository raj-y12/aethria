from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import EvaluationPrerequisiteError
from pipeline_execution import (
    MetaCycleResult,
    PipelineExecutionResult,
    PipelineExecutionState,
    ScoutCycleResult,
    StageExecutionResult,
    StageExecutionState,
)


class _Prerequisites:
    user_id = "user-a"
    thesis_context = {"version_id": "thesis-live", "mandate": "Exact mandate"}
    thesis_version_id = "thesis-live"
    policy = SimpleNamespace(policy_version_id="policy-live", policy_hash="hash-live")

    def require_tenant(self, user_id, *, context):
        if user_id != self.user_id:
            raise RuntimeError(f"{context}: tenant mismatch")
        return user_id


@pytest.mark.asyncio
async def test_periodic_gate_failure_returns_actionable_blocked_result(monkeypatch):
    import pipeline_runner

    calls = []

    async def load(**kwargs):
        calls.append(kwargs)
        raise EvaluationPrerequisiteError(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish the policy in Settings.",
        )

    monkeypatch.setattr(pipeline_runner, "load_evaluation_prerequisites", load)

    result = await pipeline_runner.run_one_pipeline_cycle(
        "user-a", fund_intelligence_repository="governed-repository"
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "published_policy_required"
    assert result.recovery_action == "Publish the policy in Settings."
    assert calls == [
        {
            "user_id": "user-a",
            "fund_intelligence_repository": "governed-repository",
        }
    ]


@pytest.mark.asyncio
async def test_periodic_returns_inner_typed_result_and_never_reloads_gate(monkeypatch):
    import pipeline_runner

    expected = PipelineExecutionResult.completed(
        code="pipeline_cycle_completed", detail="Cycle completed."
    )

    async def run_inner(user_id, **kwargs):
        assert user_id == "user-a"
        assert kwargs["evaluation_prerequisites"] is prerequisites
        return expected

    prerequisites = _Prerequisites()
    monkeypatch.setattr(
        pipeline_runner,
        "load_evaluation_prerequisites",
        lambda **_kwargs: pytest.fail("supplied gate context must not reload"),
    )
    monkeypatch.setattr(pipeline_runner, "_run_one_pipeline_cycle_inner", run_inner)

    result = await pipeline_runner.run_one_pipeline_cycle(
        "user-a", evaluation_prerequisites=prerequisites
    )

    assert result is expected


@pytest.mark.asyncio
async def test_periodic_runtime_prerequisites_are_blocked_not_silent_success(monkeypatch):
    import pipeline_runner

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")

    result = await pipeline_runner._run_one_pipeline_cycle_inner(
        "user-a", evaluation_prerequisites=_Prerequisites()
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "supabase_storage_required"


@pytest.mark.asyncio
async def test_enabled_periodic_stages_block_without_canonical_identity_store(monkeypatch):
    import pipeline_runner

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda *_args, **_kwargs: {
            "agent_config": {
                "scouts_enabled": True,
                "reviewers_enabled": True,
                "partners_enabled": True,
            }
        },
    )
    monkeypatch.setattr(
        pipeline_runner,
        "_build_storage_sync",
        lambda *_args: pytest.fail("identity authority must be checked before work"),
    )

    result = await pipeline_runner._run_one_pipeline_cycle_inner(
        "user-a",
        identity_repository=None,
        evaluation_prerequisites=_Prerequisites(),
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "institutional_identity_repository_required"


@pytest.mark.asyncio
async def test_empty_lookup_is_explicitly_skipped_before_gate(monkeypatch):
    import pipeline_runner

    monkeypatch.setattr(
        pipeline_runner,
        "load_evaluation_prerequisites",
        lambda **_kwargs: pytest.fail("empty lookup must not enter evaluation gate"),
    )

    result = await pipeline_runner.run_on_demand_lookup("user-a", "  ")

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.code == "empty_company_name"


@pytest.mark.asyncio
async def test_lookup_continues_without_active_thesis_instead_of_blocking(monkeypatch):
    """On-demand lookup is mandate-aware, not thesis-gated (AGENTS.md, ADR-0010):
    a missing thesis must not block it — only the periodic pipeline blocks on
    that. See docs/known-issues.md "On-demand lookup behaviour conflicts with
    the repository contract and ADR"."""
    import pipeline_runner

    async def load(**_kwargs):
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active thesis is required.",
            recovery_action="Publish a thesis in Settings.",
        )

    monkeypatch.setattr(pipeline_runner, "load_evaluation_prerequisites", load)

    result = await pipeline_runner.run_on_demand_lookup("user-a", "Acme")

    # Lookup proceeds past the thesis gate and reaches a real, unrelated gate
    # (no OPENAI_API_KEY configured in this test) rather than blocking on
    # "thesis_required" — proof the thesis check no longer short-circuits it.
    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code != "thesis_required"


def test_lookup_runner_exposes_no_parallel_outcome_writer():
    import pipeline_runner

    assert not hasattr(pipeline_runner, "_record_lookup_failure")
    assert not hasattr(pipeline_runner, "_record_lookup_execution_result")
    assert not hasattr(pipeline_runner, "list_upsert")


@pytest.mark.asyncio
async def test_reprocess_dry_run_uses_shared_gate_once_and_returns_typed_counts(
    monkeypatch,
):
    import pipeline_runner

    calls = []

    async def load(**kwargs):
        calls.append(kwargs)
        return _Prerequisites()

    storage = SimpleNamespace(get_startups_missing_thesis=lambda *, limit: ["one", "two"])
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(pipeline_runner, "load_evaluation_prerequisites", load)
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _user_id, settings=None: storage)
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda _user_id: {"agent_config": {"reviewers_enabled": True, "partners_enabled": True}},
    )

    result = await pipeline_runner.reprocess_startups_missing_fund_thesis(
        "user-a",
        dry_run=True,
        fund_intelligence_repository="governed-repository",
    )

    assert result.state is PipelineExecutionState.COMPLETED
    assert result.code == "reprocess_dry_run_completed"
    assert result.metadata == {"dry_run": True, "eligible": 2}
    assert calls == [
        {
            "user_id": "user-a",
            "fund_intelligence_repository": "governed-repository",
        }
    ]


@pytest.mark.asyncio
async def test_reprocess_no_work_is_skipped_without_requiring_model_runtime(monkeypatch):
    import pipeline_runner

    storage = SimpleNamespace(get_startups_missing_thesis=lambda *, limit: [])
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _user_id, settings=None: storage)
    monkeypatch.setattr(pipeline_runner, "load_settings", lambda _user_id: {})

    result = await pipeline_runner.reprocess_startups_missing_fund_thesis(
        "user-a", evaluation_prerequisites=_Prerequisites()
    )

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.code == "reprocess_no_work"
    assert result.metadata == {"processed": 0, "skipped": 0, "failed": 0}






class _ScoutPersona:
    def __init__(self, scout_type, result):
        self.scout_type = scout_type
        self.result = result
        self.system_prompt = f"{scout_type} prompt"
        self._last_token_usage = 0

    async def _discover_with_validation(self):
        if isinstance(self.result, Exception):
            raise self.result
        return dict(self.result) if isinstance(self.result, dict) else self.result


def _scout_for_stage(
    results,
    *,
    storage=None,
    cost_controller=None,
    deal_memory=None,
):
    from scout.engine import ScoutEngine

    engine = ScoutEngine.__new__(ScoutEngine)
    engine.tenant_user_id = "user-a"
    engine.logger = __import__("logging").getLogger("test.scout-stage")
    engine.scouts = [
        _ScoutPersona(f"persona_{index}", result)
        for index, result in enumerate(results, start=1)
    ]
    engine.storage = storage
    # ScoutEngine.__new__ bypasses __init__, so active_thesis (always set on
    # a real engine) needs an explicit default here -- run_cycle now reads
    # it to compute the deterministic thesis-fit confidence (2026-08-19).
    engine.active_thesis = None
    engine.cost_controller = cost_controller
    engine.deal_memory = deal_memory
    engine.model = "test-model"
    engine.settings = {"agent_config": {"scouts_enabled": True}, "cost_budget": {"enabled": False}}
    engine.backpressure_threshold = 10
    engine.scout_ramp_threshold = 5
    engine.scout_ramp_max_waves = 1
    engine._sync_thesis_to_scouts = lambda: None
    engine._select_scouts_for_wave = lambda: list(engine.scouts)
    return engine


def _scout_discovery(startup_id="startup-1"):
    return {
        "id": startup_id,
        "name": "Typed Scout Co",
        "one_line": "Typed stage result",
        "confidence": 0.8,
        "scout_type": "market_driven",
        "primary_thesis": "A distinct thesis",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("results", "expected_state", "succeeded", "failed", "skipped"),
    [
        ([_scout_discovery()], StageExecutionState.COMPLETED, 1, 0, 0),
        ([RuntimeError("boom")], StageExecutionState.SKIPPED, 0, 0, 1),
        (
            [_scout_discovery(), RuntimeError("boom")],
            StageExecutionState.COMPLETED,
            1,
            0,
            1,
        ),
    ],
    ids=["clean-success", "all-fail", "partial-failure"],
)
async def test_scout_periodic_result_accounts_for_every_persona(
    monkeypatch, results, expected_state, succeeded, failed, skipped
):
    import scout.engine as scout_module

    result = await _scout_for_stage(results).run_cycle(persist_discoveries=False)

    assert isinstance(result, ScoutCycleResult)
    assert result.outcome.state is expected_state
    assert result.outcome.attempted == len(results)
    assert result.outcome.succeeded == succeeded
    assert result.outcome.failed == failed
    assert result.outcome.skipped == skipped
    if skipped:
        assert result.outcome.warnings
    assert len(result.discoveries) == succeeded

    if skipped and succeeded == 0:
        assert result.outcome.code == "scout_no_eligible_work"
    elif skipped:
        assert result.outcome.code == "scout_completed_with_warnings"


@pytest.mark.asyncio
async def test_scout_periodic_budget_denial_is_blocked(monkeypatch):
    import scout.engine as scout_module

    controller = SimpleNamespace(
        check_budget=lambda *_args, **_kwargs: (False, "budget exhausted")
    )

    result = await _scout_for_stage(
        [_scout_discovery()], cost_controller=controller
    ).run_cycle(persist_discoveries=False)

    assert result.outcome.state is StageExecutionState.BLOCKED
    assert result.outcome.blocked == 1
    assert result.outcome.recovery_action
    assert result.discoveries == []


@pytest.mark.asyncio
async def test_scout_periodic_persistence_failure_is_not_a_success(monkeypatch):
    import scout.engine as scout_module

    storage = SimpleNamespace(
        count_unreviewed=lambda: 0,
        add_discovery=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("store unavailable")
        ),
    )

    result = await _scout_for_stage(
        [_scout_discovery()], storage=storage
    ).run_cycle()

    assert result.outcome.state is StageExecutionState.FAILED
    assert result.outcome.code == "scout_persistence_failures"
    assert result.outcome.failed == 1
    assert result.outcome.succeeded == 0
    assert result.discoveries == []








async def _run_periodic_with_stage_results(
    monkeypatch,
    reviewer_result,
    partner_result,
    *,
    scout_result=None,
    portfolio_result=None,
    meta_result=None,
    partners_enabled=True,
):
    import pipeline_runner

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda *_args, **_kwargs: {
            "agent_config": {
                "scouts_enabled": scout_result is not None,
                "reviewers_enabled": True,
                "partners_enabled": partners_enabled,
            }
        },
    )
    storage = SimpleNamespace(
        count_unreviewed=lambda: reviewer_result.attempted,
        count_undecided=lambda: partner_result.attempted,
    )
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _uid, settings=None: storage)

    class Scout:
        scouts = []

        async def run_cycle(self, **_kwargs):
            return scout_result

        def close(self):
            return None

    class Reviewer:
        last_cycle_stats = {}

        async def run_cycle(self, **_kwargs):
            assert partners_enabled, "Shared analysis must not invoke a disabled Partner"
            return reviewer_result

        def close(self):
            return None

    class Partner:
        last_cycle_escalations = 0

        async def run_cycle(self, **_kwargs):
            assert partners_enabled, "Disabled Partner must not execute"
            return partner_result

        def close(self):
            return None

    engines = SimpleNamespace(
        scout_engine=Scout(),
        reviewer_engine=Reviewer(),
        partner_engine=Partner(),
        portfolio_store=SimpleNamespace(),
        cost_controller=None,
    )
    monkeypatch.setattr(pipeline_runner, "_build_pipeline_engines", lambda **_kw: engines)

    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline_runner, "_prune_unreferenced_startups", no_op)
    monkeypatch.setattr(
        pipeline_runner, "_admit_autonomous_discoveries", no_op
    )
    monkeypatch.setattr(pipeline_runner, "_count_startups_sync", lambda _uid: 0)
    monkeypatch.setattr(pipeline_runner, "_notify_startups_changed", lambda *_a: None)

    class Portfolio:
        async def run_cycle(self):
            return portfolio_result or _stage_no_work("portfolio")

    class Meta:
        async def run_cycle(self):
            return MetaCycleResult(
                outcome=meta_result or _stage_no_work("meta"),
                report=None,
            )

    monkeypatch.setattr(pipeline_runner, "PortfolioEngine", lambda **_kwargs: Portfolio())
    monkeypatch.setattr(pipeline_runner, "MetaAgent", lambda **_kwargs: Meta())

    class Query:
        def insert(self, _record):
            return self

        def execute(self):
            return None

    monkeypatch.setattr(
        pipeline_runner,
        "get_service_client",
        lambda: SimpleNamespace(table=lambda _name: Query()),
    )

    class IdentityRepository:
        async def list_linked_legacy_startup_ids(self, **_kwargs):
            return ["startup-1"]

    return await pipeline_runner._run_one_pipeline_cycle_inner(
        "user-a",
        identity_repository=IdentityRepository(),
        evaluation_prerequisites=_Prerequisites(),
    )


def _stage_success(stage, count=1):
    return StageExecutionResult.completed(
        stage=stage,
        code=f"{stage}_completed",
        detail=f"{stage} completed.",
        attempted=count,
        succeeded=count,
    )


def _stage_no_work(stage):
    return StageExecutionResult.skipped_result(
        stage=stage,
        code=f"{stage}_no_eligible_work",
        detail=f"No eligible {stage} work.",
    )


@pytest.mark.asyncio
async def test_shared_periodic_analysis_blocks_when_partner_disabled(monkeypatch):
    result = await _run_periodic_with_stage_results(
        monkeypatch, _stage_success("reviewer"), _stage_success("partner"),
        partners_enabled=False,
    )
    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "analysis_partner_disabled"
    assert result.metadata["stage_results"]["partner"]["code"] == "partner_disabled"


@pytest.mark.asyncio
async def test_periodic_runner_aggregates_partial_failure_without_clean_completion(
    monkeypatch,
):
    reviewer = StageExecutionResult.failed_result(
        stage="reviewer",
        code="reviewer_candidate_failures",
        detail="One Reviewer candidate failed.",
        recovery_action="Retry the failed Reviewer candidate.",
        attempted=2,
        succeeded=1,
        failed=1,
    )
    result = await _run_periodic_with_stage_results(
        monkeypatch, reviewer, _stage_success("partner")
    )

    assert result.state is PipelineExecutionState.FAILED_STAGE
    assert result.failed_stage == "reviewer"
    assert result.code == "reviewer_candidate_failures"
    assert result.recovery_action == "Retry the failed Reviewer candidate."
    assert result.metadata["stage_results"]["reviewer"]["failed"] == 1
    assert result.metadata["stage_results"]["partner"]["succeeded"] == 1
    assert set(result.metadata["stage_results"]) == {
        "scout",
        "reviewer",
        "partner",
        "portfolio",
        "meta",
    }


@pytest.mark.asyncio
async def test_periodic_runner_preserves_fully_budget_blocked_stage(monkeypatch):
    reviewer = StageExecutionResult.blocked_result(
        stage="reviewer",
        code="reviewer_budget_blocked",
        detail="Reviewer budget denied all eligible work.",
        recovery_action="Increase the Reviewer budget.",
        attempted=2,
        blocked=2,
    )
    result = await _run_periodic_with_stage_results(
        monkeypatch, reviewer, _stage_no_work("partner")
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "reviewer_budget_blocked"
    assert result.recovery_action == "Increase the Reviewer budget."
    assert result.metadata["stage_results"]["reviewer"]["blocked"] == 2


@pytest.mark.asyncio
async def test_periodic_runner_distinguishes_no_work_from_clean_success(monkeypatch):
    no_work = await _run_periodic_with_stage_results(
        monkeypatch, _stage_no_work("reviewer"), _stage_no_work("partner")
    )
    clean = await _run_periodic_with_stage_results(
        monkeypatch, _stage_success("reviewer"), _stage_success("partner")
    )

    assert no_work.state is PipelineExecutionState.SKIPPED
    assert no_work.code == "pipeline_cycle_no_work"
    assert clean.state is PipelineExecutionState.COMPLETED
    assert clean.metadata["reviewed"] == 1
    assert clean.metadata["decided"] == 1


@pytest.mark.asyncio
async def test_periodic_runner_counts_due_portfolio_or_meta_work_as_completion(
    monkeypatch,
):
    portfolio_completed = await _run_periodic_with_stage_results(
        monkeypatch,
        _stage_no_work("reviewer"),
        _stage_no_work("partner"),
        portfolio_result=_stage_success("portfolio"),
    )

    assert portfolio_completed.state is PipelineExecutionState.COMPLETED
    assert portfolio_completed.metadata["stage_results"]["portfolio"][
        "state"
    ] == "completed"


@pytest.mark.asyncio
async def test_periodic_runner_aggregates_meta_failure(monkeypatch):
    meta_failed = StageExecutionResult.failed_result(
        stage="meta",
        code="meta_cycle_failed",
        detail="Meta analysis failed.",
        recovery_action="Restore the analysis store and retry.",
        attempted=1,
        failed=1,
    )
    result = await _run_periodic_with_stage_results(
        monkeypatch,
        _stage_no_work("reviewer"),
        _stage_no_work("partner"),
        meta_result=meta_failed,
    )

    assert result.state is PipelineExecutionState.FAILED_STAGE
    assert result.failed_stage == "meta"
    assert result.metadata["stage_results"]["meta"]["failed"] == 1


@pytest.mark.asyncio
async def test_periodic_runner_aggregates_scout_partial_failure(monkeypatch):
    scout_failed = ScoutCycleResult(
        outcome=StageExecutionResult.failed_result(
            stage="scout",
            code="scout_persona_failures",
            detail="One Scout persona failed.",
            recovery_action="Inspect Scout logs and retry.",
            attempted=2,
            succeeded=1,
            failed=1,
        ),
        discoveries=[_scout_discovery()],
    )
    result = await _run_periodic_with_stage_results(
        monkeypatch,
        _stage_no_work("reviewer"),
        _stage_no_work("partner"),
        scout_result=scout_failed,
    )

    assert result.state is PipelineExecutionState.FAILED_STAGE
    assert result.failed_stage == "scout"
    assert result.metadata["stage_results"]["scout"]["failed"] == 1


class _LoopLogger:
    def __init__(self):
        self.errors = []
        self.infos = []

    def info(self, message, *args, **_kwargs):
        self.infos.append(message % args if args else str(message))

    def warning(self, message, *args, **_kwargs):
        self.infos.append(message % args if args else str(message))

    def error(self, message, *args, **_kwargs):
        self.errors.append(message % args if args else str(message))


@pytest.mark.asyncio
async def test_scout_loop_consumes_typed_results_without_type_errors(
    monkeypatch,
):
    async def no_sleep(_seconds):
        return None

    logger = _LoopLogger()
    completed = _stage_success("scout")
    import scout.engine as module
    from scout.engine import ScoutEngine

    engine = ScoutEngine.__new__(ScoutEngine)
    engine.scouts = []

    async def run_cycle(**_kwargs):
        engine.running = False
        return ScoutCycleResult(
            outcome=completed,
            discoveries=[{"scout_type": "market_driven", "name": "Co", "one_line": "One"}],
        )

    engine.tenant_user_id = "user-a"
    engine.settings = {"agent_config": {"scouts_enabled": True, "reviewers_enabled": True, "partners_enabled": True}}
    engine.interval_seconds = 1
    engine.logger = logger
    engine.run_cycle = run_cycle
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)

    await engine.run_forever()

    assert logger.errors == []
    assert any("state=completed" in message for message in logger.infos)
