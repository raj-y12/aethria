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
