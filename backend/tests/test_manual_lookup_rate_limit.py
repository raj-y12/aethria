"""Regression coverage (audit HIGH-H9): POST /api/opportunities/manual-lookup
triggers a canonical evaluate() call (an LLM-driven pipeline stage) but had
no rate limit at all, unlike the legacy /api/lookup endpoint. An
authenticated user could loop it with distinct company names for unbounded
LLM cost. It now shares the same LOOKUP_MINUTE_POLICY/LOOKUP_DAY_POLICY."""

from fastapi.testclient import TestClient


def _client(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore()
    )
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    return TestClient(api.app)


def test_manual_lookup_is_rate_limited_after_five_calls_per_minute(monkeypatch):
    client = _client(monkeypatch)

    statuses = []
    for i in range(6):
        res = client.post(
            "/api/opportunities/manual-lookup",
            json={"company_name": f"Acme {i}"},
            headers={"Authorization": "Bearer t"},
        )
        statuses.append(res.status_code)

    # First 5 calls proceed past the rate-limit gate (they then 503 because
    # no opportunity_pipeline is configured in this test's app state -- that
    # proves the gate runs before the pipeline check, not that it succeeds).
    assert statuses[:5] == [503] * 5
    # The 6th call within the same minute window is rejected by the gate itself.
    assert statuses[5] == 429
