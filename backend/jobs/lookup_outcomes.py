"""Single durable authority for tenant-scoped lookup attempt outcomes."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from jobs.models import AgentJob, JobStatus
from pipeline_execution import (
    LookupExecutionStatus,
    PipelineExecutionResult,
    PipelineExecutionState,
)
from tenant_context import require_user_id
from utils.timeutil import utcnow


class LookupOutcomeStoreUnavailable(RuntimeError):
    """The durable lookup outcome authority could not be read or written."""


class LookupOutcomeCorrupt(RuntimeError):
    """A lookup outcome exists but does not satisfy the governed contract."""


class LookupAttemptDisposition(str, Enum):
    ACCEPTED = "accepted"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


def lookup_attempt_id(
    *,
    user_id: str,
    lookup_id: str,
    job_id: str,
    pipeline_run_id: str,
    attempt: int,
) -> str:
    """Build the stable storage key for one exact execution attempt."""
    uid = require_user_id(user_id, context="lookup_attempt_id")
    parts = (
        uid,
        str(lookup_id or "").strip(),
        str(job_id or "").strip(),
        str(pipeline_run_id or "").strip(),
        str(int(attempt)),
    )
    if any(not part for part in parts):
        raise ValueError("lookup attempt identity fields are required")
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"lookup-attempt-{digest}"


def planned_attempt_for_job(job: AgentJob) -> int:
    """Return the monotonic attempt represented by the job's current state."""
    if job.status is JobStatus.QUEUED:
        return max(1, job.attempts + 1)
    return max(1, job.attempts)


