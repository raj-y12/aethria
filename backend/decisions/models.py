from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from tenant_context import require_user_id
from utils.timeutil import utcnow


class HumanRulingDecision(str, Enum):
    ADVANCE = "advance"
    MONITOR = "monitor"
    PASS = "pass"
    INVEST = "invest"


class OverrideType(str, Enum):
    EVIDENCE_CORRECTION = "evidence_correction"
    MISSING_PRIVATE_EVIDENCE = "missing_private_evidence"
    POLICY_DISAGREEMENT = "policy_disagreement"
    FOUNDER_JUDGMENT = "founder_judgment"
    MARKET_JUDGMENT = "market_judgment"
    TIMING = "timing"
    STRATEGIC_EXCEPTION = "strategic_exception"
    RELATIONSHIP_CONTEXT = "relationship_context"
    CONFIDENCE_DISAGREEMENT = "confidence_disagreement"


class WorkflowActionType(str, Enum):
    PREPARE_DILIGENCE_QUESTIONS = "prepare_diligence_questions"
    DRAFT_INFORMATION_REQUEST = "draft_information_request"
    REFRESH_EVIDENCE = "refresh_evidence"
    SCHEDULE_MONITOR_REVIEW = "schedule_monitor_review"
    EXPORT_TO_CRM = "export_to_crm"
    GENERATE_DECISION_PACK = "generate_decision_pack"
    RESOLVE_IDENTITY = "resolve_identity"


class WorkflowActionStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class _TenantModel(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def tenant(cls, value):
        try:
            return require_user_id(value, context=cls.__name__)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc


class HumanRulingInput(_TenantModel):
    opportunity_id: str
    recommendation_id: Optional[str] = None
    decision: HumanRulingDecision
    rationale: str = Field(min_length=3, max_length=2000)
    risk_acknowledgement: Optional[str] = Field(default=None, max_length=1000)
    mandate_exception: Optional[str] = Field(default=None, max_length=1000)
    investor_confidence: float = Field(default=0.5, ge=0, le=1)
    override_type: Optional[OverrideType] = None
    override_note: Optional[str] = Field(default=None, max_length=1000)


class HumanRulingRecord(HumanRulingInput):
    ruling_id: str = Field(default_factory=lambda: str(uuid4()))
    actor_id: str
    prior_ruling_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class WorkflowActionRecord(_TenantModel):
    workflow_action_id: str = Field(default_factory=lambda: str(uuid4()))
    opportunity_id: str
    action_type: WorkflowActionType
    trigger_type: str
    trigger_id: Optional[str] = None
    status: WorkflowActionStatus
    generated_content: Dict[str, Any] = Field(default_factory=dict)
    approved_content: Optional[Dict[str, Any]] = None
    missing_evidence: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    external_destination: Optional[str] = None
    external_reference: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    failure_code: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
