from datetime import datetime
from enum import Enum, IntEnum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


class ServiceLevel(IntEnum):
    ARCHIVE = 0
    DISCOVERED = 1
    ACTIVE_REVIEW = 2
    MONITOR = 3
    DILIGENCE = 4
    PORTFOLIO = 5


class RefreshReason(str, Enum):
    NEW_OBSERVATION = "new_observation"
    MISSING_POLICY_EVIDENCE = "missing_policy_evidence"
    STALE_DECISIVE_EVIDENCE = "stale_decisive_evidence"
    MONITOR_DUE = "monitor_due"
    VERIFIED_EXTERNAL_SIGNAL = "verified_external_signal"
    HUMAN_REQUEST = "human_request"
    POLICY_CHANGE = "policy_change"
    CLAIM_CORRECTION = "claim_correction"


class ReservationStatus(str, Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    EXPIRED = "expired"


class RefreshEnvelope(BaseModel):
    max_search_queries: int = Field(default=3, ge=0, le=100)
    max_artifacts: int = Field(default=5, ge=1, le=100)
    max_model_tokens: int = Field(default=12000, ge=0, le=1_000_000)
    estimated_cost_usd: float = Field(default=0.25, ge=0, le=10_000)
    # Default for NEW envelopes only. Existing rows still carry "tavily"; the
    # field is an unconstrained list, so they keep deserialising unchanged.
    providers: List[str] = Field(default_factory=lambda: ["exa", "openai"])
    deadline_at: Optional[datetime] = None

    @field_validator("providers")
    @classmethod
    def bounded_providers(cls, value: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(str(item).strip().lower() for item in value if str(item).strip()))
        if len(normalized) > 10:
            raise ValueError("providers cannot contain more than 10 entries")
        return normalized


class RefreshRequest(BaseModel):
    user_id: str
    opportunity_id: str = Field(min_length=1)
    reason: RefreshReason
    request_key: str = Field(min_length=8, max_length=200)
    envelope: RefreshEnvelope = Field(default_factory=RefreshEnvelope)

    @field_validator("user_id")
    @classmethod
    def valid_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context="RefreshRequest")
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class BudgetReservationRecord(BaseModel):
    budget_reservation_id: str
    user_id: str
    opportunity_id: str
    job_id: str
    reason: RefreshReason
    service_level: ServiceLevel
    max_search_queries: int
    max_artifacts: int
    max_model_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: Optional[float] = None
    providers: List[str] = Field(default_factory=list)
    deadline_at: Optional[datetime] = None
    status: ReservationStatus
    expires_at: datetime
    settled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
