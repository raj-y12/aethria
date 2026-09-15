from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from authority.models import RolloutMode, RolloutRecord
from authority.service import AuthorityService
from security.rate_limiter import InMemorySecurityStore


def test_analyst_projection_retains_explanation_without_audit_payload():
    from routers.evaluations import analyst_evaluation
    from copy import deepcopy
    import json
    record = {"evaluation": {"evaluation_id": "ev", "status": "completed", "claim_snapshot": ["raw" * 2000],
        "judgment_audit": {"lineage": "internal"}, "policy_hash": "internal"},
        "criteria": [{"criterion": "market", "score": 6, "reasoning": "Limited evidence",
            "supporting_claim_ids": ["claim"], "deterministic_adjustments": {
                "assessment_validation": {"proposed_score": 8, "validated_score": 6, "cap_reason": "Weak support"},
                "raw_snapshot": "raw" * 2000}}],
        "recommendation": {"recommended_state": "insufficient_evidence", "decision_drivers": ["Verify demand"]},
        "provenance": {"recommendation_origin": "PARTNER_ANALYSIS", "evidence_links": ["raw" * 2000]}}
    original = deepcopy(record)
    result = analyst_evaluation(record)
    assert result["criteria"][0]["score"] == 6
    assert result["criteria"][0]["deterministic_adjustments"]["assessment_validation"]["cap_reason"] == "Weak support"
    assert result["recommendation"]["decision_drivers"] == ["Verify demand"]
    assert "policy_hash" not in result["evaluation"]
    assert len(json.dumps(result)) < len(json.dumps(record)) / 10
    assert record == original


class _AuthorityRepository:
    def __init__(self, mode: RolloutMode):
        self.rollout = RolloutRecord(user_id="user-a", mode=mode, version=1)

    async def get_rollout(self, *, user_id):
        assert user_id == "user-a"
        return self.rollout


class _EvaluationRepository:
    def __init__(self):
        self.evaluate_calls = []

    async def evaluate(self, **kwargs):
        self.evaluate_calls.append(kwargs)

    async def get_current(self, *, user_id, opportunity_id):
        assert user_id == "user-a"
        return {"evaluation": {"opportunity_id": opportunity_id}, "criteria": [], "recommendation": None}


def _client(monkeypatch, *, mode: RolloutMode, repository: _EvaluationRepository):
    import api
    import routers.evaluations as evaluations

    monkeypatch.setattr(api, "verify_clerk_token", lambda _token: "user-a")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )

    async def prerequisites(**_kwargs):
        return SimpleNamespace(policy={"policy": "v1"}, thesis_version_id="thesis-v1")

    monkeypatch.setattr(evaluations, "load_evaluation_prerequisites", prerequisites)
    api.app.state.evaluation_repository = repository
    api.app.state.authority_service = AuthorityService(_AuthorityRepository(mode))
    return TestClient(api.app)


def test_evaluation_creation_is_guarded_and_has_additive_legacy_metadata(monkeypatch):
    repository = _EvaluationRepository()
    response = _client(
        monkeypatch, mode=RolloutMode.LEGACY, repository=repository
    ).post(
        "/api/opportunities/opportunity-1/evaluate",
        headers={"Authorization": "Bearer clerk-token"},
    )

    assert response.status_code == 200
    assert repository.evaluate_calls[0]["user_id"] == "user-a"
    assert response.json()["authority"]["mode"] == "legacy"
    assert response.json()["authority"]["canonical_writes_allowed"] is False


def test_evaluation_creation_fails_closed_before_repository_write_in_canonical_read(monkeypatch):
    repository = _EvaluationRepository()
    response = _client(
        monkeypatch, mode=RolloutMode.CANONICAL_READ, repository=repository
    ).post(
        "/api/opportunities/opportunity-1/evaluate",
        headers={"Authorization": "Bearer clerk-token"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"
    assert repository.evaluate_calls == []