class LookupAttemptOutcome(BaseModel):
    """Latest lifecycle state for one exact durable lookup attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    lookup_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    pipeline_run_id: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    status: LookupExecutionStatus
    disposition: LookupAttemptDisposition
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    detail: str = Field(min_length=1, max_length=500)
    recovery_action: Optional[str] = Field(default=None, max_length=500)
    failed_stage: Optional[str] = Field(default=None, max_length=100)
    startup_id: Optional[str] = Field(default=None, max_length=200)
    recorded_at: datetime = Field(default_factory=utcnow)

    @field_validator("user_id")
    @classmethod
    def _valid_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context="LookupAttemptOutcome")
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("lookup_id", "job_id", "pipeline_run_id")
    @classmethod
    def _normalized_identity(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("lookup attempt identity fields are required")
        return normalized

    @field_serializer("recorded_at")
    def _serialize_recorded_at(self, value: datetime) -> str:
        return value.isoformat()

    @model_validator(mode="after")
    def _validate_binding_and_state(self) -> "LookupAttemptOutcome":
        expected_id = lookup_attempt_id(
            user_id=self.user_id,
            lookup_id=self.lookup_id,
            job_id=self.job_id,
            pipeline_run_id=self.pipeline_run_id,
            attempt=self.attempt,
        )
        if self.id != expected_id:
            raise ValueError("lookup outcome id does not match its attempt identity")
        allowed = {
            LookupAttemptDisposition.ACCEPTED: {LookupExecutionStatus.ACCEPTED},
            LookupAttemptDisposition.SUCCEEDED: {
                LookupExecutionStatus.COMPLETED,
                LookupExecutionStatus.ALREADY_IN_DEAL_FLOW,
            },
            LookupAttemptDisposition.BLOCKED: {LookupExecutionStatus.BLOCKED},
            LookupAttemptDisposition.SKIPPED: {LookupExecutionStatus.SKIPPED},
            LookupAttemptDisposition.CANCELLED: {LookupExecutionStatus.SKIPPED},
            LookupAttemptDisposition.RETRYABLE_FAILURE: {
                LookupExecutionStatus.FAILED,
                LookupExecutionStatus.FAILED_STAGE,
            },
            LookupAttemptDisposition.TERMINAL_FAILURE: {
                LookupExecutionStatus.FAILED,
                LookupExecutionStatus.FAILED_STAGE,
            },
        }
        if self.status not in allowed[self.disposition]:
            raise ValueError("lookup status is incompatible with attempt disposition")
        if self.disposition in {
            LookupAttemptDisposition.BLOCKED,
            LookupAttemptDisposition.RETRYABLE_FAILURE,
            LookupAttemptDisposition.TERMINAL_FAILURE,
        } and not str(self.recovery_action or "").strip():
            raise ValueError("blocked and failed outcomes require recovery_action")
        if self.status is LookupExecutionStatus.FAILED_STAGE and not self.failed_stage:
            raise ValueError("failed-stage lookup outcomes require failed_stage")
        return self

    @property
    def terminal(self) -> bool:
        return self.disposition not in {
            LookupAttemptDisposition.ACCEPTED,
            LookupAttemptDisposition.RETRYABLE_FAILURE,
        }

    @property
    def failed(self) -> bool:
        return self.disposition in {
            LookupAttemptDisposition.BLOCKED,
            LookupAttemptDisposition.TERMINAL_FAILURE,
        }

    @classmethod
    def _for_job(
        cls,
        job: AgentJob,
        *,
        status: LookupExecutionStatus,
        disposition: LookupAttemptDisposition,
        code: str,
        detail: str,
        recovery_action: Optional[str] = None,
        failed_stage: Optional[str] = None,
        startup_id: Optional[str] = None,
        attempt: Optional[int] = None,
    ) -> "LookupAttemptOutcome":
        lookup_id = str(getattr(job.payload, "lookup_id", None) or job.job_id).strip()
        resolved_attempt = attempt or planned_attempt_for_job(job)
        return cls(
            id=lookup_attempt_id(
                user_id=job.user_id,
                lookup_id=lookup_id,
                job_id=job.job_id,
                pipeline_run_id=job.pipeline_run_id,
                attempt=resolved_attempt,
            ),
            user_id=job.user_id,
            lookup_id=lookup_id,
            job_id=job.job_id,
            pipeline_run_id=job.pipeline_run_id,
            attempt=resolved_attempt,
            status=status,
            disposition=disposition,
            code=code,
            detail=str(detail or "").strip()[:500],
            recovery_action=(str(recovery_action).strip()[:500] if recovery_action else None),
            failed_stage=(str(failed_stage).strip()[:100] if failed_stage else None),
            startup_id=(str(startup_id).strip()[:200] if startup_id else None),
        )

    @classmethod
    def accepted_for_job(cls, job: AgentJob) -> "LookupAttemptOutcome":
        return cls._for_job(
            job,
            status=LookupExecutionStatus.ACCEPTED,
            disposition=LookupAttemptDisposition.ACCEPTED,
            code="lookup_attempt_accepted",
            detail="Lookup attempt accepted for execution.",
        )

    @classmethod
    def from_pipeline_result(
        cls, job: AgentJob, result: PipelineExecutionResult
    ) -> "LookupAttemptOutcome":
        raw_status = result.metadata.get("lookup_status")
        try:
            status = LookupExecutionStatus(str(raw_status)) if raw_status else LookupExecutionStatus(result.state.value)
        except ValueError:
            status = LookupExecutionStatus(result.state.value)
        if result.state is PipelineExecutionState.COMPLETED:
            disposition = LookupAttemptDisposition.SUCCEEDED
        elif result.state is PipelineExecutionState.BLOCKED:
            disposition = LookupAttemptDisposition.BLOCKED
        elif result.state is PipelineExecutionState.SKIPPED:
            disposition = (
                LookupAttemptDisposition.CANCELLED
                if result.code == "lookup_cancelled"
                else LookupAttemptDisposition.SKIPPED
            )
        else:
            disposition = (
                LookupAttemptDisposition.TERMINAL_FAILURE
                if job.attempts >= job.max_attempts
                else LookupAttemptDisposition.RETRYABLE_FAILURE
            )
        return cls._for_job(
            job,
            attempt=max(1, job.attempts),
            status=status,
            disposition=disposition,
            code=result.code,
            detail=result.detail,
            recovery_action=result.recovery_action,
            failed_stage=result.failed_stage,
            startup_id=result.startup_id,
        )

    @classmethod
    def blocked_for_job(
        cls, job: AgentJob, *, code: str, detail: str, recovery_action: str
    ) -> "LookupAttemptOutcome":
        return cls._for_job(
            job,
            attempt=max(1, job.attempts),
            status=LookupExecutionStatus.BLOCKED,
            disposition=LookupAttemptDisposition.BLOCKED,
            code=code,
            detail=detail,
            recovery_action=recovery_action,
        )

    @classmethod
    def cancelled_for_job(cls, job: AgentJob, *, detail: str) -> "LookupAttemptOutcome":
        return cls._for_job(
            job,
            attempt=planned_attempt_for_job(job),
            status=LookupExecutionStatus.SKIPPED,
            disposition=LookupAttemptDisposition.CANCELLED,
            code="lookup_cancelled",
            detail=detail,
        )

    @classmethod
    def failed_for_job(
        cls, job: AgentJob, *, detail: str, recovery_action: str
    ) -> "LookupAttemptOutcome":
        disposition = (
            LookupAttemptDisposition.TERMINAL_FAILURE
            if job.attempts >= job.max_attempts
            else LookupAttemptDisposition.RETRYABLE_FAILURE
        )
        return cls._for_job(
            job,
            attempt=max(1, job.attempts),
            status=LookupExecutionStatus.FAILED,
            disposition=disposition,
            code="lookup_attempt_failed",
            detail=detail,
            recovery_action=recovery_action,
        )

    @classmethod
    def lease_expired_for_job(cls, job: AgentJob) -> "LookupAttemptOutcome":
        terminal = job.attempts >= job.max_attempts
        return cls._for_job(
            job,
            attempt=max(1, job.attempts),
            status=LookupExecutionStatus.FAILED,
            disposition=(
                LookupAttemptDisposition.TERMINAL_FAILURE
                if terminal
                else LookupAttemptDisposition.RETRYABLE_FAILURE
            ),
            code="lookup_attempt_lease_expired",
            detail=(
                "The worker lease expired after the final lookup attempt."
                if terminal
                else "The worker lease expired before the lookup attempt completed."
            ),
            recovery_action=(
                "Inspect worker health, then explicitly retry the lookup."
                if terminal
                else "The durable worker will retry this lookup attempt."
            ),
        )
