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
            {"opportunity_id": "opportunity-a", "state": "admitted", "version": 0},
        ),
        (
            WorkflowTransition,
            {"state": "triage_pending", "expected_version": 1},
        ),
        (
            ProjectionReceipt,
            {
                "event_id": "event-a",
                "consumer": "legacy_projection",
                "aggregate_type": "opportunity",
                "aggregate_id": "opportunity-a",
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
            opportunity_id="opportunity-a",
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
            opportunity_id="opportunity-a",
            state="admitted",
            version=0,
            block_code=BlockCode.EVIDENCE_REQUIRED,
            block_detail="This must not be present.",
            block_recovery="Clear the block.",
        )
