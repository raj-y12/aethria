"""Pydantic contracts for artifacts, evidence items, claims, and plans."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


class ArtifactType(str, Enum):
    WEB_PAGE = "web_page"
    DATABASE_RESPONSE = "database_response"
    PITCH_DECK = "pitch_deck"
    EMAIL = "email"
    INTERVIEW_NOTE = "interview_note"
    OPERATOR_CONTEXT = "operator_context"
    NEWS = "news"
    REGISTRY = "registry"
    CRM = "crm"
    OTHER = "other"


class TrustClass(str, Enum):
    OFFICIAL = "official"
    REGULATORY = "regulatory"
    INDEPENDENT = "independent"
    FOUNDER = "founder"
    OPERATOR = "operator"
    MODEL = "model"
    UNKNOWN = "unknown"


class AccessClass(str, Enum):
    PUBLIC = "public"
    TENANT_CONFIDENTIAL = "tenant_confidential"
    RESTRICTED = "restricted"


class AssertionClass(str, Enum):
    EXTERNALLY_VERIFIED = "externally_verified"
    FOUNDER_ASSERTED = "founder_asserted"
    OPERATOR_ASSERTED = "operator_asserted"
    MODEL_INFERRED = "model_inferred"
    CONFLICTED = "conflicted"
    UNVERIFIED = "unverified"


class ClaimStatus(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class EvidenceRelationship(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"
    PARTIALLY_ESTABLISHES = "partially_establishes"


class VerificationState(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REVOKED = "revoked"


class EvidencePlanStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class _TenantModel(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context=cls.__name__)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class EvidenceArtifactInput(_TenantModel):
    company_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    source_observation_id: Optional[str] = None
    artifact_type: ArtifactType
    source_uri: Optional[str] = Field(default=None, max_length=2000)
    title: Optional[str] = Field(default=None, max_length=500)
    content_hash: str = Field(min_length=8, max_length=200)
    storage_reference: Optional[str] = Field(default=None, max_length=2000)
    trust_class: TrustClass = TrustClass.UNKNOWN
    access_class: AccessClass = AccessClass.PUBLIC
    retention_policy: str = Field(default="standard", max_length=100)
    parser_version: Optional[str] = Field(default=None, max_length=100)
    untrusted_input: bool = True
    prompt_injection_detected: bool = False
    published_at: Optional[datetime] = None
    effective_at: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    retrieval_provider: Optional[str] = Field(default=None, max_length=100)
    retrieval_query: Optional[str] = Field(default=None, max_length=500)


class EvidenceItemInput(_TenantModel):
    item_type: str = Field(min_length=1, max_length=160)
    normalized_value: Dict[str, Any] = Field(default_factory=dict)
    display_excerpt: str = Field(min_length=1, max_length=2000)
    source_locator: Optional[str] = Field(default=None, max_length=500)
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verification_state: VerificationState = VerificationState.UNVERIFIED
    source_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extractor_version: Optional[str] = Field(default=None, max_length=100)
    operator_attribution: Optional[str] = Field(default=None, max_length=300)


class ClaimInput(_TenantModel):
    company_id: str
    opportunity_id: Optional[str] = None
    claim_type: str = Field(min_length=1, max_length=160)
    normalized_value: Dict[str, Any] = Field(default_factory=dict)
    unit: Optional[str] = Field(default=None, max_length=80)
    period: Optional[str] = Field(default=None, max_length=160)
    display_text: str = Field(min_length=1, max_length=2000)
    assertion_class: AssertionClass
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    material: bool = True
    operator_attribution: Optional[str] = Field(default=None, max_length=300)
    supersedes_claim_id: Optional[str] = None


class ClaimEvidenceLinkInput(_TenantModel):
    evidence_item_id: str
    relationship: EvidenceRelationship
    support_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=1000)


class EvidenceArtifactRecord(EvidenceArtifactInput):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utcnow)


class EvidenceItemRecord(EvidenceItemInput):
    evidence_item_id: str = Field(default_factory=lambda: str(uuid4()))
    artifact_id: str
    created_at: datetime = Field(default_factory=utcnow)


class ClaimRecord(ClaimInput):
    claim_id: str = Field(default_factory=lambda: str(uuid4()))
    status: ClaimStatus = ClaimStatus.CURRENT
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ClaimEvidenceLinkRecord(ClaimEvidenceLinkInput):
    link_id: str = Field(default_factory=lambda: str(uuid4()))
    claim_id: str
    created_at: datetime = Field(default_factory=utcnow)


class EvidencePlanRecord(_TenantModel):
    evidence_plan_id: str = Field(default_factory=lambda: str(uuid4()))
    opportunity_id: str
    trigger_type: str
    status: EvidencePlanStatus = EvidencePlanStatus.PLANNED
    missing_evidence: List[str] = Field(default_factory=list)
    search_questions: List[str] = Field(default_factory=list)
    max_artifacts: int = Field(default=5, ge=1, le=20)
    budget_usd: float = Field(default=0.0, ge=0.0)
    plan_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None
