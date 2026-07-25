from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
import pytest

from authority.models import RolloutMode, RolloutRecord
from authority.repository import AuthorityConflict, AuthorityTransitionError
from authority.repository import AuthorityBlocked
from authority.service import AuthorityService
from security.rate_limiter import InMemorySecurityStore


@dataclass
class _ProjectionReplay:
    applied: int = 0
    calls: list[dict] | None = None

    def __post_init__(self):
        self.calls = []

    async def replay(self, **kwargs):
        self.calls.append(kwargs)
        return self.applied


class _AuthorityRepository:
    def __init__(self, *, rollout: RolloutRecord):
        self.rollout = rollout
        self.calls: list[dict] = []

    async def get_rollout(self, *, user_id: str):
        self.calls.append({"method": "get_rollout", "user_id": user_id})
        if user_id != self.rollout.user_id:
            raise AssertionError("authority route leaked a tenant id")
        return self.rollout

    async def transition_rollout(self, **kwargs):
        self.calls.append({"method": "transition_rollout", **kwargs})
        if kwargs["user_id"] != self.rollout.user_id:
            raise AssertionError("authority transition leaked a tenant id")
        if kwargs["expected_version"] != self.rollout.version:
            raise AuthorityConflict("stale authority rollout version")
        target = RolloutMode(kwargs["target_mode"])
        if self.rollout.mode is RolloutMode.LEGACY and target is not RolloutMode.SHADOW:
            raise AuthorityTransitionError("illegal authority rollout transition")
        if (
            target is RolloutMode.CANONICAL_READ
            and self.rollout.last_reconciliation_status != "green"
        ):
            raise AuthorityTransitionError("canonical read requires green reconciliation")
        self.rollout = self.rollout.model_copy(
            update={
                "mode": target,
                "version": self.rollout.version + 1,
                "snapshot_id": kwargs.get("snapshot_id"),
                "activated_by": kwargs["actor_id"],
                "kill_switch": bool(kwargs.get("kill_switch", False)),
            }
        )
        return self.rollout

    async def rearm_rollout(self, **kwargs):
        raise AssertionError("not used by these route tests")


class _RollbackRepository(_AuthorityRepository):
    async def transition_rollout(self, **kwargs):
        self.calls.append({"method": "transition_rollout", **kwargs})
        if kwargs["expected_version"] != self.rollout.version:
            raise AuthorityConflict("stale authority rollout version")
        self.rollout = self.rollout.model_copy(
            update={
                "mode": RolloutMode.LEGACY,
                "version": self.rollout.version + 1,
                "kill_switch": True,
                "activated_by": kwargs["actor_id"],
            }
        )
        return self.rollout


def _rollout(**overrides) -> RolloutRecord:
    values = {"user_id": "tenant-a", "mode": RolloutMode.LEGACY, "version": 0}
    values.update(overrides)
    return RolloutRecord(**values)


def _client(monkeypatch, repository, *, user_id: str = "tenant-a", projector=None):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda _token: user_id)
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.authority_repository = repository
    api.app.state.authority_service = AuthorityService(repository)
    api.app.state.authority_projection_consumer = projector
    return TestClient(api.app)


def _auth():
    return {"Authorization": "Bearer clerk-token"}


def test_status_requires_authentication(monkeypatch):
    client = _client(monkeypatch, _AuthorityRepository(rollout=_rollout()))

    response = client.get("/api/authority/status")

    assert response.status_code == 401


def test_status_is_tenant_scoped_and_has_the_rollout_contract(monkeypatch):
    repository = _AuthorityRepository(
        rollout=_rollout(
            mode=RolloutMode.CANONICAL_READ,
            version=4,
            last_reconciliation_status="green",
        )
    )
    client = _client(monkeypatch, repository)

    response = client.get("/api/authority/status", headers=_auth())

    assert response.status_code == 200
    assert response.json() == {
        "mode": "canonical_read",
        "version": 4,
        "kill_switch": False,
        "canonical_writes_allowed": False,
        "canonical_reads_allowed": True,
        "last_reconciliation_status": "green",
    }
    assert repository.calls == [{"method": "get_rollout", "user_id": "tenant-a"}]


