from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


class LearningAttribution(str, Enum):
    ACQUISITION_MISS = "acquisition_miss"
    IDENTITY_ERROR = "identity_error"
    EVIDENCE_RETRIEVAL_GAP = "evidence_retrieval_gap"
    EXTRACTION_ERROR = "extraction_error"
    CLAIM_VERIFICATION_ERROR = "claim_verification_error"
    POLICY_CRITERION_DISAGREEMENT = "policy_criterion_disagreement"
    WEIGHT_THRESHOLD_DISAGREEMENT = "weight_threshold_disagreement"
    RECOMMENDATION_RULE_DISAGREEMENT = "recommendation_rule_disagreement"
    PRIVATE_INFORMATION_EXCEPTION = "private_information_exception"
    HUMAN_STRATEGIC_EXCEPTION = "human_strategic_exception"
    UNCLASSIFIED = "unclassified"


class PolicyProposalStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    ACCEPTED = "accepted"
    EDITED_AND_ACCEPTED = "edited_and_accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class ProposalReviewAction(str, Enum):
    ACCEPT = "accept"
    EDIT_AND_ACCEPT = "edit_and_accept"
    REJECT = "reject"
    DEFER = "defer"


class PolicyVersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class _TenantModel(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def valid_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context=cls.__name__)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class LearningSignalRecord(_TenantModel):
    learning_signal_id: str = Field(default_factory=lambda: str(uuid4()))
    opportunity_id: Optional[str] = None
    source_type: str
    source_id: str
    signal_type: str
    attribution: LearningAttribution
    strength: float = Field(ge=0, le=1)
    detail: Dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class OverridePattern(BaseModel):
    override_type: str
    attribution: LearningAttribution
    sample_size: int = Field(ge=0)
    opportunity_count: int = Field(ge=0)
    supporting_signal_ids: List[str]
    limitations: List[str]
    proposed_patch: Dict[str, Any]
    ready_for_proposal: bool


class PolicyProposalRecord(_TenantModel):
    policy_proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    proposal_fingerprint: str
    pattern_summary: str
    attribution: LearningAttribution
    sample_size: int = Field(ge=1)
    sample_period_start: Optional[datetime] = None
    sample_period_end: Optional[datetime] = None
    confidence: float = Field(ge=0, le=1)
    limitations: List[str] = Field(default_factory=list)
    proposed_policy_patch: Dict[str, Any]
    status: PolicyProposalStatus
    reviewer_rationale: Optional[str] = None
    resulting_policy_version_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PolicyVersionRecord(_TenantModel):
    governed_policy_version_id: str = Field(default_factory=lambda: str(uuid4()))
    policy_proposal_id: str
    policy_patch: Dict[str, Any]
    status: PolicyVersionStatus = PolicyVersionStatus.DRAFT
    created_by: str
    published_by: Optional[str] = None
    published_policy_id: Optional[str] = None
    published_policy_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    published_at: Optional[datetime] = None
