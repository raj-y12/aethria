"""Tests for the SSE stream endpoint and its frame generator."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Endpoint: auth + connection cap (both return before streaming begins)
# ---------------------------------------------------------------------------

def test_stream_requires_auth():
    import api

    client = TestClient(api.app)
    res = client.get("/api/stream")
    assert res.status_code == 401


def test_stream_rejected_when_connection_cap_reached(monkeypatch):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_a")
    # Force the cap check to trip regardless of the configured limit.
    monkeypatch.setattr(api.event_bus, "total_subscribers", lambda: 10**9)

    client = TestClient(api.app)
    res = client.get("/api/stream", headers=_auth_headers())
    assert res.status_code == 503
    assert res.headers.get("Retry-After") == "30"


# ---------------------------------------------------------------------------
# Generator: connected -> data -> keepalive -> clean close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_source_emits_connected_then_hello_then_data_then_keepalive():
    import api

    queue: asyncio.Queue = asyncio.Queue()
    gen = api._sse_event_source(queue, keepalive_seconds=0.05)

    assert await gen.__anext__() == ": connected\n\n"

    # Immediate hello nudge so the client refetches the moment it connects,
    # reconciling any write that landed before this subscription.
    hello = await gen.__anext__()
    assert json.loads(hello[len("data: "):].strip()) == {
        "type": "startups_changed",
        "reason": "stream_connected",
    }

    payload = {"type": "startups_changed", "reason": "scout"}
    await queue.put(payload)
    frame = await gen.__anext__()
    assert frame == f"data: {json.dumps(payload)}\n\n"

    # Idle longer than keepalive_seconds -> keepalive comment.
    assert await gen.__anext__() == ": keepalive\n\n"

    await gen.aclose()


@pytest.mark.asyncio
async def test_event_source_runs_on_close_when_generator_closes():
    import api

    closed = []
    gen = api._sse_event_source(
        asyncio.Queue(),
        keepalive_seconds=0.05,
        on_close=lambda: closed.append(True),
    )
    assert await gen.__anext__() == ": connected\n\n"
    await gen.aclose()
    assert closed == [True]


def _http_scope(path: str, headers: dict):
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }


@pytest.mark.asyncio
async def test_stream_streams_through_middleware_without_buffering(monkeypatch):
    """Drive the real ASGI app (CORS + auth middleware + route) directly.

    Load-bearing check: if Starlette's BaseHTTPMiddleware (our @app.middleware
    auth) buffered the streaming response, `http.response.start` would never be
    sent until the infinite generator finished, and the waits below would time
    out. (We drive ASGI by hand rather than via httpx because httpx's in-process
    ASGITransport buffers streaming responses — a test artifact, not the server.)
    """
    import api
    import event_bus

    event_bus._subscribers.clear()
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user_asgi")

    sent: list = []
    started = asyncio.Event()
    got_connected = asyncio.Event()
    got_data = asyncio.Event()

    async def receive():
        await asyncio.sleep(3600)  # client stays connected until we cancel
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.start":
            started.set()
        elif message["type"] == "http.response.body":
            body = message.get("body") or b""
            if b": connected" in body:
                got_connected.set()
            if b"startups_changed" in body:
                got_data.set()

    task = asyncio.create_task(api.app(_http_scope("/api/stream", _auth_headers()), receive, send))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.wait_for(got_connected.wait(), timeout=5)

        start = next(m for m in sent if m["type"] == "http.response.start")
        assert start["status"] == 200
        header_map = {k.lower(): v for k, v in start["headers"]}
        assert header_map.get(b"content-type", b"").startswith(b"text/event-stream")

        # The endpoint subscribed us; a published event is pushed down the stream.
        assert event_bus.subscriber_count("user_asgi") == 1
        event_bus.publish("user_asgi", {"type": "startups_changed", "reason": "scout"})
        await asyncio.wait_for(got_data.wait(), timeout=5)
    finally:
        task.cancel()
        try:
            await task
        except BaseException:
            pass
        event_bus._subscribers.clear()

    # Generator's finally ran on cancel -> subscriber cleaned up.
    assert event_bus.subscriber_count("user_asgi") == 0


@pytest.mark.asyncio
async def test_event_source_unsubscribes_via_on_close_integration():
    """End-to-end: subscribe through the bus, deliver an event, then close."""
    import api
    import event_bus

    event_bus._subscribers.clear()
    try:
        queue = event_bus.subscribe("user_a")
        gen = api._sse_event_source(
            queue,
            keepalive_seconds=0.05,
            on_close=lambda: event_bus.unsubscribe("user_a", queue),
        )
        assert await gen.__anext__() == ": connected\n\n"

        # The hello nudge is emitted on connect, before any published event.
        hello = await gen.__anext__()
        assert json.loads(hello[len("data: "):].strip()) == {
            "type": "startups_changed",
            "reason": "stream_connected",
        }

        event_bus.publish("user_a", {"type": "startups_changed", "reason": "partner"})
        frame = await gen.__anext__()
        assert json.loads(frame[len("data: "):].strip()) == {
            "type": "startups_changed",
            "reason": "partner",
        }

        await gen.aclose()
        assert event_bus.subscriber_count("user_a") == 0
    finally:
        event_bus._subscribers.clear()
