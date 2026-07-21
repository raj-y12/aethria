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


@pytest.mark.asyncio
async def test_cli_continuous_mode_recovers_across_skip_block_and_failure(monkeypatch):
    import asyncio
    import run_system as cli

    results = iter(
        [
            PipelineExecutionResult.skipped(
                code="pipeline_cycle_no_work", detail="No work was due."
            ),
            PipelineExecutionResult.blocked(
                code="runtime_settings_unavailable",
                detail="Settings are unavailable.",
                recovery_action="Restore settings and retry.",
            ),
            PipelineExecutionResult.stage_failure(
                stage="reviewer",
                code="reviewer_stage_failed",
                detail="Reviewer failed.",
                recovery_action="Inspect Reviewer logs and retry.",
            ),
        ]
    )
    calls = []

    async def run(*_args, **_kwargs):
        calls.append("cycle")
        try:
            return next(results)
        except StopIteration:
            raise asyncio.CancelledError

    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setenv("SCOUT_INTERVAL_SECONDS", "17")
    monkeypatch.setenv("PIPELINE_RECOVERY_INTERVAL_SECONDS", "3")
    monkeypatch.setattr(cli, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(cli.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await cli.run_system(
            "user-a",
            once=False,
            identity_repository=object(),
            fund_intelligence_repository=object(),
        )

    assert calls == ["cycle", "cycle", "cycle", "cycle"]
    assert sleeps == [17, 3, 3]
