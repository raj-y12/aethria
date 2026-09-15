"""Long-running analysis cannot replace a review completed after its snapshot."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evaluation_v2.repository import EvaluationLifecycleError, EvaluationRepository
from investment_analysis.repository import InvestmentAnalysisRepository
from investment_analysis.model_gateway import AnalysisBlocked
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy, CLOCK
from tests.investment_analysis.test_authority import run_case


@pytest.mark.asyncio
@pytest.mark.parametrize("expected", [None, "older-evaluation"])
async def test_newer_completion_rejects_stale_analysis_before_writes(expected):
    analysis, _ = await run_case()

    class Connection:
        @asynccontextmanager
        async def transaction(self, **kwargs):
            yield

        async def fetchrow(self, sql, *args):
            assert args == ("tenant", "opportunity")
            assert "for update of o" in sql
            return {"current_evaluation_id": "newer-evaluation", "service_level": 1}

        async def fetch(self, *args):
            pytest.fail("Stale completion must be rejected before reading further state")

        async def execute(self, *args):
            pytest.fail("Stale completion must not write")

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()

    with pytest.raises(EvaluationLifecycleError, match="newer evaluation"):
        await EvaluationRepository(Pool()).evaluate(
            user_id="tenant", opportunity_id="opportunity", actor_id="tenant",
            trigger_type="rerun", policy=_policy(), prepared_analysis=analysis,
            analysis_at=CLOCK, expected_evaluation_id=expected,
        )


@pytest.mark.asyncio
async def test_thesis_changed_during_models_does_not_publish_stale_review(monkeypatch):
    analysis, _ = await run_case()
    policy = _policy()
    acquired = 0

    class Connection:
        @asynccontextmanager
        async def transaction(self, **kwargs):
            yield

        async def fetchrow(self, sql, *args):
            return {"company_id": "company", "canonical_name": "Synthetic", "service_level": 1}

        async def fetch(self, *args):
            return []

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            nonlocal acquired
            acquired += 1
            try:
                yield Connection()
            finally:
                acquired -= 1

    def context(version):
        return SimpleNamespace(require_tenant=lambda *a, **k: None, policy=policy,
                               thesis_version_id=version, thesis_context={}, fund_config={})

    load = AsyncMock(side_effect=[context("thesis-a"), context("thesis-b")])

    async def model_work(**kwargs):
        assert acquired == 0, "Database connections must be released during model calls"
        return analysis

    monkeypatch.setattr("investment_analysis.repository.analyze", model_work)
    monkeypatch.setattr("investment_analysis.repository.SettingsRepository.get", AsyncMock(return_value={}))
    monkeypatch.setattr(EvaluationRepository, "get_current", AsyncMock(return_value=None))
    persist = AsyncMock()
    monkeypatch.setattr(EvaluationRepository, "evaluate", persist)
    repository = InvestmentAnalysisRepository(Pool(), generate=AsyncMock(), prerequisites_loader=load,
                                             evidence_preparer=AsyncMock(return_value={"status": "frozen_fixture", "claims_created": 0}))
    with pytest.raises(AnalysisBlocked, match="changed") as blocked:
        await repository.evaluate(user_id="tenant", opportunity_id="opportunity", actor_id="tenant",
                                  trigger_type="rerun", policy=policy, thesis_version_id="thesis-a")
    assert blocked.value.code == "analysis_dependencies_changed"
    persist.assert_not_awaited()
    assert load.await_count == 2
