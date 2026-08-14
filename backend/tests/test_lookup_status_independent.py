from types import SimpleNamespace

import pytest

from api import agents_status
from evaluation_v2.prerequisites import EvaluationPrerequisiteError


@pytest.mark.asyncio
async def test_lookup_status_does_not_advertise_runnable_without_thesis(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("api._agent_queue", SimpleNamespace(qsize=lambda: 0))
    monkeypatch.setattr("api._lookup_queue", SimpleNamespace(qsize=lambda: 0))

    class DurableRepository:
        async def tenant_queue_depths(self, *, user_id):
            assert user_id == "user_123"
            return {}

    monkeypatch.setattr("api._durable_job_repository", DurableRepository())
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr("api.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr("api.get_active_thesis", lambda client, user_id: None)

    async def thesis_required(**_kwargs):
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active fund thesis is required before evaluation.",
            recovery_action="Create and publish the fund thesis in Settings.",
        )

    monkeypatch.setattr(
        "api.load_evaluation_prerequisites", thesis_required, raising=False
    )

    result = await agents_status(SimpleNamespace(state=SimpleNamespace(user_id="user_123")))

    assert result["agents_infrastructure_ready"] is True
    assert result["lookup_infrastructure_ready"] is True
    assert result["execution_prerequisites_ready"] is False
    assert result["thesis_ready"] is False
    assert result["agents_will_run"] is False
    assert result["lookup_will_run"] is False


@pytest.mark.asyncio
async def test_status_uses_exact_published_policy_prerequisite_contract(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class DurableRepository:
        async def tenant_queue_depths(self, *, user_id):
            return {}

    governed_repository = object()
    monkeypatch.setattr("api._durable_job_repository", DurableRepository())
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr(
        "api._agents_status_reads_sync",
        lambda *_args: (True, True, "thesis-live", None, True),
    )
    monkeypatch.setattr(
        "api.app.state.fund_intelligence_repository",
        governed_repository,
        raising=False,
    )

    calls = []

    async def blocked(**kwargs):
        calls.append(kwargs)
        raise EvaluationPrerequisiteError(
            code="published_policy_required",
            detail="An active published scoring policy is required.",
            recovery_action="Publish the fund scoring policy in Settings.",
        )

    monkeypatch.setattr("api.load_evaluation_prerequisites", blocked, raising=False)

    result = await agents_status(
        SimpleNamespace(state=SimpleNamespace(user_id="user_123"))
    )

    assert calls == [
        {
            "user_id": "user_123",
            "fund_intelligence_repository": governed_repository,
        }
    ]
    assert result["thesis_ready"] is True
    assert result["published_policy_ready"] is False
    assert result["execution_prerequisites_ready"] is False
    assert result["execution_prerequisite_code"] == "published_policy_required"
    assert result["agents_will_run"] is False
    assert result["lookup_will_run"] is False


@pytest.mark.asyncio
async def test_status_advertises_execution_only_after_exact_prerequisites_load(
    monkeypatch,
):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class DurableRepository:
        async def tenant_queue_depths(self, *, user_id):
            return {}

    prerequisites = SimpleNamespace(
        thesis_version_id="thesis-live",
        policy=SimpleNamespace(policy_version_id="policy-live"),
    )
    monkeypatch.setattr("api._durable_job_repository", DurableRepository())
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr(
        "api._agents_status_reads_sync",
        lambda *_args: (True, True, "thesis-live", None, True),
    )

    async def ready(**_kwargs):
        return prerequisites

    monkeypatch.setattr(
        "api.load_evaluation_prerequisites",
        ready,
        raising=False,
    )

    result = await agents_status(
        SimpleNamespace(state=SimpleNamespace(user_id="user_123"))
    )

    assert result["execution_prerequisites_ready"] is True
    assert result["published_policy_ready"] is True
    assert result["active_policy_version_id"] == "policy-live"
    assert result["agents_will_run"] is True
    assert result["lookup_will_run"] is True


@pytest.mark.asyncio
async def test_status_accepts_provider_neutral_postgres_without_supabase(
    monkeypatch,
):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/aethria")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class DurableRepository:
        async def tenant_queue_depths(self, *, user_id):
            return {}

    prerequisites = SimpleNamespace(
        thesis_version_id="thesis-live",
        policy=SimpleNamespace(policy_version_id="policy-live"),
    )
    monkeypatch.setattr("api._durable_job_repository", DurableRepository())
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr(
        "api._agents_status_reads_sync",
        lambda *_args: (True, True, "thesis-live", None, True),
    )

    async def ready(**_kwargs):
        return prerequisites

    monkeypatch.setattr("api.load_evaluation_prerequisites", ready, raising=False)

    result = await agents_status(
        SimpleNamespace(state=SimpleNamespace(user_id="user_123"))
    )

    assert result["agents_infrastructure_ready"] is True
    assert result["lookup_infrastructure_ready"] is True
    assert result["execution_prerequisites_ready"] is True
    assert result["agents_will_run"] is True
    assert result["lookup_will_run"] is True
