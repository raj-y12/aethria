"""Typed terminal outcomes shared by every evaluation runner and boundary."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PipelineExecutionState(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED_STAGE = "failed_stage"


class StageExecutionState(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


class StageExecutionResult(BaseModel):
    """Lossless periodic-stage outcome; every eligible item is accounted for."""

    model_config = ConfigDict(frozen=True)

    stage: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    state: StageExecutionState
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    detail: str = Field(min_length=1)
    recovery_action: Optional[str] = None
    attempted: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    blocked: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_stage_outcome(self) -> "StageExecutionResult":
        accounted = self.succeeded + self.failed + self.blocked + self.skipped
        if accounted != self.attempted:
            raise ValueError("stage outcome counts must account for every attempt")
        if self.state in {StageExecutionState.BLOCKED, StageExecutionState.FAILED}:
            if not str(self.recovery_action or "").strip():
                raise ValueError("blocked and failed stage results require recovery_action")
        if self.state is StageExecutionState.COMPLETED:
            if self.failed or self.blocked or not self.succeeded:
                raise ValueError("completed stage results require only successful work")
        elif self.state is StageExecutionState.BLOCKED:
            if not self.blocked or self.succeeded or self.failed:
                raise ValueError("blocked stage results require fully blocked work")
        elif self.state is StageExecutionState.FAILED:
            if not self.failed and not (self.blocked and self.succeeded):
                raise ValueError("failed stage results require failed or partially blocked work")
        elif self.succeeded or self.failed or self.blocked:
            raise ValueError("skipped stage results cannot contain completed work")
        return self

    @classmethod
    def completed(
        cls,
        *,
        stage: str,
        code: str,
        detail: str,
        attempted: int,
        succeeded: int,
        skipped: int = 0,
    ) -> "StageExecutionResult":
        return cls(
            stage=stage,
            state=StageExecutionState.COMPLETED,
            code=code,
            detail=detail,
            attempted=attempted,
            succeeded=succeeded,
            skipped=skipped,
        )

    @classmethod
    def failed_result(
        cls,
        *,
        stage: str,
        code: str,
        detail: str,
        recovery_action: str,
        attempted: int,
        failed: int,
        succeeded: int = 0,
        blocked: int = 0,
        skipped: int = 0,
    ) -> "StageExecutionResult":
        return cls(
            stage=stage,
            state=StageExecutionState.FAILED,
            code=code,
            detail=detail,
            recovery_action=recovery_action,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            blocked=blocked,
            skipped=skipped,
        )

    @classmethod
    def blocked_result(
        cls,
        *,
        stage: str,
        code: str,
        detail: str,
        recovery_action: str,
        attempted: int,
        blocked: int,
        skipped: int = 0,
    ) -> "StageExecutionResult":
        return cls(
            stage=stage,
            state=StageExecutionState.BLOCKED,
            code=code,
            detail=detail,
            recovery_action=recovery_action,
            attempted=attempted,
            blocked=blocked,
            skipped=skipped,
        )

    @classmethod
    def skipped_result(
        cls,
        *,
        stage: str,
        code: str,
        detail: str,
        attempted: int = 0,
        skipped: int = 0,
    ) -> "StageExecutionResult":
        return cls(
            stage=stage,
            state=StageExecutionState.SKIPPED,
            code=code,
            detail=detail,
            attempted=attempted,
            skipped=skipped,
        )


class PipelineExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: PipelineExecutionState
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    detail: str = Field(min_length=1)
    recovery_action: Optional[str] = None
    failed_stage: Optional[str] = None
    startup_id: Optional[str] = None
    projection_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "PipelineExecutionResult":
        if self.state in {
            PipelineExecutionState.BLOCKED,
            PipelineExecutionState.FAILED_STAGE,
        } and not str(self.recovery_action or "").strip():
            raise ValueError("blocked and failed-stage results require recovery_action")
        if (
            self.state is PipelineExecutionState.FAILED_STAGE
            and not str(self.failed_stage or "").strip()
        ):
            raise ValueError("failed-stage results require failed_stage")
        if (
            self.state is not PipelineExecutionState.FAILED_STAGE
            and self.failed_stage is not None
        ):
            raise ValueError("failed_stage is only valid for failed-stage results")
        return self

    @classmethod
    def completed(cls, *, code: str, detail: str, **payload: Any) -> "PipelineExecutionResult":
        return cls(state=PipelineExecutionState.COMPLETED, code=code, detail=detail, **payload)

    @classmethod
    def blocked(
        cls, *, code: str, detail: str, recovery_action: str, **payload: Any
    ) -> "PipelineExecutionResult":
        return cls(
            state=PipelineExecutionState.BLOCKED,
            code=code,
            detail=detail,
            recovery_action=recovery_action,
            **payload,
        )

    @classmethod
    def skipped(cls, *, code: str, detail: str, **payload: Any) -> "PipelineExecutionResult":
        return cls(state=PipelineExecutionState.SKIPPED, code=code, detail=detail, **payload)

    @classmethod
    def stage_failure(
        cls,
        *,
        stage: str,
        code: str,
        detail: str,
        recovery_action: str,
        **payload: Any,
    ) -> "PipelineExecutionResult":
        return cls(
            state=PipelineExecutionState.FAILED_STAGE,
            failed_stage=stage,
            code=code,
            detail=detail,
            recovery_action=recovery_action,
            **payload,
        )
