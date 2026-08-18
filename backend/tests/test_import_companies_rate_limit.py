"""Regression coverage (fresh audit MEDIUM): POST /api/imports/companies
accepts up to 500 rows per call and had no rate limit at all, unlike every
other mutating endpoint (manual-lookup, admin login/overview, settings
mutation). An authenticated user could loop it for unbounded write volume
into the canonical identity store."""

from fastapi.testclient import TestClient


def _client(monkeypatch):
    import api
    import routers.deps as deps
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(deps, "_security_store", InMemorySecurityStore())
    # routers.deps._security_repository is process-global mutable state (set
    # by configure_security_repository, e.g. on a real app startup or a
    # differently-ordered test) -- reset it so this test's rate-limit check
    # goes through the in-memory fallback deterministically, regardless of
    # what any other test in the same pytest process left behind.
    monkeypatch.setattr(deps, "_security_repository", None)
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    # app.state is a mutable attribute on the singleton api.app object --
    # another test in the same pytest process may leave a real (or stub)
    # identity_repository configured, which would make this endpoint's
    # downstream behavior nondeterministic here. This test only cares about
    # the rate-limit gate, which runs before the repository is touched.
    monkeypatch.setattr(api.app.state, "identity_repository", None, raising=False)
    return TestClient(api.app)


def test_import_companies_is_rate_limited_after_five_calls_per_minute(monkeypatch):
    client = _client(monkeypatch)

    statuses = []
    for i in range(6):
        res = client.post(
            "/api/imports/companies",
            json={"import_id": f"import-{i}", "rows": [{"name": "Acme"}]},
            headers={"Authorization": "Bearer t"},
        )
        statuses.append(res.status_code)

    # First 5 calls proceed past the rate-limit gate itself (whatever happens
    # after -- 503/500/200 -- depends on app.state.identity_repository, which
    # other tests in the same process may configure; asserting on that would
    # couple this test to unrelated state). None of the first 5 is a 429.
    assert 429 not in statuses[:5]
    # The 6th call within the same minute window is rejected by the gate itself.
    assert statuses[5] == 429
