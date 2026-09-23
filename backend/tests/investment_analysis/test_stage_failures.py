from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from investment_analysis.model_gateway import AnalysisBlocked
from investment_analysis.stages import CompletedAnalysisStage


@pytest.mark.asyncio
async def test_periodic_stage_accounts_for_block_without_retrying_or_losing_other_companies():
    load = AsyncMock(side_effect=[AnalysisBlocked("analysis_failed_this_cycle", "Retry next run"),
                                 {"evaluation": {"judgment_audit": {"investment_analysis": {"reviewer": {"complete": True}}}}}])
    refresh = AsyncMock()
    stage = CompletedAnalysisStage(stage="reviewer", user_id="tenant", model="test", settings={},
        load=load, refresh=refresh,
        storage=SimpleNamespace(get_unreviewed=lambda **kwargs: [SimpleNamespace(startup_id="blocked"), SimpleNamespace(startup_id="ready")]))
    result = await stage.run_cycle(pipeline_run_id="cycle")
    assert result.state == "failed"
    assert (result.attempted, result.succeeded, result.blocked, result.failed) == (2, 1, 1, 0)
    assert result.warnings[0]["code"] == "analysis_failed_this_cycle"
    refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("record,expected", [
    (None, False),
    ({"review_info": {"market_score": 10}, "partner_info": {"recommendation": "INVEST"}}, False),
    ({"recommendation": {"recommended_state": "advance"}, "criteria": [{"score": 10}]}, False),
    ({"evaluation": {"judgment_audit": {"investment_analysis": {"partner": {"complete": True}}}}}, True),
])
async def test_partner_callback_requires_completed_analysis_not_legacy_scores(record, expected):
    refresh = AsyncMock()
    stage = CompletedAnalysisStage(stage="partner", user_id="tenant", model="test", settings={},
        load=AsyncMock(return_value=record), refresh=refresh, storage=SimpleNamespace())
    assert await stage.run_startup("startup", force_rerun=True) is expected
    refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome,state,succeeded,blocked,failed", [
    (None, "failed", 0, 0, 1),
    (RuntimeError("read failed"), "failed", 0, 0, 1),
    (AnalysisBlocked("analysis_failed_this_cycle", "Retry next run"), "blocked", 0, 1, 0),
    ({"evaluation": {"judgment_audit": {"investment_analysis": {"partner": {"complete": True}}}}}, "completed", 1, 0, 0),
])
async def test_partner_callback_accounts_for_every_candidate(outcome, state, succeeded, blocked, failed):
    refresh = AsyncMock()
    stage = CompletedAnalysisStage(stage="partner", user_id="tenant", model="test", settings={},
        load=AsyncMock(side_effect=[outcome]), refresh=refresh,
        storage=SimpleNamespace(get_undecided=lambda **kwargs: [SimpleNamespace(startup_id="startup")]))
    result = await stage.run_cycle(pipeline_run_id="cycle")
    assert result.state == state
    assert (result.attempted, result.succeeded, result.blocked, result.failed) == (1, succeeded, blocked, failed)
    if state != "completed":
        assert result.recovery_action
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_partner_callback_skips_empty_backlog_without_loading_or_refreshing():
    load, refresh = AsyncMock(), AsyncMock()
    stage = CompletedAnalysisStage(stage="partner", user_id="tenant", model="test", settings={},
        load=load, refresh=refresh, storage=SimpleNamespace(get_undecided=lambda **kwargs: []))
    result = await stage.run_cycle()
    assert result.state == "skipped"
    load.assert_not_awaited()
    refresh.assert_not_awaited()
