import asyncio

import pytest

from pipeline_execution import PipelineExecutionResult, PipelineExecutionState


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
    identity_repository = object()
    queue = _OneJobQueue(
        {
            "user_id": "user-a",
            "manual_one_shot": True,
            "lock_key": None,
        }
    )
    calls = []
    statuses = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))
        return PipelineExecutionResult.completed(
            code="pipeline_cycle_completed", detail="Cycle completed."
        )

    async def update(user_id, status, *, execution_result=None):
        statuses.append((user_id, status, execution_result))

    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(api, "_update_agent_run_status", update)
    monkeypatch.setattr(
        api.app.state,
        "fund_intelligence_repository",
        governed_repository,
        raising=False,
    )
    monkeypatch.setattr(
        api.app.state,
        "identity_repository",
        identity_repository,
        raising=False,
    )

    await api._agent_worker()

    assert calls == [
        (
            "user-a",
            {
                "manual_one_shot": True,
                "identity_repository": identity_repository,
                "fund_intelligence_repository": governed_repository,
            },
        )
    ]
    assert statuses[0][0:2] == ("user-a", "running")
    assert statuses[0][2].state is PipelineExecutionState.COMPLETED
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
        return PipelineExecutionResult.completed(
            code="lookup_completed",
            detail="Lookup completed.",
            startup_id="startup-1",
        )

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


@pytest.mark.asyncio
async def test_agent_worker_preserves_blocked_code_detail_and_recovery_in_status(
    monkeypatch,
):
    import api

    queue = _OneJobQueue({"user_id": "user-a", "lock_key": None})
    statuses = []

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.blocked(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish the fund policy in Settings.",
        )

    async def update(user_id, status, *, execution_result=None):
        statuses.append((user_id, status, execution_result))

    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(api, "_update_agent_run_status", update)

    await api._agent_worker()

    assert statuses[0][0:2] == ("user-a", "error")
    result = statuses[0][2]
    assert result.code == "published_policy_required"
    assert result.detail == "A published policy is required."
    assert result.recovery_action == "Publish the fund policy in Settings."


@pytest.mark.asyncio
async def test_agent_worker_records_skip_without_claiming_running(monkeypatch):
    import api

    queue = _OneJobQueue({"user_id": "user-a", "lock_key": None})
    statuses = []

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.skipped(
            code="agents_disabled", detail="No enabled stages."
        )

    async def update(user_id, status, *, execution_result=None):
        statuses.append((user_id, status, execution_result))

    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(api, "_update_agent_run_status", update)

    await api._agent_worker()

    assert statuses[0][0:2] == ("user-a", "stopped")
    assert statuses[0][2].state is PipelineExecutionState.SKIPPED


@pytest.mark.asyncio
async def test_agent_worker_records_unexpected_boundary_failure_as_error(monkeypatch):
    import api

    queue = _OneJobQueue({"user_id": "user-a", "lock_key": None})
    statuses = []

    async def run(*_args, **_kwargs):
        raise RuntimeError("unexpected boundary failure")

    async def update(user_id, status, *, execution_result=None):
        statuses.append((user_id, status, execution_result))

    monkeypatch.setattr(api, "_agent_queue", queue)
    monkeypatch.setattr(api, "run_one_pipeline_cycle", run)
    monkeypatch.setattr(api, "_update_agent_run_status", update)

    await api._agent_worker()

    assert statuses == [("user-a", "error", None)]
