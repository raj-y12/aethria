"""Operator-supplied additional context rides the lookup queue to the scout."""
import asyncio

from fastapi.testclient import TestClient


def _client(monkeypatch):
    import api
    from security.rate_limiter import InMemorySecurityStore

    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore()
    )
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    monkeypatch.setattr(api, "_lookup_queue", asyncio.Queue())
    return TestClient(api.app), api


def test_lookup_queues_additional_context(monkeypatch):
    client, api = _client(monkeypatch)
    res = client.post(
        "/api/startups/lookup",
        json={
            "lookup_input": "Codeliance",
            "lookup_id": "lookup-ctx-0001",
            "additional_context": "  Signed 3 enterprise pilots in Q2; team of 8, ex-Wix.  ",
        },
        headers={"Authorization": "Bearer t"},
    )
    assert res.status_code == 202
    job = api._lookup_queue.get_nowait()
    assert job["company_name"] == "Codeliance"
    assert job["additional_context"] == "Signed 3 enterprise pilots in Q2; team of 8, ex-Wix."


def test_lookup_additional_context_optional_and_bounded(monkeypatch):
    client, api = _client(monkeypatch)
    # Absent → None in the job.
    res = client.post(
        "/api/startups/lookup",
        json={"lookup_input": "Codeliance", "lookup_id": "lookup-ctx-0002"},
        headers={"Authorization": "Bearer t"},
    )
    assert res.status_code == 202
    assert api._lookup_queue.get_nowait()["additional_context"] is None

    # Over the cap → 422, nothing queued.
    res = client.post(
        "/api/startups/lookup",
        json={
            "lookup_input": "Codeliance",
            "lookup_id": "lookup-ctx-0003",
            "additional_context": "x" * 2001,
        },
        headers={"Authorization": "Bearer t"},
    )
    assert res.status_code == 422
    assert api._lookup_queue.empty()
