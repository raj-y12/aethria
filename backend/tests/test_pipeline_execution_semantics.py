from types import SimpleNamespace

import pytest

from evaluation_v2.prerequisites import EvaluationPrerequisiteError
from pipeline_execution import PipelineExecutionResult, PipelineExecutionState


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
