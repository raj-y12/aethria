"""Regression coverage: POST /api/startups/{startup_id}/triage-override --
the manual "review it anyway" / "decide it anyway" action for the triage
funnel gates (confidence_threshold / decision_threshold) added 2026-08-18.
"""

from fastapi.testclient import TestClient


def _client(monkeypatch):
    import api
    import routers.deps as deps
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(deps, "_security_store", InMemorySecurityStore())
    monkeypatch.setattr(deps, "_security_repository", None)
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api.app.state, "durable_job_pool", None, raising=False)
    return TestClient(api.app)


def test_invalid_stage_is_rejected(monkeypatch):
    client = _client(monkeypatch)

    res = client.post(
        "/api/startups/s-1/triage-override",
        json={"stage": "bogus"},
        headers={"Authorization": "Bearer t"},
    )

    assert res.status_code == 400


def test_invalid_startup_id_is_rejected(monkeypatch):
    client = _client(monkeypatch)

    res = client.post(
        "/api/startups/not a valid id!!/triage-override",
        json={"stage": "review"},
        headers={"Authorization": "Bearer t"},
    )

    assert res.status_code == 422


def test_is_rate_limited_after_ten_calls_per_minute(monkeypatch):
    client = _client(monkeypatch)

    statuses = []
    for _ in range(11):
        res = client.post(
            "/api/startups/s-1/triage-override",
            json={"stage": "review"},
            headers={"Authorization": "Bearer t"},
        )
        statuses.append(res.status_code)

    # First 10 calls proceed past the rate-limit gate (whatever happens after --
    # 503 because durable_job_pool is None here -- isn't what this test asserts).
    assert 429 not in statuses[:10]
    assert statuses[10] == 429
