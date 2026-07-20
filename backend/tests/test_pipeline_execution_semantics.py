from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import EvaluationPrerequisiteError
from pipeline_execution import (
    PipelineExecutionResult,
    PipelineExecutionState,
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
async def test_lookup_gate_failure_returns_actionable_blocked_result(monkeypatch):
    import pipeline_runner

    async def load(**_kwargs):
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active thesis is required.",
            recovery_action="Publish a thesis in Settings.",
        )

    monkeypatch.setattr(pipeline_runner, "load_evaluation_prerequisites", load)

    result = await pipeline_runner.run_on_demand_lookup("user-a", "Acme")

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "thesis_required"
    assert result.recovery_action == "Publish a thesis in Settings."


@pytest.mark.asyncio
async def test_direct_lookup_status_persists_actionable_typed_failure(monkeypatch):
    import pipeline_runner

    records = []
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setattr(
        pipeline_runner,
        "list_upsert",
        lambda collection, record, *, user_id: records.append(
            (collection, record, user_id)
        ),
    )
    result = PipelineExecutionResult.stage_failure(
        stage="reviewer",
        code="reviewer_stage_failed",
        detail="Reviewer could not complete.",
        recovery_action="Inspect Reviewer logs and retry.",
        startup_id="startup-1",
    )

    await pipeline_runner._record_lookup_execution_result(
        "user-a", "lookup-1", result
    )

    assert records == [
        (
            "lookup_job_outcomes",
            {
                "id": "lookup-1",
                "lookup_id": "lookup-1",
                "status": "failed_stage",
                "code": "reviewer_stage_failed",
                "message": "Reviewer could not complete.",
                "recovery_action": "Inspect Reviewer logs and retry.",
                "failed_stage": "reviewer",
                "startup_id": "startup-1",
            },
            "user-a",
        )
    ]


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
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _user_id: storage)
    monkeypatch.setattr(
        pipeline_runner, "is_thesis_reprocess_agents_enabled", lambda _user_id: True
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
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _user_id: storage)

    result = await pipeline_runner.reprocess_startups_missing_fund_thesis(
        "user-a", evaluation_prerequisites=_Prerequisites()
    )

    assert result.state is PipelineExecutionState.SKIPPED
    assert result.code == "reprocess_no_work"
    assert result.metadata == {"processed": 0, "skipped": 0, "failed": 0}


class _StageStorage:
    _client = None
    _user_id = "user-a"

    def __init__(self, startups=(), *, persist_review=True):
        self.startups = list(startups)
        self.persist_review = persist_review

    def count_unreviewed(self):
        return len(self.startups)

    def get_unreviewed(self, *, limit):
        return self.startups[:limit]

    def add_review(self, *_args, **_kwargs):
        return self.persist_review


def _review_candidate(startup_id="startup-1"):
    return SimpleNamespace(
        startup_id=startup_id,
        scout_info=SimpleNamespace(confidence_score=0.9),
    )


