from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from authority.models import RolloutMode, RolloutRecord
from authority.service import AuthorityService
from security.rate_limiter import InMemorySecurityStore


class _AuthorityRepository:
    def __init__(self, mode: RolloutMode, *, kill_switch: bool = False):
        self.rollout = RolloutRecord(
            user_id="user-a", mode=mode, version=1, kill_switch=kill_switch
        )

    async def get_rollout(self, *, user_id):
        assert user_id == "user-a"
        return self.rollout


class _DecisionRepository:
    def __init__(self):
        self.ruling_calls = []

    async def create_ruling(self, ruling, *, actor_id):
        self.ruling_calls.append({"ruling": ruling, "actor_id": actor_id})
        return {"ruling_id": "ruling-1", "opportunity_id": ruling.opportunity_id}


def _client(monkeypatch, *, mode: RolloutMode, repository: _DecisionRepository):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda _token: "user-a")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.decision_repository = repository
    api.app.state.authority_service = AuthorityService(_AuthorityRepository(mode))
    return TestClient(api.app)


def _body():
    return {"decision": "pass", "rationale": "The market is outside our mandate."}


def test_human_ruling_uses_authority_guard_and_attaches_legacy_metadata(monkeypatch):
    repository = _DecisionRepository()
    response = _client(
        monkeypatch, mode=RolloutMode.SHADOW, repository=repository
    ).post(
        "/api/opportunities/opportunity-1/rulings",
        headers={"Authorization": "Bearer clerk-token"},
        json=_body(),
    )

    assert response.status_code == 200
    assert repository.ruling_calls[0]["actor_id"] == "user-a"
    assert response.json()["authority"]["mode"] == "shadow"
    assert response.json()["authority"]["canonical_writes_allowed"] is True


def test_human_ruling_is_blocked_before_mutation_in_canonical_read(monkeypatch):
    repository = _DecisionRepository()
    response = _client(
        monkeypatch, mode=RolloutMode.CANONICAL_READ, repository=repository
    ).post(
        "/api/opportunities/opportunity-1/rulings",
        headers={"Authorization": "Bearer clerk-token"},
        json=_body(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"
    assert repository.ruling_calls == []


class _ActionRepository(_DecisionRepository):
    async def create_action(self, **_kwargs):
        raise AssertionError("authority fence must run before action creation")

    async def approve_action(self, **_kwargs):
        raise AssertionError("authority fence must run before action approval")


@pytest.mark.parametrize(
    "kill_switch",
    [False, True],
)
def test_action_create_fails_before_repository_on_canonical_read_or_kill_switch(
    monkeypatch, kill_switch
):
    import api

    repository = _ActionRepository()
    client = _client(monkeypatch, mode=RolloutMode.CANONICAL_READ, repository=repository)
    if kill_switch:
        api.app.state.authority_service = AuthorityService(
            _AuthorityRepository(RolloutMode.LEGACY, kill_switch=True)
        )

    response = client.post(
        "/api/opportunities/opportunity-1/actions",
        headers={"Authorization": "Bearer clerk-token"},
        json={"action_type": "schedule_monitor_review"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"


@pytest.mark.parametrize(
    "kill_switch",
    [False, True],
)
def test_action_approve_fails_before_repository_on_canonical_read_or_kill_switch(
    monkeypatch, kill_switch
):
    import api

    repository = _ActionRepository()
    client = _client(monkeypatch, mode=RolloutMode.CANONICAL_READ, repository=repository)
    if kill_switch:
        api.app.state.authority_service = AuthorityService(
            _AuthorityRepository(RolloutMode.LEGACY, kill_switch=True)
        )

    response = client.post(
        "/api/actions/workflow-action-1/approve",
        headers={"Authorization": "Bearer clerk-token"},
        json={},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"
