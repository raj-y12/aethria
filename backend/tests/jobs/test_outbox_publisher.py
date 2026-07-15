import importlib
from types import SimpleNamespace

import pytest


class _Repository:
    def __init__(self, events):
        self.events = events
        self.published = []
        self.failed = []

    async def claim_outbox_batch(self, **kwargs):
        events, self.events = self.events, []
        return events

    async def mark_outbox_published(self, **kwargs):
        self.published.append(kwargs)
        return True

    async def mark_outbox_failed(self, **kwargs):
        self.failed.append(kwargs)
        return True


@pytest.mark.asyncio
async def test_outbox_marks_published_only_after_event_delivery():
    outbox = importlib.import_module("jobs.outbox")
    event = SimpleNamespace(
        event_id="event-1",
        user_id="user-a",
        event_type="agent_job.succeeded",
        payload={"job_id": "job-1"},
    )
    repository = _Repository([event])
    delivered = []

    async def publish(user_id, event_type, payload):
        delivered.append((user_id, event_type, payload))

    publisher = outbox.OutboxPublisher(repository, publish=publish)

    assert await publisher.publish_once() == 1
    assert delivered == [("user-a", "agent_job.succeeded", {"job_id": "job-1"})]
    assert repository.published == [{"event_id": "event-1"}]
    assert repository.failed == []


@pytest.mark.asyncio
async def test_outbox_delivery_failure_remains_retryable():
    outbox = importlib.import_module("jobs.outbox")
    event = SimpleNamespace(
        event_id="event-1",
        user_id="user-a",
        event_type="agent_job.succeeded",
        payload={"job_id": "job-1"},
    )
    repository = _Repository([event])

    async def publish(*args):
        raise RuntimeError("backplane unavailable")

    publisher = outbox.OutboxPublisher(repository, publish=publish)

    assert await publisher.publish_once() == 0
    assert repository.published == []
    assert repository.failed[0]["event_id"] == "event-1"
    assert "backplane unavailable" in repository.failed[0]["error"]
