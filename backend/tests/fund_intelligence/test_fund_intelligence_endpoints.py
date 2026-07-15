from fastapi.testclient import TestClient

from security.rate_limiter import InMemorySecurityStore


class _Repository:
    def __init__(self):
        self.calls = []

    async def derive_override_patterns(self, **kwargs):
        self.calls.append(("derive", kwargs))
        return {"observations": [], "proposals": []}

    async def review_proposal(self, **kwargs):
        self.calls.append(("review", kwargs))
        return {
            "proposal": {"status": "accepted"},
            "policy_version": {"status": "draft"},
            "production_policy_changed": False,
        }

    async def get_publishable_version(self, **kwargs):
        self.calls.append(("publishable", kwargs))
        return {"status": "draft", "proposal_status": "accepted"}

    async def mark_published(self, **kwargs):
        self.calls.append(("published", kwargs))
        return {"status": "published", "published_by": kwargs["actor_id"]}


def _client(monkeypatch, repository):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user-a")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.fund_intelligence_repository = repository
    return TestClient(api.app)


def test_review_is_tenant_scoped_and_only_creates_draft(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/proposals/proposal-1/review",
        headers={"Authorization": "Bearer t"},
        json={"action": "accept", "rationale": "Repeated attributable pattern."},
    )
    assert response.status_code == 200
    assert repository.calls[0][1]["user_id"] == "user-a"
    assert response.json()["policy_version"]["status"] == "draft"
    assert response.json()["production_policy_changed"] is False


def test_publish_is_a_separate_authenticated_action(monkeypatch):
    import routers.fund_intelligence as routes

    repository = _Repository()
    monkeypatch.setattr(
        routes,
        "publish_policy",
        lambda user_id, fund_config: {
            "policy_version_id": "published-1",
            "policy_hash": "hash-1",
        },
    )
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/policy-versions/version-1/publish",
        headers={"Authorization": "Bearer t"},
        json={"fund_config": {}},
    )
    assert response.status_code == 200
    assert [call[0] for call in repository.calls] == ["publishable", "published"]
    assert repository.calls[-1][1]["actor_id"] == "user-a"
