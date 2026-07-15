from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


class ImportSource(str, Enum):
    CSV = "csv"
    CRM_CSV = "crm_csv"
    EVENT_CSV = "event_csv"
    REFERRAL_CSV = "referral_csv"


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class ImportCandidate(BaseModel):
    row_number: int = Field(ge=2)
    row_key: str
    observed_name: str = Field(min_length=1, max_length=300)
    observed_domain: Optional[str] = Field(default=None, max_length=500)
    external_id: Optional[str] = Field(default=None, max_length=500)
    source: ImportSource
    import_id: str
    operator_confirmed_identity: bool = False


class OutcomeType(str, Enum):
    FINANCING = "financing"
    REVENUE_MILESTONE = "revenue_milestone"
    CUSTOMER_MILESTONE = "customer_milestone"
    PRODUCT_LAUNCH = "product_launch"
    ACQUISITION = "acquisition"
    SHUTDOWN = "shutdown"
    LEADERSHIP_CHANGE = "leadership_change"
    FOLLOW_ON_DECISION = "follow_on_decision"
    OTHER = "other"


class OutcomeValence(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class OutcomeVerification(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"


class OutcomeInput(BaseModel):
    user_id: str
    company_id: str
    opportunity_id: Optional[str] = None
    outcome_type: OutcomeType
    valence: OutcomeValence
    summary: str = Field(min_length=3, max_length=2000)
    verification_state: OutcomeVerification = OutcomeVerification.UNVERIFIED
    materiality: int = Field(ge=1, le=5)
    effective_at: Optional[datetime] = None
    observed_at: datetime = Field(default_factory=utcnow)
    evidence_artifact_ids: List[str] = Field(default_factory=list, max_length=20)
    supersedes_outcome_id: Optional[str] = None

    @field_validator("user_id")
    @classmethod
    def valid_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context="OutcomeInput")
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class OutcomeRecord(OutcomeInput):
    outcome_observation_id: str = Field(default_factory=lambda: str(uuid4()))
    recorded_by: str
    created_at: datetime = Field(default_factory=utcnow)
