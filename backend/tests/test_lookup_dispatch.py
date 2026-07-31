from api import _parse_lookup_input, _resolve_status_for
from resolver.company_resolver import CompanyCandidate, CompanyResolution


def test_parse_lookup_input_strips_common_command_prefix():
    parsed = _parse_lookup_input("find Perplexity AI")

    assert parsed["company_name"] == "Perplexity AI"
    assert parsed["lookup_query"] == "find Perplexity AI"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_strips_generic_trailing_qualifier():
    parsed = _parse_lookup_input("Perplexity AI company")

    assert parsed["company_name"] == "Perplexity AI"
    assert parsed["lookup_query"] == "Perplexity AI company"


def test_parse_lookup_input_keeps_the_browser_company_brand():
    parsed = _parse_lookup_input("The Browser Company")

    assert parsed["company_name"] == "The Browser Company"


def test_parse_lookup_input_keeps_embedded_website_disambiguation():
    parsed = _parse_lookup_input("Aethria aethria.ai")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.ai"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_normalizes_command_prefix_before_embedded_website():
    parsed = _parse_lookup_input("look up Aethria https://aethria.co")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.co"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_command_plus_only_website_uses_domain_label():
    parsed = _parse_lookup_input("find https://aethria.co")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.co"
    assert parsed["lookup_input_type"] == "website"


def _res(status, candidates):
    return CompanyResolution(
        query="x", canonical_name="x", resolution_status=status, candidates=candidates
    )


def test_resolve_status_ambiguous_when_two_strong_candidates():
    res = _res(
        "NEEDS_REVIEW",
        [
            CompanyCandidate(name="lyra", website="https://lyra.ie", confidence=0.9),
            CompanyCandidate(name="lyra", website="https://lyra.com", confidence=0.85),
        ],
    )
    assert _resolve_status_for(res, website_hint=None) == "ambiguous"


def test_resolve_status_resolved_with_single_candidate():
    res = _res("FOUND", [CompanyCandidate(name="acme", website="https://acme.com", confidence=0.9)])
    assert _resolve_status_for(res, website_hint=None) == "resolved"


def test_resolve_status_resolved_when_website_hint_given():
    res = _res(
        "NEEDS_REVIEW",
        [
            CompanyCandidate(name="lyra", website="https://lyra.ie", confidence=0.9),
            CompanyCandidate(name="lyra", website="https://lyra.com", confidence=0.85),
        ],
    )
    assert _resolve_status_for(res, website_hint="lyra.ie") == "resolved"


def test_resolve_status_not_found_when_no_candidates():
    res = _res("NOT_FOUND", [])
    assert _resolve_status_for(res, website_hint=None) == "not_found"


def _resolve_test_client(monkeypatch, sources):
    """Wire a TestClient with mocked auth, an isolated rate-limit store, and
    a stubbed retrieval provider returning the given sources."""
    from fastapi.testclient import TestClient
    import api
    import resolver.company_resolver as cr
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore()
    )
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(
        cr, "retrieve_source_pack_merged", lambda **kw: {"provider": "exa", "sources": sources}
    )
    return TestClient(api.app)


def test_resolve_endpoint_returns_ambiguous_with_candidates(monkeypatch):
    sources = [
        {"title": "Lyra IE", "url": "https://lyra.ie", "snippet": "Dublin payments startup for SMEs."},
        {"title": "Lyra US", "url": "https://lyra.com", "snippet": "US healthcare analytics platform."},
    ]
    client = _resolve_test_client(monkeypatch, sources)
    res = client.post(
        "/api/startups/lookup/resolve",
        json={"lookup_input": "Lyra"},
        headers={"Authorization": "Bearer t"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ambiguous"
    domains = {c["website"] for c in body["candidates"]}
    assert {"https://lyra.ie", "https://lyra.com"} <= domains


def test_resolved_lookup_token_reuses_server_side_resolution(monkeypatch):
    import api

    sources = [
        {
            "title": "Acme",
            "url": "https://acme.example",
            "snippet": "Acme builds warehouse robots.",
        }
    ]
    client = _resolve_test_client(monkeypatch, sources)

    class CapturingQueue:
        def __init__(self):
            self.jobs = []

        async def put(self, job):
            self.jobs.append(job)

    queue = CapturingQueue()
    monkeypatch.setattr(api, "_lookup_queue", queue)

    resolved = client.post(
        "/api/startups/lookup/resolve",
        json={"lookup_input": "Acme"},
        headers={"Authorization": "Bearer t"},
    )
    assert resolved.status_code == 200
    token = resolved.json().get("resolution_token")
    assert token

    queued = client.post(
        "/api/startups/lookup",
        json={
            "lookup_input": "Acme https://acme.example",
            "lookup_id": "lookup-acme-123",
            "resolution_token": token,
        },
        headers={"Authorization": "Bearer t"},
    )

    assert queued.status_code == 202
    assert len(queue.jobs) == 1
    resolution = queue.jobs[0]["resolution"]
    assert resolution.canonical_name == "Acme"
    assert resolution.website == "https://acme.example"


def test_resolution_token_is_tenant_scoped_and_single_use():
    import api
    from resolver.company_resolver import CompanyResolution

    resolution = CompanyResolution(
        query="Acme",
        canonical_name="Acme",
        resolution_status="FOUND",
    )
    token = api._cache_lookup_resolution("user-a", resolution)

    assert api._consume_lookup_resolution("user-b", token) is None
    assert api._consume_lookup_resolution("user-a", token) is resolution
    assert api._consume_lookup_resolution("user-a", token) is None


def test_resolve_endpoint_uses_separate_bucket_from_lookup(monkeypatch):
    """Resolve has its own 30/min bucket, so six resolves (over the lookup's
    5/min limit) all still succeed and never touch the queue's budget."""
    client = _resolve_test_client(monkeypatch, [])
    codes = [
        client.post(
            "/api/startups/lookup/resolve",
            json={"lookup_input": f"Company {i}"},
            headers={"Authorization": "Bearer t"},
        ).status_code
        for i in range(6)
    ]
    assert codes == [200] * 6