def _reviewer_for_stage(storage, *, cost_controller=None, persona_failure=False):
    from reviewer.engine import ReviewerEngine

    engine = ReviewerEngine.__new__(ReviewerEngine)
    engine.tenant_user_id = "user-a"
    engine.logger = __import__("logging").getLogger("test.reviewer-stage")
    engine.storage = storage
    engine.cost_controller = cost_controller
    engine.last_cycle_stats = {}
    engine.ramp_threshold = 5
    engine.ramp_batch_max = 20
    engine.batch_size = 5
    engine.use_structured_scoring = False
    engine.active_thesis = None
    engine.deal_memory = None
    engine.agent_id = "reviewer-test"
    engine.model = "test-model"
    engine._sync_thesis_to_reviewers = lambda: None
    engine._build_scout_output_payload = lambda startup: {
        "id": startup.startup_id,
        "name": "Typed Stage Co",
    }

    class Persona:
        _last_token_usage = 0

        async def review(self, _payload):
            if persona_failure:
                raise RuntimeError("persona failed")
            return {
                "market_score": 7.25,
                "product_score": 7.25,
                "technical_score": 7.25,
                "execution_score": 7.25,
                "overall_summary": "Typed result fixture",
                "key_risks": [],
                "verdict": "MEDIUM",
            }

    engine.reviewer = Persona()
    engine.skeptical_reviewer = Persona()
    engine.opportunist_reviewer = Persona()
    engine._blend_numeric_scores_into_primary = lambda *_args: None
    engine._refresh_derived_after_dimension_changes = lambda *_args: None
    engine._derive_verdict_from_scores = lambda *_args: None
    engine._pick_primary_structured_signals = lambda *_args: None
    engine._persist_scoring_trail = lambda *_args: None
    engine._apply_rule_based_thesis_alignment = lambda *_args: None
    engine._apply_resource_fund_thesis_alignment = lambda *_args: None
    engine._compute_consensus = lambda *_args: {
        "consensus_verdict": "MEDIUM",
        "reviewer_disagreement": False,
        "score_variance": 0.0,
    }
    engine._build_single_reviews = lambda *_args: []
    return engine


@pytest.mark.asyncio
async def test_reviewer_periodic_result_reports_no_work_and_budget_block(monkeypatch):
    import reviewer.engine as reviewer_module

    monkeypatch.setattr(reviewer_module, "is_reviewers_enabled", lambda _uid: True)
    no_work = await _reviewer_for_stage(_StageStorage()).run_cycle()

    cost_controller = SimpleNamespace(
        check_budget=lambda *_args, **_kwargs: (False, "monthly budget exhausted")
    )
    blocked = await _reviewer_for_stage(
        _StageStorage([_review_candidate()]), cost_controller=cost_controller
    ).run_cycle()

    assert isinstance(no_work, StageExecutionResult)
    assert no_work.state is StageExecutionState.SKIPPED
    assert no_work.code == "reviewer_no_eligible_work"
    assert blocked.state is StageExecutionState.BLOCKED
    assert blocked.code == "reviewer_budget_blocked"
    assert blocked.blocked == 1
    assert blocked.recovery_action


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("persona_failure", "persist_review", "expected_state", "expected_succeeded"),
    [
        (True, True, StageExecutionState.FAILED, 0),
        (False, False, StageExecutionState.FAILED, 0),
        (False, True, StageExecutionState.COMPLETED, 1),
    ],
    ids=["all-personas-fail", "persistence-fails", "clean-success"],
)
async def test_reviewer_periodic_result_accounts_for_candidate_outcomes(
    monkeypatch,
    persona_failure,
    persist_review,
    expected_state,
    expected_succeeded,
):
    import meta.calibrator as calibrator_module
    import reviewer.engine as reviewer_module
    import utils.adapters as adapters_module

    monkeypatch.setattr(reviewer_module, "is_reviewers_enabled", lambda _uid: True)
    monkeypatch.setattr(
        reviewer_module, "get_runtime_limits", lambda _uid: {"max_agents_per_run": 5}
    )
    monkeypatch.setattr(
        reviewer_module,
        "load_settings",
        lambda _uid: {"agent_config": {"confidence_threshold": 0.2}},
    )
    monkeypatch.setattr(
        reviewer_module, "enrich_scout_for_reviewer_llm", lambda payload, _uid: payload
    )
    monkeypatch.setattr(
        reviewer_module,
        "apply_resolution_to_primary",
        lambda *_args: ([], "aligned"),
    )
    monkeypatch.setattr(
        reviewer_module,
        "build_aethria_view",
        lambda **_kwargs: SimpleNamespace(model_dump=lambda **_kw: {}),
    )
    monkeypatch.setattr(calibrator_module, "load_calibration_state", lambda _uid: {})
    monkeypatch.setattr(
        adapters_module,
        "reviewer_output_to_review_info",
        lambda _output: SimpleNamespace(),
    )
    storage = _StageStorage(
        [_review_candidate()], persist_review=persist_review
    )

    result = await _reviewer_for_stage(
        storage, persona_failure=persona_failure
    ).run_cycle()

    assert result.state is expected_state
    assert result.attempted == 1
    assert result.succeeded == expected_succeeded
    assert result.failed == 1 - expected_succeeded
    if result.failed:
        assert result.recovery_action


