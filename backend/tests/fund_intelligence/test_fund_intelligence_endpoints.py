from fastapi.testclient import TestClient

from security.rate_limiter import InMemorySecurityStore


class _Repository:
    def __init__(self):
        self.calls = []
        self.active_policy = None

    async def get_observations(self, **kwargs):
        self.calls.append(("observations", kwargs))
        return [{"observation_type": "recommendation_ruling_agreement"}]

    async def get_hypotheses(self, **kwargs):
        self.calls.append(("hypotheses", kwargs))
        return [{"status": "descriptive_hypothesis"}]

    async def get_replay_preview(self, **kwargs):
        self.calls.append(("replay", kwargs))
        return {
            "hypothesis_id": kwargs["hypothesis_id"],
            "replay_status": "not_replayable",
            "outcome_context_used_for_replay": False,
        }

    async def get_counterfactual_proposals(self, **kwargs):
        self.calls.append(("counterfactual_proposals", kwargs))
        return [{"proposal_status": "insufficient_basis"}]

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

    async def get_active_published_policy(self, **kwargs):
        if self.active_policy is None:
            raise LookupError("No governed policy yet")
        return self.active_policy

    async def publish_settings_policy(self, **kwargs):
        self.calls.append(("settings_publish", kwargs))
        return {
            "governed_policy_version_id": "settings-version-1",
            "policy_hash": kwargs["policy_hash"],
            "published_at": "2026-07-16T20:00:00Z",
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
    async def load_settings(*args, **kwargs):
        return {
            "fund_config": {
                "publishedPolicyHash": "old-hash",
                "scoringWeights": [{"key": "market", "weight": 20}],
            }
        }
    monkeypatch.setattr(routes, "load_settings", load_settings)
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


def test_observations_are_authenticated_and_forward_historical_filters(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).get(
        "/api/fund-intelligence/observations?sector=fintech&date_from=2026-01-01T00:00:00Z",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    call = next(call for call in repository.calls if call[0] == "observations")
    assert call[1]["user_id"] == "user-a"
    assert call[1]["sector"] == "fintech"
    assert call[1]["date_from"].isoformat() == "2026-01-01T00:00:00+00:00"
    assert response.json()["observations"][0]["observation_type"] == "recommendation_ruling_agreement"


def test_hypotheses_are_tenant_scoped_and_do_not_mutate_policy(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).get(
        "/api/fund-intelligence/hypotheses?hypothesis_family=segment_specific_behavior",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    call = next(call for call in repository.calls if call[0] == "hypotheses")
    assert call[1]["user_id"] == "user-a"
    assert call[1]["hypothesis_family"] == "segment_specific_behavior"
    assert response.json()["hypotheses"][0]["status"] == "descriptive_hypothesis"
    assert not any(call[0] in {"review", "published", "settings_publish"} for call in repository.calls)


def test_replay_preview_is_tenant_scoped_and_fail_closed(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).get(
        "/api/fund-intelligence/hypotheses/hypothesis-1/replay",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    call = next(call for call in repository.calls if call[0] == "replay")
    assert call[1] == {"user_id": "user-a", "hypothesis_id": "hypothesis-1"}
    assert response.json()["replay_status"] == "not_replayable"
    assert response.json()["outcome_context_used_for_replay"] is False


def test_counterfactual_proposals_are_tenant_scoped_and_not_published(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).get(
        "/api/fund-intelligence/counterfactual-proposals?hypothesis_family=segment_specific_behavior",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    call = next(call for call in repository.calls if call[0] == "counterfactual_proposals")
    assert call[1]["user_id"] == "user-a"
    assert call[1]["hypothesis_family"] == "segment_specific_behavior"
    assert response.json()["counterfactual_proposals"][0]["proposal_status"] == "insufficient_basis"
    assert not any(call[0] in {"review", "published", "settings_publish"} for call in repository.calls)


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
    async def load_settings(*args, **kwargs):
        return {
            "fund_config": {
                "publishedPolicyHash": "old-hash",
                "scoringWeights": [{"key": "market", "weight": 20}],
            }
        }
    monkeypatch.setattr(routes, "load_settings", load_settings)
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


def test_edit_is_applied_to_authoritative_governed_base_not_stale_legacy(monkeypatch):
    import routers.fund_intelligence as routes

    repository = _Repository()
    repository.active_policy = {
        "policy_patch": {
            "rubric": [{"id": "authoritative"}],
            "scoringWeights": [{"key": "market", "weight": 20}],
        },
        "policy_hash": "governed-hash",
    }
    monkeypatch.setattr(
        routes,
        "load_settings",
        lambda *args, **kwargs: {
            "fund_config": {"rubric": [{"id": "stale-legacy"}]}
        },
    )
    monkeypatch.setattr(
        routes,
        "compile_policy_from_fund_config",
        lambda config, require_publish_ready=True: {"policy_hash": "next-hash"},
    )

    response = _client(monkeypatch, repository).post(
        "/api/fund-intelligence/proposals/proposal-1/review",
        headers={"Authorization": "Bearer t"},
        json={
            "action": "edit_and_accept",
            "rationale": "Apply to current governed base.",
            "edited_policy_patch": {
                "scoringWeights": [{"key": "market", "weight": 30}]
            },
        },
    )

    assert response.status_code == 200
    call = next(item for item in repository.calls if item[0] == "review")
    assert call[1]["resulting_fund_config"]["rubric"] == [{"id": "authoritative"}]
    assert call[1]["resulting_fund_config"]["scoringWeights"][0]["weight"] == 30


def test_settings_publish_uses_the_governed_repository_not_legacy_store(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/settings/policy/publish",
        headers={"Authorization": "Bearer t"},
        json={"fund_config": {"scoringWeights": [{"key": "market", "weight": 30}]}},
    )

    assert response.status_code == 200
    call = next(item for item in repository.calls if item[0] == "settings_publish")
    assert call[1]["user_id"] == "user-a"
    assert call[1]["fund_config"]["scoringWeights"][0]["weight"] == 30
    assert response.json()["policy"]["policy_version_id"] == "settings-version-1"
    assert response.json()["policy"]["authoritative_store"] == "governed_policy_versions"
