from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from authority.projection import (
    AuthorityProjectionConsumer,
    ProjectionTenantMismatch,
    legacy_patch_for_event,
)


class _LegacyRepository:
    """In-memory transactional projection port used to exercise real consumer behavior."""

    def __init__(self):
        self.receipts = {}
        self.patch = {}
        self.canonical_writes = []
        self.events = []

    async def get_projection_receipt(self, *, user_id, event_id, consumer):
        return self.receipts.get((user_id, event_id, consumer))

    async def apply_legacy_projection(self, *, user_id, event_id, consumer, aggregate_type, aggregate_id, patch, **_kwargs):
        key = (user_id, event_id, consumer)
        if key in self.receipts:
            return self.receipts[key]
        if patch.startup_id != "startup-a":
            raise LookupError("legacy startup is not available for tenant")
        self.patch = deepcopy(patch.patch)
        receipt = SimpleNamespace(
            receipt_id=str(uuid4()),
            user_id=user_id,
            event_id=event_id,
            consumer=consumer,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
        )
        self.receipts[key] = receipt
        return receipt

    async def list_pending_authority_events(self, *, user_id, opportunity_id=None):
        return [
            event
            for event in self.events
            if event.user_id == user_id
            and (opportunity_id is None or event.aggregate_id == opportunity_id)
        ]

    async def get_outbox_event(self, *, user_id, event_id):
        return next(
            (event for event in self.events if event.user_id == user_id and event.event_id == event_id),
            None,
        )


def event_for(event_type, *, user_id="tenant-a", payload=None, aggregate_type="opportunity"):
    body = {
        "legacy_startup_id": "startup-a",
        "opportunity_id": str(uuid4()),
        **(payload or {}),
    }
    return {
        "user_id": user_id,
        "event_id": str(uuid4()),
        "aggregate_type": aggregate_type,
        "aggregate_id": body["opportunity_id"],
        "event_type": event_type,
        "payload": body,
    }


def test_recommendation_mapping_keeps_insufficient_evidence_visible_and_never_passes():
    patch = legacy_patch_for_event(
        "recommendation.created",
        {
            "legacy_startup_id": "startup-a",
            "recommendation_id": str(uuid4()),
            "opportunity_id": str(uuid4()),
            "state": "insufficient_evidence",
            "reason": "Need customer references",
        },
    )

    assert patch.patch["partner_info"]["recommendation"] == "MONITOR"
    assert patch.patch["partner_info"]["canonical_recommendation_state"] == "insufficient_evidence"
    assert patch.patch["partner_info"]["canonical_recommendation_reason"] == "Need customer references"
    assert patch.patch["partner_info"]["canonical_recommendation_id"]


def test_advance_recommendation_does_not_create_a_portfolio_position():
    patch = legacy_patch_for_event(
        "recommendation.created",
        {
            "legacy_startup_id": "startup-a",
            "recommendation_id": str(uuid4()),
            "opportunity_id": str(uuid4()),
            "state": "advance",
        },
    )

    assert patch.patch["partner_info"]["recommendation"] == "MONITOR"
    assert "portfolio" not in patch.patch
    assert "portfolio_position" not in patch.patch


def test_human_ruling_maps_to_human_resolution_with_canonical_ids_and_reason():
    ruling_id = str(uuid4())
    opportunity_id = str(uuid4())
    patch = legacy_patch_for_event(
        "human_ruling.created",
        {
            "legacy_startup_id": "startup-a",
            "ruling_id": ruling_id,
            "opportunity_id": opportunity_id,
            "decision": "pass",
            "rationale": "Outside mandate",
        },
    )

    assert patch.patch["human_resolution"] == {
        "decision": "PASS",
        "notes": "Outside mandate",
        "canonical_ruling_id": ruling_id,
        "canonical_opportunity_id": opportunity_id,
        "canonical_ruling_rationale": "Outside mandate",
    }


