"""Exercise the real named-lookup orchestration with frozen external boundaries."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import pipeline_runner as runner
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "budget", "lifecycle", "model"])
async def test_lookup_delegates_once_to_shared_core_and_stops_on_failure(monkeypatch, failure):
    events = []
    startup = SimpleNamespace(
        scout_info=SimpleNamespace(model_dump=lambda **k: {}, lookup_website="https://acme.example"),
        agent_trace={}, review_info=None,
    )
    scout = SimpleNamespace(run_named_lookup=AsyncMock(return_value="startup-1"),
                            last_lookup_startup=startup, last_lookup_outcome=None)
    # Stop after the core so this test isolates retrieval/analysis ordering.
    reviewer = SimpleNamespace(run_startup=AsyncMock(return_value=False), model="mock", founder_persister=None)
    engines = SimpleNamespace(scout_engine=scout, reviewer_engine=reviewer,
                              partner_engine=SimpleNamespace(), cost_controller=None)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic")
    monkeypatch.setattr(runner, "_load_settings_for_repository", AsyncMock(return_value={}))
    monkeypatch.setattr(runner, "StartupRepository", lambda pool: SimpleNamespace(load_snapshot=AsyncMock(return_value=None)))
    monkeypatch.setattr(runner, "StartupIdAliasRepository", lambda pool: SimpleNamespace(list_aliases_for_validation=AsyncMock(return_value=[])))
    monkeypatch.setattr(runner, "StartupReadStorageAdapter", lambda *a: SimpleNamespace())
    monkeypatch.setattr(runner, "_build_pipeline_engines", lambda **k: engines)
    monkeypatch.setattr(runner, "_initialize_deal_memory", AsyncMock())
    monkeypatch.setattr(runner, "_close_pipeline_engines", lambda *a: None)
    monkeypatch.setattr(runner, "_mark_lookup_pipeline_failed", AsyncMock())
    monkeypatch.setattr(runner, "_admit_named_lookup_before_review", AsyncMock(return_value=SimpleNamespace(
        company_id="company-1", opportunity_id="opportunity-1", observation_id="observation-1", blocks_evaluation=False,
    )))
    evidence = SimpleNamespace(list_current_claim_types=AsyncMock(return_value=set()), create_plan=AsyncMock(return_value=object()))
    monkeypatch.setattr(runner, "EvidenceRepository", lambda pool: evidence)

    async def evaluate(**kwargs):
        events.append("analyze")
        if failure == "budget":
            from investment_analysis.model_gateway import AnalysisBlocked
            raise AnalysisBlocked("analysis_budget_blocked", "Synthetic exhausted budget")
        if failure == "lifecycle":
            raise runner.EvaluationLifecycleError("Synthetic concurrent completion")
        if failure == "model":
            raise ValueError("Synthetic malformed model output")
        return {"evaluation_id": "evaluation-1", "criteria": [], "recommendation": {"state": "monitor"}}

    monkeypatch.setattr(runner, "InvestmentAnalysisRepository", lambda *a, **k: SimpleNamespace(evaluate=evaluate))
    prerequisites = SimpleNamespace(require_tenant=lambda *a, **k: None, thesis_context={},
                                    thesis_version_id="thesis-1", policy=_policy())
    result = await runner._run_on_demand_lookup_inner(
        "fund-a", "Acme", evaluation_prerequisites=prerequisites,
        fund_intelligence_repository=SimpleNamespace(pool=object()),
    )
    assert events == ["analyze"]
    if failure:
        reviewer.run_startup.assert_not_called()
        assert result.code == {"budget": "analysis_budget_blocked", "lifecycle": "analysis_dependencies_changed",
                               "model": "investment_analysis_failed"}[failure]
