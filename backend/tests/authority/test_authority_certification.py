"""Executable evidence for the authority-control rollout boundary."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from authority.models import RolloutMode, RolloutRecord
from authority.projection import AuthorityProjectionConsumer
from authority.service import AuthorityContext, AuthorityService
from security.rate_limiter import InMemorySecurityStore
from scripts import check_phase8_readiness as readiness


class _AuthorityRepository:
    def __init__(self, rollout: RolloutRecord):
        self.rollout = rollout

    async def get_rollout(self, *, user_id: str) -> RolloutRecord:
        assert user_id == self.rollout.user_id
        return self.rollout


class _ProjectionRepository:
    def __init__(self):
        self.receipts = {}
        self.patches = []

    async def get_projection_receipt(self, *, user_id, event_id, consumer):
        return self.receipts.get((user_id, event_id, consumer))

    async def apply_legacy_projection(self, *, user_id, event_id, consumer, aggregate_type, aggregate_id, patch, **_kwargs):
        receipt = SimpleNamespace(
            receipt_id=str(uuid4()),
            user_id=user_id,
            event_id=event_id,
            consumer=consumer,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
        )
        self.receipts[(user_id, event_id, consumer)] = receipt
        self.patches.append(patch)
        return receipt


def _rollout(mode: RolloutMode) -> RolloutRecord:
    return RolloutRecord(user_id="tenant-a", mode=mode, version=1)


def _authenticated_client(monkeypatch, mode: RolloutMode) -> TestClient:
    import api
    import routers.deps

    monkeypatch.setattr(api, "verify_clerk_token", lambda _token: "tenant-a")
    monkeypatch.setattr(routers.deps, "_security_store", InMemorySecurityStore())
    repository = _AuthorityRepository(_rollout(mode))
    api.app.state.authority_repository = repository
    api.app.state.authority_service = AuthorityService(repository)
    return TestClient(api.app)


@pytest.mark.parametrize("mode", [RolloutMode.LEGACY, RolloutMode.SHADOW])
def test_authenticated_manual_lookup_is_admitted_in_legacy_and_shadow_modes(monkeypatch, mode):
    import api

    client = _authenticated_client(monkeypatch, mode)
    lookup_queue = asyncio.Queue()
    monkeypatch.setattr(api, "_lookup_queue", lookup_queue)
    monkeypatch.setattr(api, "_durable_jobs_required", lambda: False)

    response = client.post(
        "/api/startups/lookup",
        headers={"Authorization": "Bearer clerk-token"},
        json={"lookup_input": "Authority Contract Co", "lookup_id": "lookup-authority-1"},
    )

    assert response.status_code == 202
    assert response.json()["user_id"] == "tenant-a"
    queued = lookup_queue.get_nowait()
    assert queued["user_id"] == "tenant-a"
    assert queued["company_name"] == "Authority Contract Co"


@pytest.mark.asyncio
async def test_canonical_write_projects_event_and_records_receipt():
    class CanonicalWriteAuthority:
        async def authority(self, *, user_id):
            return AuthorityContext(
                user_id=user_id,
                mode=RolloutMode.CANONICAL_WRITE,
                version=3,
                kill_switch=False,
                last_reconciliation_status="green",
            )

    repository = _ProjectionRepository()
    event_id = str(uuid4())
    opportunity_id = str(uuid4())
    receipt = await AuthorityProjectionConsumer(
        repository,
        authority_service=CanonicalWriteAuthority(),
    ).apply(
        user_id="tenant-a",
        event_id=event_id,
        aggregate_type="recommendation",
        aggregate_id=opportunity_id,
        event_type="recommendation.created",
        payload={
            "user_id": "tenant-a",
            "legacy_startup_id": "startup-a",
            "opportunity_id": opportunity_id,
            "state": "advance",
        },
    )

    assert receipt is not None
    assert repository.receipts[("tenant-a", event_id, "startups_compatibility")] is receipt
    assert repository.patches[0].patch["partner_info"]["recommendation"] == "MONITOR"


def test_readiness_requires_the_authority_migration_and_service_role_rls():
    assert readiness.AUTHORITY_CONTROL_MIGRATION == "20260722090000_authority_control.sql"
    check = readiness._authority_security_check(
        table_rows=[
            {"table_name": "tenant_authority_rollouts", "relrowsecurity": True},
            {"table_name": "authority_projection_receipts", "relrowsecurity": True},
        ],
        policy_rows=[
            {
                "tablename": "tenant_authority_rollouts",
                "policyname": "tenant_authority_rollouts_service_role_all",
                "roles": ["service_role"],
                "cmd": "ALL",
                "qual": "true",
                "with_check": "true",
            },
            {
                "tablename": "authority_projection_receipts",
                "policyname": "authority_projection_receipts_service_role_all",
                "roles": ["service_role"],
                "cmd": "ALL",
                "qual": "true",
                "with_check": "true",
            },
        ],
        grant_rows=[
            {"table_name": table, "grantee": "service_role", "privilege_type": privilege}
            for table in ("tenant_authority_rollouts", "authority_projection_receipts")
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
        ],
    )

    assert check["status"] == "passed"


@pytest.mark.parametrize(
    ("extra_policy", "extra_grant"),
    [
        (
            {
                "tablename": "tenant_authority_rollouts",
                "policyname": "tenant_authority_rollouts_authenticated_read",
                "roles": ["authenticated"],
                "cmd": "SELECT",
                "qual": "true",
                "with_check": "true",
            },
            None,
        ),
        (
            {
                "tablename": "authority_projection_receipts",
                "policyname": "authority_projection_receipts_anon_read",
                "roles": ["anon"],
                "cmd": "SELECT",
                "qual": "true",
                "with_check": "true",
            },
            None,
        ),
        (None, {"table_name": "authority_projection_receipts", "grantee": "anon", "privilege_type": "SELECT"}),
    ],
)
def test_readiness_rejects_extra_client_authority_policy_or_grant(extra_policy, extra_grant):
    policies = [
        {
            "tablename": table,
            "policyname": policy,
            "roles": ["service_role"],
            "cmd": "ALL",
            "qual": "true",
            "with_check": "true",
        }
        for table, policy in {
            "tenant_authority_rollouts": "tenant_authority_rollouts_service_role_all",
            "authority_projection_receipts": "authority_projection_receipts_service_role_all",
        }.items()
    ]
    grants = [
        {"table_name": table, "grantee": "service_role", "privilege_type": privilege}
        for table in ("tenant_authority_rollouts", "authority_projection_receipts")
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
    ]
    if extra_policy:
        policies.append(extra_policy)
    if extra_grant:
        grants.append(extra_grant)

    check = readiness._authority_security_check(
        table_rows=[
            {"table_name": "tenant_authority_rollouts", "relrowsecurity": True},
            {"table_name": "authority_projection_receipts", "relrowsecurity": True},
        ],
        policy_rows=policies,
        grant_rows=grants,
    )

    assert check["status"] == "failed"
