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
            "proposal": {"status": "edited_and_accepted"},
            "policy_version": {"status": "draft"},
            "production_policy_changed": False,
        }

    async def preview_impact(self, **kwargs):
        self.calls.append(("preview", kwargs))
        return {"affected_opportunity_count": 0}

    async def get_proposal(self, **kwargs):
        self.calls.append(("detail", kwargs))
        return {
            "proposal": {
                "proposed_policy_patch": {
                    "target": "review_guidance",
                    "mode": "proposal",
                }
            },
            "signals": [],
            "impact_previews": [],
            "policy_versions": [],
        }

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
        return {
            "governed_policy_version_id": kwargs["governed_policy_version_id"],
            "policy_hash": "hash-1",
            "status": "published",
            "published_by": kwargs["actor_id"],
        }


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
    import routers.fund_intelligence as routes

    repository = _Repository()
    monkeypatch.setattr(
        routes,
        "load_settings",
        lambda *args, **kwargs: {
            "fund_config": {
                "publishedPolicyHash": "old-hash",
                "scoringWeights": [{"key": "market", "weight": 20}],
            }
        },
    )
    monkeypatch.setattr(
        routes,
        "compile_policy_from_fund_config",
        lambda config, require_publish_ready=True: {"policy_hash": "new-hash"},
    )
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/proposals/proposal-1/review",
        headers={"Authorization": "Bearer t"},
        json={
            "action": "edit_and_accept",
            "rationale": "Repeated attributable pattern.",
            "edited_policy_patch": {
                "scoringWeights": [{"key": "market", "weight": 30}]
            },
        },
    )
    assert response.status_code == 200
    review_call = next(call for call in repository.calls if call[0] == "review")
    assert review_call[1]["user_id"] == "user-a"
    assert review_call[1]["resulting_fund_config"]["scoringWeights"][0]["weight"] == 30
    assert response.json()["policy_version"]["status"] == "draft"
    assert response.json()["production_policy_changed"] is False


def test_publish_is_a_separate_authenticated_action(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/policy-versions/version-1/publish",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    assert [call[0] for call in repository.calls] == ["published"]
    assert repository.calls[-1][1]["actor_id"] == "user-a"
    assert response.json()["legacy_projection"] == "pending"
    assert response.json()["published_policy"]["authoritative_store"] == "governed_policy_versions"


def test_preview_and_accept_are_bound_to_the_same_compiled_policy_hash(monkeypatch):
    import routers.fund_intelligence as routes

    repository = _Repository()
    monkeypatch.setattr(
        routes,
        "compile_policy_from_fund_config",
        lambda config, require_publish_ready=True: {"policy_hash": "bound-hash"},
    )
    monkeypatch.setattr(
        routes,
        "load_settings",
        lambda *args, **kwargs: {
            "fund_config": {
                "publishedPolicyHash": "old-hash",
                "scoringWeights": [{"key": "market", "weight": 20}],
            }
        },
    )
    client = _client(monkeypatch, repository)

    preview = client.post(
        "/api/fund-intelligence/proposals/proposal-1/preview",
        headers={"Authorization": "Bearer t"},
        json={
            "action": "edit_and_accept",
            "edited_policy_patch": {
                "scoringWeights": [{"key": "market", "weight": 30}]
            },
        },
    )

    assert preview.status_code == 200
    assert repository.calls[-1][1]["policy_hash"] == "bound-hash"
    assert repository.calls[-1][1]["config_hash"]


def test_descriptive_proposal_cannot_be_plain_accepted(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/proposals/proposal-1/review",
        headers={"Authorization": "Bearer t"},
        json={"action": "accept", "rationale": "Accept unchanged."},
    )

    assert response.status_code == 409
    assert "unsupported field" in str(response.json()["detail"]).lower()
    assert not any(call[0] == "review" for call in repository.calls)
