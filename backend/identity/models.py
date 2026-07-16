"""Pydantic contracts for canonical identity, observations, and opportunities."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


def _tenant(value: str, *, context: str) -> str:
    try:
        return require_user_id(value, context=context)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc


class SourceChannel(str, Enum):
    MANUAL_LOOKUP = "manual_lookup"
    AUTONOMOUS_DISCOVERY = "autonomous_discovery"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    REFERRAL = "referral"
    EVENT = "event"
    PORTFOLIO_INTRO = "portfolio_intro"
    IMPORT = "import"
    CRM_IMPORT = "crm_import"
    BACKFILL = "backfill"


class IdentityStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class IdentityCaseStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class IdentifierType(str, Enum):
    DOMAIN = "domain"
    LINKEDIN = "linkedin"
    CRUNCHBASE = "crunchbase"
    DEALROOM = "dealroom"
    YC = "yc"
    REGISTRY = "registry"
    EXTERNAL = "external"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REVOKED = "revoked"


class OpportunityState(str, Enum):
    DISCOVERED = "discovered"
    IDENTITY_REVIEW = "identity_review"
    ACTIVE_REVIEW = "active_review"
    MONITOR = "monitor"
    ADVANCE = "advance"
    PASS = "pass"
    INVESTED = "invested"
    ARCHIVED = "archived"


class _TenantModel(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def _valid_user(cls, value: str) -> str:
        return _tenant(value, context=cls.__name__)


class SourceObservationInput(_TenantModel):
    channel: SourceChannel
    observed_name: str = Field(min_length=1, max_length=300)
    observed_domain: Optional[str] = None
    provider_identifiers: Dict[str, str] = Field(default_factory=dict)
    external_event_key: Optional[str] = Field(default=None, max_length=500)
    lookup_id: Optional[str] = None
    legacy_startup_id: Optional[str] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    resolution_payload: Optional[Dict[str, Any]] = None
    opportunity_context_key: str = Field(default="primary", min_length=1, max_length=160)
    observed_at: datetime = Field(default_factory=utcnow)

    @field_validator("observed_name")
    @classmethod
    def _name_required(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("observed_name is required")
        return normalized

    @field_validator("external_event_key", "lookup_id", "legacy_startup_id")
    @classmethod
    def _optional_text(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None


class NormalizedIdentifier(BaseModel):
    identifier_type: IdentifierType
    normalized_value: str = Field(min_length=1, max_length=500)
    raw_value: str = Field(min_length=1, max_length=1000)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_primary: bool = False


class IdentityCandidate(BaseModel):
    company_id: Optional[str] = None
    canonical_name: str = Field(min_length=1, max_length=300)
    canonical_domain: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_identifiers: List[NormalizedIdentifier] = Field(default_factory=list)
    evidence_urls: List[str] = Field(default_factory=list)
    reason: str = ""


class IdentityAdmission(_TenantModel):
    observation_id: str
    status: IdentityStatus
    company_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    identity_case_id: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_identifier: Optional[NormalizedIdentifier] = None
    blocks_evaluation: bool = False
    candidates: List[IdentityCandidate] = Field(default_factory=list)
    created: bool = False


class CompanyRecord(_TenantModel):
    company_id: str = Field(default_factory=lambda: str(uuid4()))
    canonical_name: str
    canonical_domain: Optional[str] = None
    identity_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CompanyIdentifierRecord(_TenantModel):
    identifier_id: str = Field(default_factory=lambda: str(uuid4()))
    company_id: str
    identifier_type: IdentifierType
    normalized_value: str
    raw_value: str
    verification_status: VerificationStatus
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_primary: bool = False
    source_observation_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class SourceObservationRecord(_TenantModel):
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    channel: SourceChannel
    observed_name: str
    observed_domain: Optional[str] = None
    external_event_key: Optional[str] = None
    lookup_id: Optional[str] = None
    legacy_startup_id: Optional[str] = None
    company_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    identity_status: IdentityStatus = IdentityStatus.PENDING
    identity_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    resolution_payload: Optional[Dict[str, Any]] = None
    observed_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OpportunityRecord(_TenantModel):
    opportunity_id: str = Field(default_factory=lambda: str(uuid4()))
    company_id: str
    context_key: str = "primary"
    decision_state: OpportunityState = OpportunityState.DISCOVERED
    service_level: int = Field(default=1, ge=0, le=5)
    first_observation_id: str
    latest_observation_id: str
    legacy_startup_id: Optional[str] = None
    current_evaluation_id: Optional[str] = None
    current_recommendation_id: Optional[str] = None
    current_ruling_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class IdentityResolutionCaseRecord(_TenantModel):
    identity_case_id: str = Field(default_factory=lambda: str(uuid4()))
    observation_id: str
    status: IdentityCaseStatus = IdentityCaseStatus.OPEN
    reason_code: str
    candidates: List[IdentityCandidate] = Field(default_factory=list)
    selected_company_id: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
