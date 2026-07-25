from collections import deque
from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

import pytest

from authority.models import BlockCode, RolloutMode, WorkflowState
from authority.repository import (
    AuthorityBlocked,
    AuthorityConflict,
    AuthorityRepository,
    AuthorityTransitionError,
)


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, *, fetchrows=(), outbox_error=False):
        self.fetchrows = deque(fetchrows)
        self.calls = []
        self.outbox_error = outbox_error

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.popleft() if self.fetchrows else None

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        if self.outbox_error and "domain_outbox" in sql:
            raise RuntimeError("outbox unavailable")
        return "INSERT 0 1"


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


def _rollout_row(**overrides):
    row = {
        "user_id": "tenant-a",
        "mode": "legacy",
        "version": 0,
        "activated_at": None,
        "activated_by": None,
        "snapshot_id": None,
        "last_reconciliation_status": None,
        "kill_switch": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


def _workflow_row(**overrides):
    row = {
        "user_id": "tenant-a",
        "opportunity_id": str(uuid4()),
        "workflow_state": "admitted",
        "workflow_version": 0,
        "block_code": None,
        "block_detail": None,
        "block_recovery": None,
        "last_transition_id": None,
        "updated_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_get_rollout_bootstraps_legacy_once_for_a_tenant():
    row = _rollout_row()
    connection = _Connection(fetchrows=[row, row])
    repository = AuthorityRepository(_Pool(connection))

    first = await repository.get_rollout(user_id="tenant-a")
    second = await repository.get_rollout(user_id="tenant-a")

    assert first.mode is RolloutMode.LEGACY
    assert second.version == 0
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "insert into public.tenant_authority_rollouts" in sql
    assert "on conflict (user_id) do nothing" in sql
    assert sql.count("insert into public.tenant_authority_rollouts") == 2


@pytest.mark.asyncio
async def test_rollout_rejects_legacy_to_canonical_write():
    connection = _Connection(fetchrows=[_rollout_row()])
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityTransitionError):
        await repository.transition_rollout(
            user_id="tenant-a",
            expected_version=0,
            target_mode=RolloutMode.CANONICAL_WRITE,
            actor_id="operator-a",
            snapshot_id=None,
        )

    assert not any("domain_outbox" in call[1] for call in connection.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("reconciliation_status", [None, "pending"])
async def test_rollout_rejects_canonical_read_until_reconciliation_is_green(
    reconciliation_status,
):
    connection = _Connection(
        fetchrows=[
            _rollout_row(
                mode="canonical_write",
                version=3,
                last_reconciliation_status=reconciliation_status,
            )
        ]
    )
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityTransitionError, match="reconciliation"):
        await repository.transition_rollout(
            user_id="tenant-a",
            expected_version=3,
            target_mode=RolloutMode.CANONICAL_READ,
            actor_id="operator-a",
            snapshot_id=None,
        )

    assert not any("domain_outbox" in call[1] for call in connection.calls)


@pytest.mark.asyncio
async def test_rollout_allows_ordered_transition_and_writes_outbox_in_transaction():
    connection = _Connection(
        fetchrows=[
            _rollout_row(),
            _rollout_row(mode="shadow", version=1, activated_by="operator-a"),
        ]
    )
    repository = AuthorityRepository(_Pool(connection))

    record = await repository.transition_rollout(
        user_id="tenant-a",
        expected_version=0,
        target_mode=RolloutMode.SHADOW,
        actor_id="operator-a",
        snapshot_id="snapshot-1",
    )

    assert record.mode is RolloutMode.SHADOW
    assert record.version == 1
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "for update" in sql
    assert "where user_id=$1 and version=$2" in sql
    assert "insert into public.domain_outbox" in sql
    assert "authority.rollout_transitioned" in str(connection.calls)


@pytest.mark.asyncio
async def test_rollout_allows_each_step_of_the_ordered_cutover():
    connection = _Connection(
        fetchrows=[
            _rollout_row(mode="legacy", version=0),
            _rollout_row(mode="shadow", version=1),
            _rollout_row(mode="shadow", version=1),
            _rollout_row(mode="backfill", version=2),
            _rollout_row(mode="backfill", version=2),
            _rollout_row(mode="canonical_write", version=3),
            _rollout_row(
                mode="canonical_write", version=3, last_reconciliation_status="green"
            ),
            _rollout_row(
                mode="canonical_read", version=4, last_reconciliation_status="green"
            ),
        ]
    )
    repository = AuthorityRepository(_Pool(connection))
    current = _rollout_row(mode="legacy", version=0)
    for target in (
        RolloutMode.SHADOW,
        RolloutMode.BACKFILL,
        RolloutMode.CANONICAL_WRITE,
        RolloutMode.CANONICAL_READ,
    ):
        current = await repository.transition_rollout(
            user_id="tenant-a",
            expected_version=current["version"],
            target_mode=target,
            actor_id="operator-a",
            snapshot_id=None,
        )
        current = {"version": current.version}
    assert current["version"] == 4


@pytest.mark.asyncio
async def test_stale_rollout_transition_is_rejected():
    connection = _Connection(fetchrows=[_rollout_row(version=2)])
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityConflict):
        await repository.transition_rollout(
            user_id="tenant-a",
            expected_version=1,
            target_mode=RolloutMode.SHADOW,
            actor_id="operator-a",
            snapshot_id=None,
        )


@pytest.mark.asyncio
async def test_rollout_rejects_cross_tenant_row():
    connection = _Connection(fetchrows=[_rollout_row(user_id="tenant-b")])
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityConflict):
        await repository.transition_rollout(
            user_id="tenant-a",
            expected_version=0,
            target_mode=RolloutMode.SHADOW,
            actor_id="operator-a",
            snapshot_id=None,
        )


