import pytest

from pipeline_execution import PipelineExecutionResult, PipelineExecutionState


@pytest.mark.asyncio
async def test_cli_once_routes_through_typed_shared_runner(monkeypatch):
    import run_system as cli

    calls = []
    expected = PipelineExecutionResult.completed(
        code="pipeline_cycle_completed", detail="Cycle completed."
    )

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))
        return expected

    monkeypatch.setattr(cli, "run_one_pipeline_cycle", run, raising=False)

    result = await cli.run_system(
        " user-a ",
        once=True,
        identity_repository="identity-repository",
        fund_intelligence_repository="fund-repository",
    )

    assert result is expected
    assert calls == [
        (
            "user-a",
            {
                "manual_one_shot": True,
                "identity_repository": "identity-repository",
                "fund_intelligence_repository": "fund-repository",
            },
        )
    ]


@pytest.mark.asyncio
async def test_cli_returns_blocked_result_without_claiming_success(monkeypatch):
    import run_system as cli

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.blocked(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish the policy in Settings.",
        )

    monkeypatch.setattr(cli, "run_one_pipeline_cycle", run, raising=False)

    result = await cli.run_system(
        "user-a",
        once=True,
        identity_repository=object(),
        fund_intelligence_repository=object(),
    )

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "published_policy_required"


@pytest.mark.asyncio
async def test_cli_blocks_actionably_when_institutional_store_is_unavailable(monkeypatch):
    import run_system as cli

    async def create_pool():
        raise OSError("database refused connection")

    monkeypatch.setattr(cli, "create_pool", create_pool)

    result = await cli.run_system("user-a", once=True)

    assert result.state is PipelineExecutionState.BLOCKED
    assert result.code == "institutional_repository_unavailable"
    assert "retry" in result.recovery_action.lower()
