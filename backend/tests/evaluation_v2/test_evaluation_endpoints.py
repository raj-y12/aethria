from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from authority.models import RolloutMode, RolloutRecord
from authority.service import AuthorityService
from security.rate_limiter import InMemorySecurityStore


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
