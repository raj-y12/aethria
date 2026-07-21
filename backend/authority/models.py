"""Strict tenant-scoped contracts for the authority-control rollout."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from tenant_context import require_user_id
from utils.timeutil import utcnow


class RolloutMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    BACKFILL = "backfill"
    CANONICAL_WRITE = "canonical_write"
    CANONICAL_READ = "canonical_read"


class WorkflowState(str, Enum):
    ADMITTED = "admitted"
    IDENTITY_REVIEW = "identity_review"
    TRIAGE_PENDING = "triage_pending"
    TRIAGED_LIGHT = "triaged_light"
    DEEP_REVIEW_PENDING = "deep_review_pending"
    EVIDENCE_ACTIVE = "evidence_active"
    EVALUATION_PENDING = "evaluation_pending"
    RULING_PENDING = "ruling_pending"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class BlockCode(str, Enum):
    IDENTITY_REVIEW_REQUIRED = "identity_review_required"
    THESIS_REQUIRED = "thesis_required"
    POLICY_REQUIRED = "policy_required"
    EVIDENCE_REQUIRED = "evidence_required"
    EVALUATION_REQUIRED = "evaluation_required"
    RULING_REQUIRED = "ruling_required"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    KILL_SWITCH_ACTIVE = "kill_switch_active"


class _TenantModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str) -> str:
        try:
            return require_user_id(value, context=cls.__name__)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class _WorkflowBlockModel(_TenantModel):
    state: WorkflowState
    block_code: Optional[BlockCode] = None
    block_detail: Optional[str] = Field(default=None, max_length=2000)
    block_recovery: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("block_detail", "block_recovery")
    @classmethod
    def _normalize_optional_block_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def _validate_block_shape(self) -> "_WorkflowBlockModel":
        block_fields = (self.block_code, self.block_detail, self.block_recovery)
        if self.state is WorkflowState.BLOCKED:
            if any(value is None for value in block_fields):
                raise ValueError(
                    "blocked workflow state requires block_code, block_detail, and block_recovery"
                )
        elif any(value is not None for value in block_fields):
            raise ValueError("non-blocked workflow state cannot carry block metadata")
        return self


class RolloutRecord(_TenantModel):
    mode: RolloutMode
    version: StrictInt = Field(ge=0)
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = Field(default=None, max_length=300)
    snapshot_id: Optional[str] = Field(default=None, max_length=300)
    last_reconciliation_status: Optional[str] = Field(default=None, max_length=120)
    kill_switch: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class WorkflowStateRecord(_WorkflowBlockModel):
    opportunity_id: UUID
    version: StrictInt = Field(ge=0)
    last_transition_id: Optional[UUID] = None
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("opportunity_id", "last_transition_id", mode="before")
    @classmethod
    def _normalize_uuid_keys(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class WorkflowTransition(_WorkflowBlockModel):
    expected_version: StrictInt = Field(ge=0)
    transition_id: UUID = Field(default_factory=uuid4)

    @field_validator("transition_id", mode="before")
    @classmethod
    def _normalize_transition_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ProjectionReceipt(_TenantModel):
    receipt_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    consumer: str = Field(min_length=1, max_length=300)
    aggregate_type: str = Field(min_length=1, max_length=160)
    aggregate_id: UUID
    applied_at: datetime = Field(default_factory=utcnow)
    projection_hash: Optional[str] = Field(default=None, max_length=300)

    @field_validator("receipt_id", "event_id", "aggregate_id", mode="before")
    @classmethod
    def _normalize_uuid_keys(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("consumer", "aggregate_type")
    @classmethod
    def _normalize_required_text_keys(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("authority receipt keys must be nonblank")
        return normalized
