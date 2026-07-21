"""Pydantic contracts for durable agent jobs, checkpoints, and outbox events."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


def _validated_user_id(value: str, *, context: str) -> str:
    try:
        return require_user_id(value, context=context)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc


class JobExecutionCancelled(RuntimeError):
    """Cooperative stop observed between durable execution checkpoints."""


class JobLeaseLost(RuntimeError):
    """The executing worker no longer owns the durable job lease."""


class JobExecutionBlocked(RuntimeError):
    """Execution cannot continue until an explicit operator action is complete."""

    def __init__(
        self,
        *,
        code: str,
        detail: str,
        recovery_action: str,
        lookup_outcome: Any = None,
    ):
        normalized_code = str(code or "").strip().lower()
        if not normalized_code or not normalized_code.replace("_", "a").isalnum():
            raise ValueError("blocked job code must be lowercase snake_case")
        self.code = normalized_code[:80]
        self.detail = str(detail or "").strip()[:1000]
        self.recovery_action = str(recovery_action or "").strip()[:1000]
        self.lookup_outcome = lookup_outcome
        if not self.recovery_action:
            raise ValueError("blocked job recovery_action is required")
        super().__init__(f"{self.code}: {self.detail or self.recovery_action}")


class JobType(str, Enum):
    PIPELINE_CYCLE = "pipeline_cycle"
    COMPANY_LOOKUP = "company_lookup"
    EVIDENCE_REFRESH = "evidence_refresh"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class CheckpointStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class _TenantPayload(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def _valid_user_id(cls, value: str) -> str:
        return _validated_user_id(value, context=cls.__name__)


class PipelineCyclePayload(_TenantPayload):
    manual_one_shot: bool = False
    source: str = "scheduled_loop"


class CompanyLookupPayload(_TenantPayload):
    company_name: str = Field(min_length=1)
    website: Optional[str] = None
    lookup_query: Optional[str] = None
    lookup_input_type: Optional[str] = None
    lookup_id: Optional[str] = None
    additional_context: Optional[str] = None
    replace_startup_id: Optional[str] = None
    resolution: Optional[Dict[str, Any]] = None

    @field_validator("company_name")
    @classmethod
    def _company_required(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("company_name is required")
        return normalized


class EvidenceRefreshPayload(_TenantPayload):
    opportunity_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    budget_reservation_id: str = Field(min_length=1)
    evidence_plan_id: Optional[str] = None


JobPayload = Union[PipelineCyclePayload, CompanyLookupPayload, EvidenceRefreshPayload]


class AgentJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    job_type: JobType
    idempotency_key: str = Field(min_length=1)
    payload: JobPayload
    status: JobStatus = JobStatus.QUEUED
    priority: int = 0
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    next_attempt_at: datetime = Field(default_factory=utcnow)
    pipeline_run_id: str = Field(default_factory=lambda: str(uuid4()))
    last_error: Optional[str] = None
    block_code: Optional[str] = None
    block_detail: Optional[str] = None
    recovery_action: Optional[str] = None
    accepted_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="before")
    @classmethod
    def _parse_payload_for_job_type(cls, data):
        if not isinstance(data, dict):
            return data
        payload = data.get("payload")
        if not isinstance(payload, dict):
            return data
        kind = getattr(data.get("job_type"), "value", data.get("job_type"))
        model = {
            JobType.PIPELINE_CYCLE.value: PipelineCyclePayload,
            JobType.COMPANY_LOOKUP.value: CompanyLookupPayload,
            JobType.EVIDENCE_REFRESH.value: EvidenceRefreshPayload,
        }.get(str(kind))
        if model is not None:
            data = dict(data)
            data["payload"] = model.model_validate(payload)
        return data

    @field_validator("user_id")
    @classmethod
    def _valid_user_id(cls, value: str) -> str:
        return _validated_user_id(value, context="AgentJob")

    @field_validator("idempotency_key")
    @classmethod
    def _valid_idempotency_key(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("idempotency_key is required")
        return normalized

    @model_validator(mode="after")
    def _payload_matches_job(self):
        if self.payload.user_id != self.user_id:
            raise ValueError("payload tenant does not match job tenant")
        if self.job_type is JobType.PIPELINE_CYCLE and not isinstance(
            self.payload, PipelineCyclePayload
        ):
            raise ValueError("payload type does not match pipeline_cycle")
        if self.job_type is JobType.COMPANY_LOOKUP and not isinstance(
            self.payload, CompanyLookupPayload
        ):
            raise ValueError("payload type does not match company_lookup")
        if self.job_type is JobType.EVIDENCE_REFRESH and not isinstance(
            self.payload, EvidenceRefreshPayload
        ):
            raise ValueError("payload type does not match evidence_refresh")
        if self.attempts > self.max_attempts:
            raise ValueError("attempts cannot exceed max_attempts")
        return self


class JobCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    user_id: str
    pipeline_run_id: str
    stage: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    status: CheckpointStatus
    output_metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("user_id")
    @classmethod
    def _valid_user_id(cls, value: str) -> str:
        return _validated_user_id(value, context="JobCheckpoint")


class DomainOutboxEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    aggregate_type: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_version: int = Field(default=1, ge=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    publication_attempts: int = Field(default=0, ge=0)
    next_attempt_at: datetime = Field(default_factory=utcnow)
    published_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("user_id")
    @classmethod
    def _valid_user_id(cls, value: str) -> str:
        return _validated_user_id(value, context="DomainOutboxEvent")
