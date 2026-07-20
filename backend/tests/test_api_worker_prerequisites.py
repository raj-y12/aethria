import asyncio

import pytest


class _OneJobQueue:
    def __init__(self, job):
        self.job = job
        self.delivered = False
        self.completed = 0

    async def get(self):
        if self.delivered:
            raise asyncio.CancelledError
        self.delivered = True
        return self.job

    def task_done(self):
        self.completed += 1


@pytest.mark.asyncio
async def test_agent_worker_passes_governed_repository_to_direct_cycle(monkeypatch):
    import api

    governed_repository = object()
    queue = _OneJobQueue(
        {
            "user_id": "user-a",
            "manual_one_shot": True,
            "lock_key": None,
        }
    )
    calls = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))

    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(
        api.app.state,
        "fund_intelligence_repository",
        governed_repository,
        raising=False,
    )

    await api._agent_worker()

    assert calls == [
        (
            "user-a",
            {
                "manual_one_shot": True,
                "fund_intelligence_repository": governed_repository,
            },
        )
    ]
    assert queue.completed == 1


@pytest.mark.asyncio
async def test_lookup_worker_passes_governed_repository_to_direct_lookup(monkeypatch):
    import api

    governed_repository = object()
    queue = _OneJobQueue(
        {
            "user_id": "user-a",
            "company_name": "Acme",
            "lookup_id": "lookup-1",
            "lock_key": None,
        }
    )
    calls = []

    async def run(user_id, company_name, **kwargs):
        calls.append((user_id, company_name, kwargs))

    monkeypatch.setattr(api, "_lookup_queue", queue)
    monkeypatch.setattr(api, "_is_lookup_cancelled", lambda *_args: False)
    monkeypatch.setattr(api, "run_on_demand_lookup", run)
    monkeypatch.setattr(
        api.app.state,
        "fund_intelligence_repository",
        governed_repository,
        raising=False,
    )

    await api._lookup_worker()

    assert calls[0][0:2] == ("user-a", "Acme")
    assert calls[0][2]["fund_intelligence_repository"] is governed_repository
    assert queue.completed == 1
