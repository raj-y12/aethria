"""Model and dependency blocks are actionable API results, never opaque 500s."""
from unittest.mock import AsyncMock

import pytest

from authority.models import RolloutMode
from investment_analysis.model_gateway import AnalysisBlocked
from tests.evaluation_v2.test_evaluation_endpoints import _client, _EvaluationRepository


def test_read_reports_dependency_staleness_with_verified_tenant(monkeypatch):
    repository = _EvaluationRepository()
    repository.inspect_dependencies = AsyncMock(return_value={"state": "stale", "reasons": ["thesis_changed"],
        "message": "Your thesis changed. Refresh this review."})
    response = _client(monkeypatch, mode=RolloutMode.LEGACY, repository=repository).get(
        "/api/opportunities/opportunity-1/evaluation", headers={"Authorization": "Bearer clerk-token"})
    assert response.status_code == 200
    assert response.json()["dependencies"]["state"] == "stale"
    assert repository.inspect_dependencies.await_args.kwargs["user_id"] == "user-a"


@pytest.mark.parametrize("code,status", [
    ("analysis_dependencies_changed", 409),
    ("analysis_model_unconfigured", 503),
    ("analysis_budget_blocked", 503),
])
def test_evaluation_returns_named_analysis_block(monkeypatch, code, status):
    repository = _EvaluationRepository()
    repository.evaluate = AsyncMock(side_effect=AnalysisBlocked(code, "Analysis cannot complete yet."))
    response = _client(monkeypatch, mode=RolloutMode.LEGACY, repository=repository).post(
        "/api/opportunities/opportunity-1/evaluate",
        headers={"Authorization": "Bearer clerk-token"},
    )
    assert response.status_code == status
    assert response.json()["detail"] == {"code": code, "detail": "Analysis cannot complete yet."}


def test_partner_refresh_scope_is_explicit_and_tenant_bound(monkeypatch):
    repository = _EvaluationRepository()
    response = _client(monkeypatch, mode=RolloutMode.LEGACY, repository=repository).post(
        "/api/opportunities/opportunity-1/evaluate?scope=partner",
        headers={"Authorization": "Bearer clerk-token"},
    )
    assert response.status_code == 200
    assert repository.evaluate_calls[0]["review_mode"] == "partner_only"
    assert repository.evaluate_calls[0]["user_id"] == "user-a"
    assert repository.evaluate_calls[0]["trigger_type"] == "operator_partner_refresh"


def test_manual_lookup_returns_named_model_block(monkeypatch):
    import api
    from opportunity_pipeline import OpportunityPipeline

    client = _client(monkeypatch, mode=RolloutMode.LEGACY, repository=_EvaluationRepository())
    pipeline = object.__new__(OpportunityPipeline)
    pipeline.process = AsyncMock(side_effect=AnalysisBlocked("analysis_budget_blocked", "Budget unavailable."))
    monkeypatch.setattr(api.app.state, "opportunity_pipeline", pipeline, raising=False)
    response = client.post("/api/opportunities/manual-lookup", json={"company_name": "Synthetic"},
                           headers={"Authorization": "Bearer clerk-token"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "analysis_budget_blocked"
