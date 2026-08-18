from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolated_admin_security_state(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    api._admin_login_attempts.clear()
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())


def test_admin_token_round_trip(monkeypatch):
    from admin_auth import issue_admin_token, verify_admin_token

    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)

    token = issue_admin_token(now=now)

    claims = verify_admin_token(token, now=now)
    assert claims["scope"] == "admin"


def test_admin_token_rejects_wrong_secret(monkeypatch):
    from admin_auth import issue_admin_token, verify_admin_token

    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    token = issue_admin_token(now=now)

    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "different-secret-with-at-least-32-bytes")

    with pytest.raises(ValueError, match="invalid admin token"):
        verify_admin_token(token, now=now)


def test_admin_token_rejects_expired_token(monkeypatch):
    from admin_auth import issue_admin_token, verify_admin_token

    issued_at = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    monkeypatch.setenv("ADMIN_TOKEN_TTL_MINUTES", "5")

    token = issue_admin_token(now=issued_at)

    with pytest.raises(ValueError, match="expired admin token"):
        verify_admin_token(token, now=issued_at + timedelta(minutes=6))


def test_validate_admin_secret_uses_constant_time_compare(monkeypatch):
    from admin_auth import validate_admin_secret

    monkeypatch.setenv("ADMIN_DASHBOARD_SECRET", "correct horse battery staple")

    assert validate_admin_secret("correct horse battery staple") is True
    assert validate_admin_secret("wrong") is False
    assert validate_admin_secret("") is False


def test_admin_login_route_is_public_and_returns_token(monkeypatch):
    from api import app

    monkeypatch.setenv("ADMIN_DASHBOARD_SECRET", "correct horse battery staple")
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")

    client = TestClient(app)
    response = client.post("/api/admin/login", json={"secret": "correct horse battery staple"})

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expires_in_seconds"] > 0


def test_admin_login_records_success_audit_event(monkeypatch):
    import api

    events = []
    monkeypatch.setenv("ADMIN_DASHBOARD_SECRET", "correct horse battery staple")
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    monkeypatch.setattr(api, "record_admin_audit_event", lambda **kwargs: events.append(kwargs))

    client = TestClient(api.app)
    response = client.post("/api/admin/login", json={"secret": "correct horse battery staple"})

    assert response.status_code == 200
    assert events[0]["event"] == "admin_login"
    assert events[0]["success"] is True


def test_admin_login_records_failed_audit_event(monkeypatch):
    import api

    events = []
    monkeypatch.setenv("ADMIN_DASHBOARD_SECRET", "correct horse battery staple")
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    api._admin_login_attempts.clear()
    monkeypatch.setattr(api, "record_admin_audit_event", lambda **kwargs: events.append(kwargs))

    client = TestClient(api.app)
    response = client.post("/api/admin/login", json={"secret": "wrong"})

    assert response.status_code == 401
    assert events[0]["event"] == "admin_login"
    assert events[0]["success"] is False


def test_admin_overview_rejects_missing_admin_token(monkeypatch):
    from api import app

    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")

    client = TestClient(app)
    response = client.get("/api/admin/overview")

    assert response.status_code == 401


def test_admin_login_rate_limits_repeated_bad_secrets(monkeypatch):
    import api

    monkeypatch.setenv("ADMIN_DASHBOARD_SECRET", "correct horse battery staple")
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    api._admin_login_attempts.clear()

    client = TestClient(api.app)
    for _ in range(5):
        response = client.post("/api/admin/login", json={"secret": "wrong"})
        assert response.status_code == 401

    response = client.post("/api/admin/login", json={"secret": "wrong"})

    assert response.status_code == 429


def test_a_future_admin_route_that_forgets_its_own_auth_check_is_still_rejected(monkeypatch):
    """Regression (audit M7): admin auth used to be opt-in per route -- the
    middleware skipped Clerk auth for the whole /api/admin/ prefix and trusted
    each handler to call _require_admin_claims itself. Register a bare route
    under that prefix with no auth check of its own and confirm the
    middleware rejects it structurally, not because the handler remembered to."""
    import api

    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")

    @api.app.get("/api/admin/__test_unguarded_route")
    def _unguarded():
        return {"reached_handler": True}

    client = TestClient(api.app)
    response = client.get("/api/admin/__test_unguarded_route")

    assert response.status_code == 401


def test_admin_overview_uses_admin_service_with_valid_token(monkeypatch):
    import api
    from admin_auth import issue_admin_token

    events = []
    monkeypatch.setenv("ADMIN_TOKEN_SECRET", "test-token-secret-with-at-least-32-bytes")
    monkeypatch.setattr(api, "record_admin_audit_event", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr(
        api,
        "build_admin_overview",
        lambda loop_status_by_user: {
            "generated_at": "2026-04-26T12:00:00+00:00",
            "totals": {
                "users": 1,
                "active_sessions": 0,
                "users_with_agents_enabled": 0,
                "startups": 0,
                "pipeline_runs_24h": 0,
            },
            "users": [{"user_id": "user_a"}],
        },
    )

    client = TestClient(api.app)
    response = client.get(
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {issue_admin_token()}"},
    )

    assert response.status_code == 200
    assert response.json()["users"] == [{"user_id": "user_a"}]
    assert events[0]["event"] == "admin_overview"
    assert events[0]["success"] is True
