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

    async def preview_impact(self, **kwargs):
        self.calls.append(("preview", kwargs))
        return {"affected_opportunity_count": 0}

    async def get_publishable_version(self, **kwargs):
        self.calls.append(("publishable", kwargs))
        return {
            "status": "draft",
            "proposal_status": "accepted",
            "policy_patch": {"stage": "pre_seed"},
            "policy_hash": "hash-1",
        }

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
        json={
            "action": "accept",
            "rationale": "Repeated attributable pattern.",
            "resulting_fund_config": {"stage": "pre_seed"},
        },
    )
    assert response.status_code == 200
    assert repository.calls[0][1]["user_id"] == "user-a"
    assert response.json()["policy_version"]["status"] == "draft"
    assert response.json()["production_policy_changed"] is False


def test_publish_is_a_separate_authenticated_action(monkeypatch):
    import routers.fund_intelligence as routes

    repository = _Repository()
    published_configs = []

    def publish(user_id, fund_config):
        published_configs.append(fund_config)
        return {
            "policy_version_id": "published-1",
            "policy_hash": "hash-1",
        }

    monkeypatch.setattr(routes, "publish_policy", publish)
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/policy-versions/version-1/publish",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    assert [call[0] for call in repository.calls] == ["publishable", "published"]
    assert repository.calls[-1][1]["actor_id"] == "user-a"
    assert published_configs == [{"stage": "pre_seed"}]


def test_preview_and_accept_are_bound_to_the_same_compiled_policy_hash(monkeypatch):
    import routers.fund_intelligence as routes

    repository = _Repository()
    monkeypatch.setattr(
        routes,
        "compile_policy_from_fund_config",
        lambda config, require_publish_ready=True: {"policy_hash": "bound-hash"},
    )
    client = _client(monkeypatch, repository)

    preview = client.post(
        "/api/fund-intelligence/proposals/proposal-1/preview",
        headers={"Authorization": "Bearer t"},
        json={"resulting_fund_config": {"stage": "pre_seed"}},
    )

    assert preview.status_code == 200
    assert repository.calls[-1][1]["policy_hash"] == "bound-hash"