def test_identity_evaluation_memo_and_workflow_events_have_display_only_patches():
    opportunity_id = str(uuid4())
    identity = legacy_patch_for_event(
        "identity_case.resolved",
        {
            "legacy_startup_id": "startup-a",
            "company_id": str(uuid4()),
            "opportunity_id": opportunity_id,
            "reason": "domain verified",
        },
    )
    evaluation = legacy_patch_for_event(
        "evaluation.completed",
        {
            "legacy_startup_id": "startup-a",
            "opportunity_id": opportunity_id,
            "evaluation_id": str(uuid4()),
            "recommended_state": "monitor",
        },
    )
    memo = legacy_patch_for_event(
        "memo.created",
        {
            "legacy_startup_id": "startup-a",
            "opportunity_id": opportunity_id,
            "memo_id": str(uuid4()),
            "markdown": "# Canonical memo",
        },
    )
    workflow = legacy_patch_for_event(
        "opportunity.workflow_changed",
        {
            "legacy_startup_id": "startup-a",
            "opportunity_id": opportunity_id,
            "workflow_state": "monitoring",
            "workflow_version": 3,
        },
    )

    assert identity.patch["scout_info"]["canonical_identity_reason"] == "domain verified"
    assert evaluation.patch["review_info"]["canonical_evaluation_id"]
    assert evaluation.patch["partner_info"]["recommendation"] == "MONITOR"
    assert memo.patch["investment_memo_markdown"] == "# Canonical memo"
    assert workflow.patch["agent_trace"]["authority_projection"]["canonical_workflow_state"] == "monitoring"


@pytest.mark.asyncio
async def test_projection_is_idempotent_and_never_writes_canonical_tables():
    legacy_repo = _LegacyRepository()
    projector = AuthorityProjectionConsumer(legacy_repo)
    event = event_for("recommendation.created", payload={"state": "insufficient_evidence"})

    first = await projector.apply(**event)
    second = await projector.apply(**event)

    assert first.receipt_id == second.receipt_id
    assert legacy_repo.patch["partner_info"]["recommendation"] == "MONITOR"
    assert legacy_repo.canonical_writes == []


@pytest.mark.asyncio
async def test_projection_rejects_cross_tenant_event_before_legacy_patch():
    legacy_repo = _LegacyRepository()
    projector = AuthorityProjectionConsumer(legacy_repo)
    event = event_for("recommendation.created", payload={"state": "advance", "user_id": "tenant-b"})

    with pytest.raises(ProjectionTenantMismatch):
        await projector.apply(**event)

    assert legacy_repo.patch == {}
    assert legacy_repo.receipts == {}


@pytest.mark.asyncio
async def test_emitted_evaluation_event_projects_a_valid_legacy_value_and_reason():
    legacy_repo = _LegacyRepository()
    projector = AuthorityProjectionConsumer(legacy_repo)
    event = event_for(
        "evaluation.completed",
        payload={
            "legacy_startup_id": "startup-a",
            "evaluation_id": str(uuid4()),
            "recommendation_id": str(uuid4()),
            "recommended_state": "insufficient_evidence",
            "compatibility_reason": "Evidence coverage below policy minimum.",
        },
    )

    receipt = await projector.apply(**event)

    assert receipt is not None
    assert legacy_repo.patch["review_info"]["canonical_evaluation_id"] == event["payload"]["evaluation_id"]
    assert legacy_repo.patch["review_info"]["canonical_evaluation_reason"] == "Evidence coverage below policy minimum."
    assert legacy_repo.patch["partner_info"]["recommendation"] == "MONITOR"
    assert legacy_repo.patch["partner_info"]["canonical_recommendation_state"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_replay_reapplies_one_event_or_pending_tenant_events():
    legacy_repo = _LegacyRepository()
    projector = AuthorityProjectionConsumer(legacy_repo)
    first = SimpleNamespace(**event_for("recommendation.created", payload={"state": "advance"}))
    second = SimpleNamespace(**event_for("human_ruling.created", payload={"decision": "monitor"}))
    legacy_repo.events = [first, second]

    assert await projector.replay(user_id="tenant-a", event_id=first.event_id) == 1
    assert await projector.replay(user_id="tenant-a") == 1
    assert len(legacy_repo.receipts) == 2