def test_transition_rejects_illegal_and_stale_versions_as_conflicts(monkeypatch):
    illegal = _client(monkeypatch, _AuthorityRepository(rollout=_rollout()))
    illegal_response = illegal.post(
        "/api/authority/transition",
        headers=_auth(),
        json={"target_mode": "canonical_write", "expected_version": 0},
    )
    stale = _client(monkeypatch, _AuthorityRepository(rollout=_rollout(version=2)))
    stale_response = stale.post(
        "/api/authority/transition",
        headers=_auth(),
        json={"target_mode": "shadow", "expected_version": 1},
    )

    assert illegal_response.status_code == stale_response.status_code == 409


def test_transition_uses_authenticated_operator_as_actor_and_never_body_tenant(monkeypatch):
    repository = _AuthorityRepository(rollout=_rollout())
    client = _client(monkeypatch, repository)

    response = client.post(
        "/api/authority/transition",
        headers=_auth(),
        json={
            "target_mode": "shadow",
            "expected_version": 0,
            "snapshot_id": "snapshot-1",
            "user_id": "tenant-b",
        },
    )

    assert response.status_code == 422
    assert not any(call["method"] == "transition_rollout" for call in repository.calls)


def test_rollback_returns_killed_legacy_record(monkeypatch):
    repository = _RollbackRepository(
        rollout=_rollout(mode=RolloutMode.CANONICAL_WRITE, version=3)
    )
    client = _client(monkeypatch, repository)

    response = client.post(
        "/api/authority/rollback",
        headers=_auth(),
        json={"expected_version": 3, "reason": "reconciliation mismatch"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "legacy"
    assert response.json()["kill_switch"] is True
    call = repository.calls[-1]
    assert call["actor_id"] == call["user_id"] == "tenant-a"
    assert call["rollback_reason"] == "reconciliation mismatch"


@pytest.mark.parametrize("selector", [{"event_id": "event-1"}, {"opportunity_id": "opportunity-1"}])
def test_replay_is_tenant_scoped_and_returns_applied_count(monkeypatch, selector):
    projector = _ProjectionReplay(applied=2)
    client = _client(monkeypatch, _AuthorityRepository(rollout=_rollout()), projector=projector)

    response = client.post("/api/authority/replay-projection", headers=_auth(), json=selector)

    assert response.status_code == 200
    assert response.json() == {"applied": 2}
    assert projector.calls == [{"user_id": "tenant-a", **selector}]


def test_replay_requires_exactly_one_selector(monkeypatch):
    client = _client(monkeypatch, _AuthorityRepository(rollout=_rollout()), projector=_ProjectionReplay())

    response = client.post(
        "/api/authority/replay-projection",
        headers=_auth(),
        json={"event_id": "event-1", "opportunity_id": "opportunity-1"},
    )

    assert response.status_code == 422


def test_canonical_read_transition_refuses_non_green_reconciliation(monkeypatch):
    repository = _AuthorityRepository(
        rollout=_rollout(
            mode=RolloutMode.CANONICAL_WRITE,
            version=3,
            last_reconciliation_status="pending",
        )
    )
    client = _client(monkeypatch, repository)

    response = client.post(
        "/api/authority/transition",
        headers=_auth(),
        json={"target_mode": "canonical_read", "expected_version": 3},
    )

    assert response.status_code == 409
    assert "reconciliation" in response.json()["detail"]["message"]


def test_canonical_write_rejects_direct_legacy_startup_mutation_with_typed_conflict(monkeypatch):
    import api

    repository = _AuthorityRepository(
        rollout=_rollout(mode=RolloutMode.CANONICAL_WRITE, version=3)
    )
    client = _client(monkeypatch, repository)

    class LegacyStorage:
        def get_by_id(self, _startup_id):
            return {"startup_id": "d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1"}

        def update_startup_partial(self, *_args):
            raise AssertionError("canonical authority must reject before legacy mutation")

    monkeypatch.setattr(api, "_get_storage", lambda _request: LegacyStorage())
    response = client.post(
        "/api/startups/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/acknowledge",
        headers=_auth(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"


@pytest.mark.parametrize(
    "path",
    [
        "/api/startups/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/acknowledge",
        "/api/escalations/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/resolve",
    ],
)
def test_rollback_kill_switch_fences_legacy_writes_before_storage_access(monkeypatch, path):
    import api

    client = _client(
        monkeypatch,
        _AuthorityRepository(rollout=_rollout(mode=RolloutMode.LEGACY, kill_switch=True)),
    )
    monkeypatch.setattr(
        api,
        "_get_storage",
        lambda _request: (_ for _ in ()).throw(
            AssertionError("kill switch must reject before legacy storage access")
        ),
    )
    response = client.post(
        path,
        headers=_auth(),
        json=(
            {"decision": "NO", "notes": "The opportunity does not fit the mandate."}
            if "/escalations/" in path
            else None
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"


def test_canonical_write_escalation_never_updates_legacy_startup_without_linked_opportunity(
    monkeypatch,
):
    import api

    client = _client(
        monkeypatch,
        _AuthorityRepository(rollout=_rollout(mode=RolloutMode.CANONICAL_WRITE)),
    )

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **kwargs):
            assert kwargs == {
                "user_id": "tenant-a",
                "legacy_startup_id": "d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1",
            }
            return None

    class LegacyStorage:
        def update_startup_partial(self, *_args):
            raise AssertionError("canonical escalation must not update legacy startups")

    api.app.state.identity_repository = IdentityRepository()
    monkeypatch.setattr(api, "_get_storage", lambda _request: LegacyStorage())
    response = client.post(
        "/api/escalations/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/resolve",
        headers=_auth(),
        json={"decision": "YES", "notes": "Strong evidence supports advancing."},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"


def test_canonical_write_escalation_delegates_linked_opportunity_to_canonical_ruling(
    monkeypatch,
):
    import api

    client = _client(
        monkeypatch,
        _AuthorityRepository(rollout=_rollout(mode=RolloutMode.CANONICAL_WRITE)),
    )

    class IdentityRepository:
        async def get_opportunity_by_legacy_projection(self, **_kwargs):
            return type("Opportunity", (), {"opportunity_id": "opportunity-1"})()

    class DecisionRepository:
        def __init__(self):
            self.calls = []

        async def create_ruling(self, ruling, *, actor_id):
            self.calls.append((ruling, actor_id))
            return {"ruling_id": "ruling-1", "opportunity_id": ruling.opportunity_id}

    class LegacyStorage:
        def get_by_id(self, *_args):
            raise AssertionError("canonical escalation must not read a legacy startup")

    decisions = DecisionRepository()
    api.app.state.identity_repository = IdentityRepository()
    api.app.state.decision_repository = decisions
    monkeypatch.setattr(api, "_get_storage", lambda _request: LegacyStorage())
    response = client.post(
        "/api/escalations/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/resolve",
        headers=_auth(),
        json={"decision": "YES", "notes": "Strong evidence supports advancing."},
    )

    assert response.status_code == 200
    assert response.json()["canonical"] is True
    assert response.json()["ruling"]["ruling_id"] == "ruling-1"
    assert decisions.calls[0][0].decision.value == "advance"
    assert decisions.calls[0][1] == "tenant-a"


@pytest.mark.parametrize(
    "path",
    ["/api/startups", "/api/startups/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1"],
)
def test_canonical_read_primary_startup_routes_do_not_fall_back_to_legacy_dtos(
    monkeypatch, path
):
    import api

    client = _client(
        monkeypatch,
        _AuthorityRepository(
            rollout=_rollout(
                mode=RolloutMode.CANONICAL_READ,
                version=4,
                last_reconciliation_status="green",
            )
        ),
    )

    class LegacyStorage:
        def get_by_id(self, *_args):
            raise AssertionError("canonical read must not query the legacy startup DTO")

        def get_list_projection_rows(self, **_kwargs):
            raise AssertionError("canonical read must not query the legacy startup DTO")

    monkeypatch.setattr(api, "_get_storage", lambda _request: LegacyStorage())
    response = client.get(path, headers=_auth())

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_READ_NOT_CERTIFIED"


def test_backfill_apply_requires_backfill_authority_mode(monkeypatch):
    client = _client(
        monkeypatch,
        _AuthorityRepository(
            rollout=_rollout(mode=RolloutMode.CANONICAL_WRITE, version=3)
        ),
    )
    response = client.post(
        "/api/authority/backfill",
        headers=_auth(),
        json={"apply": True, "batch_size": 10},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CONFLICT"


@pytest.mark.parametrize(
    ("rollout", "expected_code"),
    [
        (
            _rollout(
                mode=RolloutMode.CANONICAL_READ,
                version=4,
                last_reconciliation_status="green",
            ),
            "AUTHORITY_CANONICAL_READ_NOT_CERTIFIED",
        ),
        (_rollout(mode=RolloutMode.LEGACY, kill_switch=True), "AUTHORITY_CANONICAL_ONLY"),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "/api/startups/d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1/memo",
        "/api/escalations",
    ],
)
def test_canonical_or_killed_legacy_reads_fail_closed_before_storage(
    monkeypatch, rollout, expected_code, path
):
    import api

    client = _client(monkeypatch, _AuthorityRepository(rollout=rollout))
    monkeypatch.setattr(
        api,
        "_get_storage",
        lambda _request: (_ for _ in ()).throw(
            AssertionError("authority read fence must run before legacy storage access")
        ),
    )
    response = client.get(path, headers=_auth())

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == expected_code


@pytest.mark.asyncio
async def test_repository_write_paths_use_the_injected_authority_guard_before_database_access():
    from decisions.models import HumanRulingInput
    from decisions.models import WorkflowActionType
    from decisions.repository import DecisionRepository
    from evaluation_v2.repository import EvaluationRepository
    from identity.repository import IdentityRepository

    class BlockingAuthority:
        def __init__(self):
            self.calls = []

        async def require_write_path(self, *, user_id, operation):
            self.calls.append({"user_id": user_id, "operation": operation})
            raise AuthorityBlocked("authority kill switch is active")

    guard = BlockingAuthority()
    identity = IdentityRepository(None, authority_service=guard)
    evaluation = EvaluationRepository(None, authority_service=guard)
    decisions = DecisionRepository(None, authority_service=guard)

    with pytest.raises(AuthorityBlocked):
        await identity.resolve_case(
            user_id="tenant-a",
            identity_case_id="case-1",
            selected_company_id="company-1",
            resolved_by="operator-a",
        )
    with pytest.raises(AuthorityBlocked):
        await evaluation.evaluate(
            user_id="tenant-a",
            opportunity_id="opportunity-1",
            actor_id="operator-a",
            trigger_type="operator_refresh",
            policy=None,
        )
    with pytest.raises(AuthorityBlocked):
        await decisions.create_ruling(
            HumanRulingInput(
                user_id="tenant-a",
                opportunity_id="opportunity-1",
                decision="pass",
                rationale="outside our investment mandate",
            ),
            actor_id="operator-a",
        )
    with pytest.raises(AuthorityBlocked):
        await decisions.create_action(
            user_id="tenant-a",
            opportunity_id="opportunity-1",
            action_type=WorkflowActionType.SCHEDULE_MONITOR_REVIEW,
        )
    with pytest.raises(AuthorityBlocked):
        await decisions.approve_action(
            user_id="tenant-a",
            workflow_action_id="action-1",
            approved_by="operator-a",
        )

    assert guard.calls == [
        {"user_id": "tenant-a", "operation": "identity linkage"},
        {"user_id": "tenant-a", "operation": "evaluation creation"},
        {"user_id": "tenant-a", "operation": "human ruling creation"},
        {"user_id": "tenant-a", "operation": "workflow action creation"},
        {"user_id": "tenant-a", "operation": "workflow action approval"},
    ]


@pytest.mark.asyncio
async def test_shadow_mode_never_projects_canonical_events_into_legacy_startups():
    from authority.projection import AuthorityProjectionConsumer
    from authority.service import AuthorityContext

    class ProjectionRepository:
        def __init__(self):
            self.calls = []

        async def get_projection_receipt(self, **kwargs):
            self.calls.append(("receipt", kwargs))
            return None

        async def apply_legacy_projection(self, **kwargs):
            self.calls.append(("projection", kwargs))
            raise AssertionError("shadow mode must not mutate legacy startup projections")

    class ShadowAuthority:
        async def authority(self, *, user_id):
            return AuthorityContext(
                user_id=user_id,
                mode=RolloutMode.SHADOW,
                version=1,
                kill_switch=False,
                last_reconciliation_status=None,
            )

    repository = ProjectionRepository()
    consumer = AuthorityProjectionConsumer(repository, authority_service=ShadowAuthority())

    applied = await consumer.apply(
        user_id="tenant-a",
        event_id="2b25c2df-0ad1-4e6a-b285-977a1d80c51f",
        aggregate_type="recommendation",
        aggregate_id="96ff49e4-4f28-476d-aa86-c2ca75272d92",
        event_type="recommendation.created",
        payload={"user_id": "tenant-a", "startup_id": "startup-1", "state": "advance"},
    )

    assert applied is None
    assert repository.calls == []