def _partner_for_stage(entries, *, cost_controller=None, outcome=(True, None)):
    from partner.engine import PartnerEngine

    engine = PartnerEngine.__new__(PartnerEngine)
    engine.tenant_user_id = "user-a"
    engine.logger = __import__("logging").getLogger("test.partner-stage")
    engine.storage = SimpleNamespace(count_undecided=lambda: len(entries))
    engine.cost_controller = cost_controller
    engine.batch_max = 20
    engine.last_cycle_escalations = 0
    engine.deal_memory = None
    engine._get_undecided_entries = lambda *, limit=None: list(entries)[:limit]

    async def decide(*_args, **_kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        success, decision = outcome
        return success, decision or {
            "recommendation": "MONITOR",
            "confidence": 0.6,
            "human_review_required": False,
        }

    engine._decide_and_save = decide
    return engine


def _partner_entry(startup_id="startup-1"):
    return {
        "id": startup_id,
        "scout": {"name": "Typed Stage Co", "primary_thesis": ""},
        "review": {},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entries", "cost_controller", "outcome", "expected_state"),
    [
        ([], None, (True, None), StageExecutionState.SKIPPED),
        (
            [_partner_entry()],
            SimpleNamespace(check_budget=lambda *_args, **_kwargs: (False, "budget")),
            (True, None),
            StageExecutionState.BLOCKED,
        ),
        ([_partner_entry()], None, (False, None), StageExecutionState.FAILED),
        (
            [_partner_entry()],
            None,
            RuntimeError("decision failed"),
            StageExecutionState.FAILED,
        ),
        ([_partner_entry()], None, (True, None), StageExecutionState.COMPLETED),
    ],
    ids=["no-work", "budget-block", "persistence-failure", "exception", "success"],
)
async def test_partner_periodic_result_accounts_for_every_candidate(
    monkeypatch, entries, cost_controller, outcome, expected_state
):
    import partner.engine as partner_module

    monkeypatch.setattr(partner_module, "is_partners_enabled", lambda _uid: True)
    monkeypatch.setattr(
        partner_module, "get_runtime_limits", lambda _uid: {"max_agents_per_run": 20}
    )

    result = await _partner_for_stage(
        entries, cost_controller=cost_controller, outcome=outcome
    ).run_cycle()

    assert isinstance(result, StageExecutionResult)
    assert result.state is expected_state
    if entries:
        assert result.attempted == 1
    if expected_state in {StageExecutionState.BLOCKED, StageExecutionState.FAILED}:
        assert result.recovery_action


async def _run_periodic_with_stage_results(monkeypatch, reviewer_result, partner_result):
    import pipeline_runner

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda *_args, **_kwargs: {
            "agent_config": {
                "scouts_enabled": False,
                "reviewers_enabled": True,
                "partners_enabled": True,
            }
        },
    )
    storage = SimpleNamespace(
        count_unreviewed=lambda: reviewer_result.attempted,
        count_undecided=lambda: partner_result.attempted,
    )
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda _uid: storage)

    class Scout:
        scouts = []

        def close(self):
            return None

    class Reviewer:
        last_cycle_stats = {}

        async def run_cycle(self, **_kwargs):
            return reviewer_result

        def close(self):
            return None

    class Partner:
        last_cycle_escalations = 0

        async def run_cycle(self, **_kwargs):
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
    monkeypatch.setattr(pipeline_runner, "_count_startups_sync", lambda _uid: 0)
    monkeypatch.setattr(pipeline_runner, "_notify_startups_changed", lambda *_a: None)

    class Portfolio:
        async def run_cycle(self):
            return None

    class Meta:
        async def run_cycle(self):
            return None

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
