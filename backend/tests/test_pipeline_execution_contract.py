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
