from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator
from tenant_context import require_user_id


class TriageDisposition(str, Enum):
    DEEP_REVIEW = "deep_review"
    LIGHT_MONITOR = "light_monitor"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OUT_OF_MANDATE = "out_of_mandate"
    ARCHIVE_CANDIDATE = "archive_candidate"


class TriageAssessment(BaseModel):
    assessment_id: str
    user_id: str
    opportunity_id: str
    disposition: TriageDisposition
    reasons: List[str] = Field(default_factory=list)
    observation_ids: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    thesis_version_id: str
    policy_version_id: str
    trigger: str
    priority: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)

    @field_validator("user_id")
    @classmethod
    def tenant(cls, value: str) -> str:
        return require_user_id(value, context="TriageAssessment")
