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
