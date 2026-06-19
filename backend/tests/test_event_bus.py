"""Unit tests for the in-process SSE pub/sub (event_bus)."""
import asyncio

import pytest

import event_bus


@pytest.fixture(autouse=True)
def _clean_bus():
    """Each test starts and ends with an empty subscriber table."""
    event_bus._subscribers.clear()
    yield
    event_bus._subscribers.clear()


def test_publish_with_no_subscribers_is_a_noop():
    assert event_bus.publish("user_a", {"type": "startups_changed"}) == 0
    assert event_bus.total_subscribers() == 0


def test_publish_requires_user_and_ignores_blank():
    assert event_bus.publish("", {"type": "x"}) == 0
    assert event_bus.publish("   ", {"type": "x"}) == 0


def test_subscribe_rejects_empty_user():
    with pytest.raises(ValueError):
        event_bus.subscribe("")


@pytest.mark.asyncio
async def test_subscribe_publish_delivers_to_that_user_only():
    q_a = event_bus.subscribe("user_a")
    q_b = event_bus.subscribe("user_b")

    delivered = event_bus.publish("user_a", {"type": "startups_changed", "reason": "scout"})

    assert delivered == 1
    assert q_a.get_nowait() == {"type": "startups_changed", "reason": "scout"}
    assert q_b.empty()  # other tenant must not receive it


@pytest.mark.asyncio
async def test_publish_fans_out_to_all_connections_for_a_user():
    q1 = event_bus.subscribe("user_a")
    q2 = event_bus.subscribe("user_a")

    delivered = event_bus.publish("user_a", {"type": "startups_changed"})

    assert delivered == 2
    assert q1.get_nowait() == {"type": "startups_changed"}
    assert q2.get_nowait() == {"type": "startups_changed"}


@pytest.mark.asyncio
async def test_unsubscribe_removes_connection_and_cleans_bucket():
    q = event_bus.subscribe("user_a")
    assert event_bus.subscriber_count("user_a") == 1

    event_bus.unsubscribe("user_a", q)

    assert event_bus.subscriber_count("user_a") == 0
    assert "user_a" not in event_bus._subscribers  # bucket cleaned up
    # Unsubscribing again is harmless.
    event_bus.unsubscribe("user_a", q)


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_event():
    q = event_bus.subscribe("user_a")
    # Fill the queue past capacity; the oldest events get evicted.
    total = event_bus._MAX_QUEUED_EVENTS + 5
    for i in range(total):
        event_bus.publish("user_a", {"type": "startups_changed", "seq": i})

    assert q.qsize() == event_bus._MAX_QUEUED_EVENTS
    drained = [q.get_nowait()["seq"] for _ in range(q.qsize())]
    # The newest event is always retained; the oldest were dropped.
    assert drained[-1] == total - 1
    assert drained[0] == total - event_bus._MAX_QUEUED_EVENTS


@pytest.mark.asyncio
async def test_total_subscribers_counts_across_users():
    event_bus.subscribe("user_a")
    event_bus.subscribe("user_a")
    event_bus.subscribe("user_b")
    assert event_bus.total_subscribers() == 3
