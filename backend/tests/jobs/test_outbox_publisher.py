import importlib
from types import SimpleNamespace

import pytest


class _Repository:
    def __init__(self, events, governed_projection=None):
        self.events = events
        self.published = []
        self.failed = []
        self.governed_projection = governed_projection

    async def claim_outbox_batch(self, **kwargs):
        events, self.events = self.events, []
        return events

    async def mark_outbox_published(self, **kwargs):
        self.published.append(kwargs)
        return True

    async def mark_outbox_failed(self, **kwargs):
        self.failed.append(kwargs)
        return True

    async def get_current_governed_policy_projection(self, *, user_id):
        return self.governed_projection


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


@pytest.mark.asyncio
async def test_governed_policy_projects_exact_config_before_marking_outbox(monkeypatch):
    outbox = importlib.import_module("jobs.outbox")
    policy_store = importlib.import_module("services.scoring.policy_store")
    projected = []

    def publish_policy(user_id, fund_config):
        projected.append((user_id, fund_config))
        return {"policy_hash": "hash-1"}

    monkeypatch.setattr(policy_store, "publish_policy", publish_policy)
    event = SimpleNamespace(
        event_id="event-policy-1",
        user_id="user-a",
        event_type="governed_policy_version.published",
        payload={"fund_config": {"rubric": []}, "policy_hash": "hash-1"},
    )
    repository = _Repository(
        [event],
        governed_projection={
            "governed_policy_version_id": "version-1",
            "published_policy_id": "version-1",
            "fund_config": {"rubric": []},
            "policy_hash": "hash-1",
        },
    )
    delivered = []

    async def publish(user_id, event_type, payload):
        delivered.append(event_type)

    publisher = outbox.OutboxPublisher(repository, publish=publish)

    assert await publisher.publish_once() == 1
    assert projected == [("user-a", {"rubric": []})]
    assert delivered == ["governed_policy_version.published"]
    assert repository.published == [{"event_id": "event-policy-1"}]


@pytest.mark.asyncio
async def test_stale_policy_event_projects_the_current_authoritative_version(monkeypatch):
    outbox = importlib.import_module("jobs.outbox")
    policy_store = importlib.import_module("services.scoring.policy_store")
    projected = []

    def publish_policy(user_id, fund_config):
        projected.append(fund_config)
        return {"policy_hash": "hash-2"}

    monkeypatch.setattr(policy_store, "publish_policy", publish_policy)
    stale_event = SimpleNamespace(
        event_id="event-policy-old",
        user_id="user-a",
        event_type="governed_policy_version.published",
        payload={"governed_policy_version_id": "version-1"},
    )
    repository = _Repository(
        [stale_event],
        governed_projection={
            "governed_policy_version_id": "version-2",
            "published_policy_id": "version-2",
            "fund_config": {"scoringWeights": [{"key": "market", "weight": 30}]},
            "policy_hash": "hash-2",
        },
    )

    assert await outbox.OutboxPublisher(repository).publish_once() == 1
    assert projected == [
        {"scoringWeights": [{"key": "market", "weight": 30}]}
    ]
    assert repository.published == [{"event_id": "event-policy-old"}]


@pytest.mark.asyncio
async def test_authority_projection_failure_leaves_outbox_event_retryable():
    outbox = importlib.import_module("jobs.outbox")
    event = SimpleNamespace(
        event_id="event-authority-1",
        user_id="user-a",
        aggregate_type="opportunity",
        aggregate_id="opportunity-a",
        event_type="recommendation.created",
        payload={"legacy_startup_id": "startup-a", "state": "advance"},
    )
    repository = _Repository([event])

    async def explode(**kwargs):
        raise RuntimeError("legacy projection unavailable")

    publisher = outbox.OutboxPublisher(
        repository,
        consumers={"authority": explode},
    )

    assert await publisher.publish_once() == 0
    assert repository.published == []
    assert repository.failed[0]["event_id"] == "event-authority-1"
    assert "legacy projection unavailable" in repository.failed[0]["error"]
