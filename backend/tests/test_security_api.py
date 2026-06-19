from types import SimpleNamespace
import asyncio

from fastapi.testclient import TestClient
import pytest


class _FakeQueue:
    def __init__(self):
        self.items = []

    async def put(self, item):
        self.items.append(item)

    def qsize(self):
        return len(self.items)


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


def test_authenticated_lookup_rate_limit_is_per_user(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    store = InMemorySecurityStore()
    users = iter(["user_a"] * 6 + ["user_b"])
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", store)
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: next(users))
    monkeypatch.setattr(api, "_lookup_queue", _FakeQueue())

    client = TestClient(api.app)
    for i in range(5):
        response = client.post(
            "/api/startups/lookup",
            json={"lookup_input": f"Acme {i}", "lookup_id": f"lookup-a-{i}"},
            headers=_auth_headers(),
        )
        assert response.status_code == 202

    denied = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme 6", "lookup_id": "lookup-a-6"},
        headers=_auth_headers(),
    )
    assert denied.status_code == 429
    assert denied.json()["detail"] == "Rate limit exceeded"
    assert denied.json()["retry_after_seconds"] > 0

    other_user = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme B", "lookup_id": "lookup-b-1"},
        headers=_auth_headers(),
    )
    assert other_user.status_code == 202


def test_duplicate_lookup_id_is_coalesced_without_second_enqueue(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    queue = _FakeQueue()
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_lookup_queue", queue)

    client = TestClient(api.app)
    first = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme", "lookup_id": "lookup-same"},
        headers=_auth_headers(),
    )
    second = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Acme", "lookup_id": "lookup-same"},
        headers=_auth_headers(),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["status"] == "already_queued"
    assert len(queue.items) == 1


def test_cancel_lookup_marks_lookup_cancelled(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_cancelled_lookup_ids", set())

    client = TestClient(api.app)
    response = client.post(
        "/api/startups/lookup/cancel",
        json={"lookup_ids": ["lookup-cancel-1", "lookup-cancel-2"]},
        headers=_auth_headers(),
    )

    assert response.status_code == 202
    assert response.json()["cancelled"] == ["lookup-cancel-1", "lookup-cancel-2"]
    assert api._is_lookup_cancelled("user_a", "lookup-cancel-1") is True
    assert api._is_lookup_cancelled("user_b", "lookup-cancel-1") is False


def test_manual_agent_trigger_when_ops_off_is_coalesced_without_second_enqueue(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    queue = _FakeQueue()
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "load_settings", lambda user_id: {"agent_config": {"scouts_enabled": False}})
    monkeypatch.setattr(api, "get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(api, "get_active_thesis", lambda client, user_id: SimpleNamespace())

    client = TestClient(api.app)
    first = client.post("/api/agents/trigger", headers=_auth_headers())
    second = client.post("/api/agents/trigger", headers=_auth_headers())

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["status"] == "already_queued"
    assert len(queue.items) == 1
    assert queue.items[0]["manual_one_shot"] is True


def test_agent_trigger_ignores_when_persistent_loop_already_running(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    class _LiveTask:
        def done(self):
            return False

    queue = _FakeQueue()
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setitem(api._per_user_loops, "user_a", _LiveTask())
    monkeypatch.setattr(api, "load_settings", lambda user_id: {"agent_config": {"scouts_enabled": True}})
    monkeypatch.setattr(api, "get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(api, "get_active_thesis", lambda client, user_id: SimpleNamespace())

    client = TestClient(api.app)
    response = client.post("/api/agents/trigger", headers=_auth_headers())

    assert response.status_code == 202
    assert response.json()["status"] == "loop_running"
    assert queue.items == []


def test_agent_trigger_starts_persistent_loop_without_queueing_when_ops_on(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    queue = _FakeQueue()
    started = []

    async def fake_ensure_user_loop(user_id):
        started.append(user_id)
        return True

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "_loops_lock", object())
    monkeypatch.setattr(api, "_ensure_user_loop", fake_ensure_user_loop)
    monkeypatch.setattr(api, "load_settings", lambda user_id: {"agent_config": {"scouts_enabled": True}})
    monkeypatch.setattr(api, "get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(api, "get_active_thesis", lambda client, user_id: SimpleNamespace())

    client = TestClient(api.app)
    response = client.post("/api/agents/trigger", headers=_auth_headers())

    assert response.status_code == 202
    assert response.json()["status"] == "loop_started"
    assert started == ["user_a"]
    assert queue.items == []


@pytest.mark.asyncio
async def test_persistent_agent_loop_runs_cycles_sequentially_and_stops_when_disabled(monkeypatch):
    import api

    states = iter([
        {"agent_config": {"scouts_enabled": True}},
        {"agent_config": {"scouts_enabled": False, "reviewers_enabled": False, "partners_enabled": False}},
    ])
    active_cycles = 0
    max_active_cycles = 0
    calls = []

    async def fake_run_one_pipeline_cycle(user_id):
        nonlocal active_cycles, max_active_cycles
        active_cycles += 1
        max_active_cycles = max(max_active_cycles, active_cycles)
        calls.append(user_id)
        await asyncio.sleep(0)
        active_cycles -= 1

    monkeypatch.setattr(api, "load_settings", lambda user_id, use_cache=False: next(states))
    monkeypatch.setattr(api, "run_one_pipeline_cycle", fake_run_one_pipeline_cycle)
    monkeypatch.setattr(api, "_update_agent_run_status", lambda user_id, status: asyncio.sleep(0))
    monkeypatch.setattr(api, "AGENT_LOOP_INTERVAL_SECONDS", 0)
    monkeypatch.setitem(api._per_user_loops, "user_loop", asyncio.current_task())

    await api._user_agent_loop("user_loop")

    assert calls == ["user_loop"]
    assert max_active_cycles == 1
    assert "user_loop" not in api._per_user_loops


def test_admin_token_includes_jti(monkeypatch):
    from admin_auth import issue_admin_token, verify_admin_token

    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")

    claims = verify_admin_token(issue_admin_token())

    assert isinstance(claims.get("jti"), str)
    assert len(claims["jti"]) >= 16


def test_admin_routes_can_be_disabled_in_production(monkeypatch):
    import api

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ADMIN_DASHBOARD_ENABLED", raising=False)

    client = TestClient(api.app)
    response = client.post("/api/admin/login", json={"secret": "anything"})

    assert response.status_code == 404


def test_admin_overview_rate_limited_by_admin_token(monkeypatch):
    import api
    from admin_auth import issue_admin_token
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("ADMIN_DASHBOARD_ENABLED", "true")
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(api, "record_admin_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(api, "build_admin_overview", lambda loop_status_by_user: {"users": []})

    token = issue_admin_token()
    client = TestClient(api.app)
    for _ in range(30):
        response = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    denied = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})

    assert denied.status_code == 429
    assert denied.json()["detail"] == "Rate limit exceeded"
