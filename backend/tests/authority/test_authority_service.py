import pytest

from authority.models import RolloutMode, RolloutRecord
from authority.service import AuthorityBlocked, AuthorityService


class _Repository:
    def __init__(self, rollout):
        self.rollout = rollout
        self.rollback_calls = []
        self.rearm_calls = []

    async def get_rollout(self, *, user_id):
        assert user_id == self.rollout.user_id
        return self.rollout

    async def transition_rollout(self, **kwargs):
        self.rollback_calls.append(kwargs)
        self.rollout = self.rollout.model_copy(
            update={
                "mode": RolloutMode.LEGACY,
                "version": self.rollout.version + 1,
                "kill_switch": True,
            }
        )
        return self.rollout

    async def rearm_rollout(self, **kwargs):
        self.rearm_calls.append(kwargs)
        self.rollout = self.rollout.model_copy(
            update={"version": self.rollout.version + 1, "kill_switch": False}
        )
        return self.rollout


def _rollout(**overrides):
    values = {"user_id": "tenant-a", "mode": RolloutMode.LEGACY, "version": 0}
    values.update(overrides)
    return RolloutRecord(**values)


@pytest.mark.asyncio
async def test_authority_context_exposes_calculated_mode_permissions():
    service = AuthorityService(_Repository(_rollout(mode=RolloutMode.CANONICAL_WRITE, version=3)))

    context = await service.authority(user_id="tenant-a")

    assert context.mode is RolloutMode.CANONICAL_WRITE
    assert context.canonical_writes_allowed is True
    assert context.canonical_reads_allowed is False
    assert context.legacy_projection_allowed is True


@pytest.mark.asyncio
async def test_canonical_read_requires_green_reconciliation_before_canonical_reads():
    service = AuthorityService(
        _Repository(
            _rollout(
                mode=RolloutMode.CANONICAL_READ,
                last_reconciliation_status="pending",
            )
        )
    )

    context = await service.authority(user_id="tenant-a")

    assert context.canonical_reads_allowed is False
    assert context.canonical_writes_allowed is False
    assert context.legacy_projection_allowed is False


@pytest.mark.asyncio
async def test_require_write_path_returns_explicit_legacy_and_shadow_behavior():
    legacy = AuthorityService(_Repository(_rollout()))
    shadow = AuthorityService(_Repository(_rollout(mode=RolloutMode.SHADOW)))

    legacy_context = await legacy.require_write_path(user_id="tenant-a", operation="identity")
    shadow_context = await shadow.require_write_path(user_id="tenant-a", operation="identity")

    assert legacy_context.mode is RolloutMode.LEGACY
    assert legacy_context.canonical_writes_allowed is False
    assert legacy_context.legacy_projection_allowed is True
    assert shadow_context.mode is RolloutMode.SHADOW
    assert shadow_context.canonical_writes_allowed is True
    assert shadow_context.legacy_projection_allowed is False


@pytest.mark.asyncio
async def test_require_write_path_blocks_canonical_read_only_and_killed_tenants():
    canonical_read = AuthorityService(
        _Repository(_rollout(mode=RolloutMode.CANONICAL_READ, last_reconciliation_status="green"))
    )
    killed = AuthorityService(_Repository(_rollout(kill_switch=True)))

    with pytest.raises(AuthorityBlocked, match="canonical read"):
        await canonical_read.require_write_path(user_id="tenant-a", operation="ruling")
    with pytest.raises(AuthorityBlocked, match="kill switch"):
        await killed.require_write_path(user_id="tenant-a", operation="worker")


@pytest.mark.asyncio
async def test_rollback_moves_canonical_tenant_to_killed_legacy_and_emits_audit_event():
    repository = _Repository(_rollout(mode=RolloutMode.CANONICAL_WRITE, version=5))
    service = AuthorityService(repository)

    record = await service.rollback(
        user_id="tenant-a",
        expected_version=5,
        actor_id="operator-a",
        reason="reconciliation mismatch",
    )

    assert record.mode is RolloutMode.LEGACY
    assert record.kill_switch is True
    assert repository.rollback_calls == [
        {
            "user_id": "tenant-a",
            "expected_version": 5,
            "target_mode": RolloutMode.LEGACY,
            "actor_id": "operator-a",
            "snapshot_id": None,
            "kill_switch": True,
            "rollback_reason": "reconciliation mismatch",
        }
    ]


@pytest.mark.asyncio
async def test_rearm_requires_green_reconciliation_and_explicit_expected_version():
    repository = _Repository(
        _rollout(
            mode=RolloutMode.LEGACY,
            version=6,
            kill_switch=True,
            last_reconciliation_status="pending",
        )
    )
    service = AuthorityService(repository)

    with pytest.raises(AuthorityBlocked, match="reconciliation"):
        await service.rearm(
            user_id="tenant-a",
            expected_version=6,
            actor_id="operator-a",
            reason="reconciliation repaired",
        )


@pytest.mark.asyncio
async def test_rearm_delegates_audited_clear_after_green_reconciliation():
    repository = _Repository(
        _rollout(
            mode=RolloutMode.LEGACY,
            version=6,
            kill_switch=True,
            last_reconciliation_status="green",
        )
    )
    service = AuthorityService(repository)

    record = await service.rearm(
        user_id="tenant-a",
        expected_version=6,
        actor_id="operator-a",
        reason="reconciliation repaired",
    )

    assert record.kill_switch is False
    assert repository.rearm_calls == [
        {
            "user_id": "tenant-a",
            "expected_version": 6,
            "actor_id": "operator-a",
            "reason": "reconciliation repaired",
        }
    ]
