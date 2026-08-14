from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from tenant_context import require_user_id
from utils.timeutil import utcnow


class _TenantModel(BaseModel):
    user_id: str

    def model_post_init(self, __context: object) -> None:
        require_user_id(self.user_id, context=self.__class__.__name__)


class PersonRecord(_TenantModel):
    person_id: str = Field(default_factory=lambda: str(uuid4()))
    canonical_name: str
    normalized_name: str
    status: str = "active"
    identity_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PersonIdentifierRecord(_TenantModel):
    identifier_id: str = Field(default_factory=lambda: str(uuid4()))
    person_id: str
    identifier_type: str
    normalized_value: str
    raw_value: str
    verification_status: str = "unverified"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


class CompanyPersonRecord(_TenantModel):
    relationship_id: str = Field(default_factory=lambda: str(uuid4()))
    company_id: str
    person_id: str
    relationship_type: str
    role: Optional[str] = None
    is_current: bool = True
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    source_claim_id: Optional[str] = None


class PersonHistoryRecord(_TenantModel):
    history_id: str = Field(default_factory=lambda: str(uuid4()))
    person_id: str
    company_id: Optional[str] = None
    history_type: str
    organization_name: str
    role: Optional[str] = None
    is_current: bool = False
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    state: str = "unknown"
    source_claim_id: Optional[str] = None


@dataclass(frozen=True)
class PersonIdentifierDraft:
    identifier_type: str
    normalized_value: str
    raw_value: str


@dataclass(frozen=True)
class PersonHistoryDraft:
    history_type: str
    organization_name: str
    role: Optional[str] = None
    state: str = "probable"


@dataclass(frozen=True)
class PersonDraft:
    canonical_name: str
    normalized_name: str
    company_id: str
    identity_key: str
    identity_confidence: float
    relationship_type: str
    role: Optional[str]
    identifiers: tuple[PersonIdentifierDraft, ...] = ()
    history: tuple[PersonHistoryDraft, ...] = ()
    conflict_fields: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()
    persistable: bool = True
    unresolved_reason: Optional[str] = None
