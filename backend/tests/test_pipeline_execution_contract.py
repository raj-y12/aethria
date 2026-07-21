import pytest


def test_execution_result_contract_distinguishes_terminal_states_and_payload_ids():
    from pipeline_execution import PipelineExecutionResult, PipelineExecutionState

    completed = PipelineExecutionResult.completed(
        code="lookup_completed",
        detail="The company was evaluated.",
        startup_id="startup-1",
        projection_id="opportunity-1",
    )
    blocked = PipelineExecutionResult.blocked(
        code="openai_api_key_required",
        detail="OpenAI is not configured.",
        recovery_action="Configure OPENAI_API_KEY and retry.",
    )
    skipped = PipelineExecutionResult.skipped(
        code="agents_disabled",
        detail="No agent stage is enabled.",
    )
    failed = PipelineExecutionResult.stage_failure(
        stage="reviewer",
        code="reviewer_failed",
        detail="Reviewer did not complete.",
        recovery_action="Retry after checking reviewer logs.",
        startup_id="startup-1",
    )

    assert completed.state is PipelineExecutionState.COMPLETED
    assert blocked.state is PipelineExecutionState.BLOCKED
    assert skipped.state is PipelineExecutionState.SKIPPED
    assert failed.state is PipelineExecutionState.FAILED_STAGE
    assert completed.startup_id == "startup-1"
    assert completed.projection_id == "opportunity-1"
    assert failed.failed_stage == "reviewer"


def test_blocked_and_failed_results_require_actionable_recovery_data():
    from pipeline_execution import PipelineExecutionResult

    with pytest.raises(ValueError):
        PipelineExecutionResult(
            state="blocked",
            code="openai_api_key_required",
            detail="OpenAI is not configured.",
        )
    with pytest.raises(ValueError):
        PipelineExecutionResult(
            state="failed_stage",
            code="reviewer_failed",
            detail="Reviewer did not complete.",
            recovery_action="Retry.",
        )


def test_stage_execution_result_carries_typed_counts_and_stable_outcome():
    from pipeline_execution import StageExecutionResult, StageExecutionState

    completed = StageExecutionResult.completed(
        stage="reviewer",
        code="reviewer_completed",
        detail="Reviewer completed eligible work.",
        attempted=2,
        succeeded=2,
    )
    failed = StageExecutionResult.failed_result(
        stage="partner",
        code="partner_candidate_failures",
        detail="One Partner candidate failed.",
        recovery_action="Inspect Partner logs and retry.",
        attempted=2,
        succeeded=1,
        failed=1,
    )
    blocked = StageExecutionResult.blocked_result(
        stage="reviewer",
        code="reviewer_budget_blocked",
        detail="Reviewer budget denied eligible work.",
        recovery_action="Increase the Reviewer budget or wait for reset.",
        attempted=3,
        blocked=3,
    )
    no_work = StageExecutionResult.skipped_result(
        stage="partner",
        code="partner_no_eligible_work",
        detail="No eligible Partner work was found.",
    )

    assert completed.state is StageExecutionState.COMPLETED
    assert failed.state is StageExecutionState.FAILED
    assert blocked.state is StageExecutionState.BLOCKED
    assert no_work.state is StageExecutionState.SKIPPED
    assert failed.model_dump()["failed"] == 1
    assert blocked.model_dump()["blocked"] == 3


def test_stage_execution_result_rejects_inconsistent_counts_and_recovery():
    from pipeline_execution import StageExecutionResult

    with pytest.raises(ValueError):
        StageExecutionResult(
            stage="reviewer",
            state="completed",
            code="reviewer_completed",
            detail="Impossible clean result.",
            attempted=1,
            succeeded=0,
            failed=1,
        )
    with pytest.raises(ValueError):
        StageExecutionResult.failed_result(
            stage="partner",
            code="partner_candidate_failures",
            detail="Missing recovery.",
            recovery_action="",
            attempted=1,
            failed=1,
        )


def test_lookup_execution_status_union_covers_every_persisted_state():
    from pipeline_execution import LookupExecutionStatus

    assert {status.value for status in LookupExecutionStatus} == {
        "pending",
        "accepted",
        "completed",
        "blocked",
        "skipped",
        "failed_stage",
        "failed",
        "already_in_deal_flow",
    }


def test_scout_and_meta_payload_results_bind_payloads_to_typed_outcomes():
    from pipeline_execution import (
        MetaCycleResult,
        ScoutCycleResult,
        StageExecutionResult,
    )

    scout = ScoutCycleResult(
        outcome=StageExecutionResult.completed(
            stage="scout",
            code="scout_completed",
            detail="Scout produced one discovery.",
            attempted=1,
            succeeded=1,
        ),
        discoveries=[{"id": "startup-1", "name": "Typed Co"}],
    )
    meta = MetaCycleResult(
        outcome=StageExecutionResult.completed(
            stage="meta",
            code="meta_completed",
            detail="Meta produced an analysis report.",
            attempted=1,
            succeeded=1,
        ),
        report={"cycle_number": 4, "analysis_only": True},
    )

    assert scout.discoveries[0]["id"] == "startup-1"
    assert meta.report["analysis_only"] is True

    with pytest.raises(ValueError, match="discovery count"):
        ScoutCycleResult(
            outcome=StageExecutionResult.completed(
                stage="scout",
                code="scout_completed",
                detail="Impossible payload count.",
                attempted=1,
                succeeded=1,
            ),
            discoveries=[],
        )
    with pytest.raises(ValueError, match="report"):
        MetaCycleResult(
            outcome=StageExecutionResult.skipped_result(
                stage="meta",
                code="meta_not_due",
                detail="Meta is not due.",
            ),
            report={"cycle_number": 4},
        )
