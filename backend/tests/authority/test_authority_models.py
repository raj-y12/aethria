from uuid import UUID

import pytest
from pydantic import ValidationError

from authority.models import (
    BlockCode,
    ProjectionReceipt,
    RolloutMode,
    RolloutRecord,
    WorkflowState,
    WorkflowStateRecord,
    WorkflowTransition,
)


OPPORTUNITY_ID = "efbaef79-bbbd-44ff-b6e7-b52c7fdc0d76"
EVENT_ID = "e8d1ac39-6f4e-459c-8c4b-f938cf93e407"
AGGREGATE_ID = "5291d97e-1ec7-4e99-8684-7cf32a9b9b48"
RECEIPT_ID = "d653d2d3-9573-47ea-9b09-ff3c9e1ac974"
TRANSITION_ID = "3b2a1f50-d622-4ff6-af68-6f5ed6dc3e31"


def test_rollout_modes_and_workflow_states_are_closed_sets():
    assert [mode.value for mode in RolloutMode] == [
        "legacy",
        "shadow",
        "backfill",
        "canonical_write",
        "canonical_read",
    ]
    assert WorkflowState("triage_pending") is WorkflowState.TRIAGE_PENDING
    with pytest.raises(ValueError):
        WorkflowState("invested")


def test_tenant_scoped_authority_records_reject_blank_tenant():
    for model, values in (
        (RolloutRecord, {"mode": "legacy", "version": 0}),
        (
            WorkflowStateRecord,
            {"opportunity_id": OPPORTUNITY_ID, "state": "admitted", "version": 0},
        ),
        (
            WorkflowTransition,
            {"state": "triage_pending", "expected_version": 1},
        ),
        (
            ProjectionReceipt,
            {
                "event_id": EVENT_ID,
                "consumer": "legacy_projection",
                "aggregate_type": "opportunity",
                "aggregate_id": AGGREGATE_ID,
            },
        ),
    ):
        with pytest.raises(ValidationError):
            model(user_id=" ", **values)


def test_models_reject_unknown_mode_workflow_state_and_block_code():
    with pytest.raises(ValidationError):
        RolloutRecord(user_id="tenant-a", mode="unsafe", version=0)
    with pytest.raises(ValidationError):
        WorkflowStateRecord(
            user_id="tenant-a",
            opportunity_id=OPPORTUNITY_ID,
            state="invested",
            version=0,
        )
    with pytest.raises(ValidationError):
        WorkflowTransition(
            user_id="tenant-a",
            state="blocked",
            expected_version=1,
            block_code="unrecognized_block",
            block_detail="A reason",
            block_recovery="A recovery path",
        )


def test_blocked_workflow_requires_code_detail_and_recovery():
    with pytest.raises(ValidationError):
        WorkflowTransition(user_id="tenant-a", state="blocked", expected_version=1)

    transition = WorkflowTransition(
        user_id="tenant-a",
        state=WorkflowState.BLOCKED,
        expected_version=1,
        block_code=BlockCode.EVIDENCE_REQUIRED,
        block_detail="Verified evidence is required before review.",
        block_recovery="Collect and attach verified evidence.",
    )

    assert transition.block_code is BlockCode.EVIDENCE_REQUIRED


