from types import SimpleNamespace

import pytest

from api import agents_status


@pytest.mark.asyncio
async def test_lookup_status_does_not_require_thesis(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("api._agent_queue", SimpleNamespace(qsize=lambda: 0))
    monkeypatch.setattr("api._lookup_queue", SimpleNamespace(qsize=lambda: 0))

    class DurableRepository:
        async def queue_depths(self):
            return {}

    monkeypatch.setattr("api._durable_job_repository", DurableRepository())
    monkeypatch.setattr("api.load_settings", lambda user_id: {"agent_config": {}})
    monkeypatch.setattr("api.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr("api.get_active_thesis", lambda client, user_id: None)

    result = await agents_status(SimpleNamespace(state=SimpleNamespace(user_id="user_123")))

    assert result["thesis_ready"] is False
    assert result["agents_will_run"] is False
    assert result["lookup_will_run"] is True