@pytest.mark.asyncio
async def test_workflow_transition_rejects_optimistic_lock_conflict():
    connection = _Connection(fetchrows=[_rollout_row(), None])
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityConflict):
        await repository.transition_workflow(
            user_id="tenant-a",
            opportunity_id=uuid4(),
            expected_version=4,
            target_state=WorkflowState.TRIAGE_PENDING,
            transition_id=uuid4(),
        )

    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "workflow_version=$3" in sql
    assert "user_id=$1" in sql


@pytest.mark.asyncio
async def test_workflow_transition_rejects_writes_while_kill_switch_is_active():
    connection = _Connection(fetchrows=[_rollout_row(kill_switch=True)])
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityBlocked, match="kill switch"):
        await repository.transition_workflow(
            user_id="tenant-a",
            opportunity_id=uuid4(),
            expected_version=0,
            target_state=WorkflowState.TRIAGE_PENDING,
            transition_id=uuid4(),
        )

    assert not any("update public.opportunities" in call[1].lower() for call in connection.calls)


@pytest.mark.asyncio
async def test_workflow_blocked_state_requires_complete_block_metadata():
    repository = AuthorityRepository(_Pool(_Connection()))

    with pytest.raises(ValueError, match="block"):
        await repository.transition_workflow(
            user_id="tenant-a",
            opportunity_id=uuid4(),
            expected_version=0,
            target_state=WorkflowState.BLOCKED,
            transition_id=uuid4(),
            block={"code": BlockCode.THESIS_REQUIRED},
        )


@pytest.mark.asyncio
async def test_workflow_change_and_outbox_are_atomic_when_outbox_fails():
    connection = _Connection(
        fetchrows=[
            _rollout_row(),
            _workflow_row(
                workflow_state="triage_pending",
                workflow_version=1,
                last_transition_id=str(uuid4()),
            ),
        ],
        outbox_error=True,
    )
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await repository.transition_workflow(
            user_id="tenant-a",
            opportunity_id=uuid4(),
            expected_version=0,
            target_state=WorkflowState.TRIAGE_PENDING,
            transition_id=uuid4(),
        )

    assert any("update public.opportunities" in call[1].lower() for call in connection.calls)
    assert any("domain_outbox" in call[1].lower() for call in connection.calls)


@pytest.mark.asyncio
async def test_workflow_outbox_carries_linked_legacy_startup_and_reason():
    legacy_startup_id = "4f591cb7-3c0d-44c5-a663-8dab0bc94e6d"
    connection = _Connection(
        fetchrows=[
            _rollout_row(),
            _workflow_row(
                workflow_state="monitoring",
                workflow_version=1,
                last_transition_id=str(uuid4()),
                legacy_startup_id=legacy_startup_id,
            ),
        ]
    )
    repository = AuthorityRepository(_Pool(connection))

    await repository.transition_workflow(
        user_id="tenant-a",
        opportunity_id=uuid4(),
        expected_version=0,
        target_state=WorkflowState.MONITORING,
        transition_id=uuid4(),
    )

    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == legacy_startup_id
    assert payload["compatibility_reason"] == "workflow transitioned to monitoring"


@pytest.mark.asyncio
async def test_conn_aware_workflow_transition_carries_projection_fields():
    legacy_startup_id = "4f591cb7-3c0d-44c5-a663-8dab0bc94e6d"
    connection = _Connection(fetchrows=[
        _rollout_row(),
        _workflow_row(workflow_state="monitoring", workflow_version=1,
                      last_transition_id=str(uuid4()), legacy_startup_id=legacy_startup_id),
    ])
    repository = AuthorityRepository(_Pool(connection))
    await repository.transition_workflow_on_connection(
        connection, user_id="tenant-a", opportunity_id=uuid4(), expected_version=0,
        target_state=WorkflowState.MONITORING, transition_id=uuid4(),
    )
    outbox = next(call for call in connection.calls
                  if call[0] == "execute" and "insert into public.domain_outbox" in call[1])
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == legacy_startup_id
    assert payload["compatibility_reason"] == "workflow transitioned to monitoring"


@pytest.mark.asyncio
async def test_rearm_clears_kill_switch_only_with_green_reconciliation_and_audits_it():
    connection = _Connection(
        fetchrows=[
            _rollout_row(
                mode="legacy",
                version=6,
                kill_switch=True,
                last_reconciliation_status="green",
            ),
            _rollout_row(
                mode="legacy",
                version=7,
                kill_switch=False,
                last_reconciliation_status="green",
            ),
        ]
    )
    repository = AuthorityRepository(_Pool(connection))

    record = await repository.rearm_rollout(
        user_id="tenant-a",
        expected_version=6,
        actor_id="operator-a",
        reason="reconciliation repaired",
    )

    assert record.kill_switch is False
    assert record.version == 7
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "where user_id=$1 and version=$2 and kill_switch=true" in sql
    assert "authority.kill_switch_cleared" in str(connection.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [None, "pending"])
async def test_rearm_repository_requires_green_reconciliation(status):
    connection = _Connection(
        fetchrows=[
            _rollout_row(
                mode="legacy",
                version=6,
                kill_switch=True,
                last_reconciliation_status=status,
            )
        ]
    )
    repository = AuthorityRepository(_Pool(connection))

    with pytest.raises(AuthorityBlocked, match="reconciliation"):
        await repository.rearm_rollout(
            user_id="tenant-a",
            expected_version=6,
            actor_id="operator-a",
            reason="reconciliation repaired",
        )