def test_non_blocked_workflow_cannot_carry_block_metadata():
    with pytest.raises(ValidationError):
        WorkflowStateRecord(
            user_id="tenant-a",
            opportunity_id=OPPORTUNITY_ID,
            state="admitted",
            version=0,
            block_code=BlockCode.EVIDENCE_REQUIRED,
            block_detail="This must not be present.",
            block_recovery="Clear the block.",
        )


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (
            WorkflowStateRecord,
            {
                "user_id": "tenant-a",
                "opportunity_id": "not-a-uuid",
                "state": "admitted",
                "version": 0,
            },
        ),
        (
            WorkflowStateRecord,
            {
                "user_id": "tenant-a",
                "opportunity_id": OPPORTUNITY_ID,
                "state": "admitted",
                "version": 0,
                "last_transition_id": "not-a-uuid",
            },
        ),
        (
            WorkflowTransition,
            {
                "user_id": "tenant-a",
                "state": "admitted",
                "expected_version": 0,
                "transition_id": "not-a-uuid",
            },
        ),
        (
            ProjectionReceipt,
            {
                "user_id": "tenant-a",
                "receipt_id": "not-a-uuid",
                "event_id": EVENT_ID,
                "consumer": "legacy_projection",
                "aggregate_type": "opportunity",
                "aggregate_id": AGGREGATE_ID,
            },
        ),
        (
            ProjectionReceipt,
            {
                "user_id": "tenant-a",
                "event_id": "not-a-uuid",
                "consumer": "legacy_projection",
                "aggregate_type": "opportunity",
                "aggregate_id": AGGREGATE_ID,
            },
        ),
        (
            ProjectionReceipt,
            {
                "user_id": "tenant-a",
                "event_id": EVENT_ID,
                "consumer": "legacy_projection",
                "aggregate_type": "opportunity",
                "aggregate_id": "not-a-uuid",
            },
        ),
    ],
)
def test_uuid_backed_authority_fields_reject_invalid_values(model, values):
    with pytest.raises(ValidationError):
        model(**values)


def test_uuid_backed_fields_use_uuid_values_and_uuid_defaults():
    transition = WorkflowTransition(
        user_id="tenant-a", state="admitted", expected_version=0
    )
    receipt = ProjectionReceipt(
        user_id="tenant-a",
        event_id=EVENT_ID,
        consumer="legacy_projection",
        aggregate_type="opportunity",
        aggregate_id=AGGREGATE_ID,
    )
    record = WorkflowStateRecord(
        user_id="tenant-a",
        opportunity_id=OPPORTUNITY_ID,
        state="admitted",
        version=0,
        last_transition_id=TRANSITION_ID,
    )

    assert isinstance(transition.transition_id, UUID)
    assert isinstance(receipt.receipt_id, UUID)
    assert isinstance(receipt.event_id, UUID)
    assert isinstance(receipt.aggregate_id, UUID)
    assert isinstance(record.opportunity_id, UUID)
    assert isinstance(record.last_transition_id, UUID)


def test_authority_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        RolloutRecord(
            user_id="tenant-a", mode="legacy", version=0, untrusted="ignored-before"
        )


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (RolloutRecord, {"user_id": "tenant-a", "mode": "legacy", "version": "1"}),
        (
            WorkflowStateRecord,
            {
                "user_id": "tenant-a",
                "opportunity_id": OPPORTUNITY_ID,
                "state": "admitted",
                "version": "1",
            },
        ),
        (
            WorkflowTransition,
            {
                "user_id": "tenant-a",
                "state": "admitted",
                "expected_version": "1",
            },
        ),
    ],
)
def test_authority_versions_do_not_coerce_strings_to_integers(model, values):
    with pytest.raises(ValidationError):
        model(**values)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("receipt_id", f"  {RECEIPT_ID}  ", UUID(RECEIPT_ID)),
        ("event_id", f"  {EVENT_ID}  ", UUID(EVENT_ID)),
        ("consumer", "  legacy_projection  ", "legacy_projection"),
        ("aggregate_type", "  opportunity  ", "opportunity"),
        ("aggregate_id", f"  {AGGREGATE_ID}  ", UUID(AGGREGATE_ID)),
    ],
)
def test_projection_receipt_normalizes_and_rejects_blank_identity_keys(
    field, value, expected
):
    values = {
        "user_id": "tenant-a",
        "receipt_id": RECEIPT_ID,
        "event_id": EVENT_ID,
        "consumer": "  legacy_projection  ",
        "aggregate_type": "  opportunity  ",
        "aggregate_id": AGGREGATE_ID,
    }
    values[field] = value
    receipt = ProjectionReceipt(**values)
    assert getattr(receipt, field) == expected

    values[field] = "   "
    with pytest.raises(ValidationError):
        ProjectionReceipt(**values)
