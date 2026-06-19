"""Tests for the opt-in Postgres LISTEN/NOTIFY backplane in event_bus.

No real Postgres: a fake asyncpg-style connection is injected via the
``connect`` hook so we can assert NOTIFY emission, inbound re-delivery, and
own-instance suppression deterministically.
"""
import asyncio
import json

import pytest
import pytest_asyncio

import event_bus


class FakeConn:
    """Minimal asyncpg-connection stand-in shared by listen + notify roles."""

    instances: list = []

    def __init__(self):
        self.listeners = {}
        self.notified = []
        self.closed = False
        FakeConn.instances.append(self)

    async def add_listener(self, channel, cb):
        self.listeners[channel] = cb

    async def remove_listener(self, channel, cb):
        self.listeners.pop(channel, None)

    async def execute(self, query, *args):
        # SELECT pg_notify($1, $2)
        if "pg_notify" in query:
            self.notified.append((args[0], args[1]))

    async def close(self):
        self.closed = True


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    event_bus._subscribers.clear()
    FakeConn.instances = []
    yield
    await event_bus.stop_backplane()
    event_bus._subscribers.clear()


async def _connect(_dsn):
    return FakeConn()


@pytest.mark.asyncio
async def test_publish_emits_notify_when_backplane_active():
    started = await event_bus.start_backplane(dsn="postgres://x", connect=_connect)
    assert started is True
    assert event_bus._backplane_active is True

    event_bus.publish("user_a", {"type": "startups_changed", "reason": "scout"})
    # Let the sender task drain the queue.
    await asyncio.sleep(0.05)

    notify_conn = FakeConn.instances[1]  # second connect() is the notify conn
    assert len(notify_conn.notified) == 1
    channel, payload = notify_conn.notified[0]
    assert channel == event_bus._NOTIFY_CHANNEL
    data = json.loads(payload)
    assert data["user_id"] == "user_a"
    assert data["event"]["reason"] == "scout"
    assert data["instance"] == event_bus._INSTANCE_ID


@pytest.mark.asyncio
async def test_inbound_notification_redelivers_locally():
    await event_bus.start_backplane(dsn="postgres://x", connect=_connect)
    q = event_bus.subscribe("user_b")
    listen_conn = FakeConn.instances[0]
    cb = listen_conn.listeners[event_bus._NOTIFY_CHANNEL]

    # Simulate a sibling instance's NOTIFY (different instance id).
    payload = json.dumps(
        {"instance": "other-instance", "user_id": "user_b", "event": {"type": "startups_changed"}}
    )
    cb(listen_conn, 1234, event_bus._NOTIFY_CHANNEL, payload)

    assert q.get_nowait() == {"type": "startups_changed"}


@pytest.mark.asyncio
async def test_own_notifications_are_ignored():
    await event_bus.start_backplane(dsn="postgres://x", connect=_connect)
    q = event_bus.subscribe("user_c")
    listen_conn = FakeConn.instances[0]
    cb = listen_conn.listeners[event_bus._NOTIFY_CHANNEL]

    payload = json.dumps(
        {"instance": event_bus._INSTANCE_ID, "user_id": "user_c", "event": {"type": "x"}}
    )
    cb(listen_conn, 1234, event_bus._NOTIFY_CHANNEL, payload)

    assert q.empty()  # our own NOTIFY must not double-deliver


@pytest.mark.asyncio
async def test_publish_returns_local_count_unaffected_by_backplane():
    await event_bus.start_backplane(dsn="postgres://x", connect=_connect)
    event_bus.subscribe("user_d")
    event_bus.subscribe("user_d")
    delivered = event_bus.publish("user_d", {"type": "startups_changed"})
    assert delivered == 2  # local count only


@pytest.mark.asyncio
async def test_stop_backplane_closes_connections_and_is_idempotent():
    await event_bus.start_backplane(dsn="postgres://x", connect=_connect)
    conns = list(FakeConn.instances)
    await event_bus.stop_backplane()
    assert all(c.closed for c in conns)
    assert event_bus._backplane_active is False
    await event_bus.stop_backplane()  # idempotent
