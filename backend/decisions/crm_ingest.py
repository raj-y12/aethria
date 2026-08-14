"""Future CRM-to-Aethria boundary; validation only, no automatic ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field

from tenant_context import require_user_id
from utils.timeutil import utcnow


class CrmInboundRecord(BaseModel):
    """Tenant-private input envelope for a future connector.

    It is deliberately not accepted by an endpoint yet. Connector code will
    later translate this envelope into observations, private evidence, or
    relationship records after explicit policy and provenance checks.
    """

    user_id: str
    provider: str
    entity_type: str
    external_entity_id: str
    workspace_id: str = "default"
    company_identity: Dict[str, Any] = Field(default_factory=dict)
    pipeline_stage: str | None = None
    owner_external_id: str | None = None
    meeting_notes: str | None = None
    private_notes: str | None = None
    observed_at: datetime = Field(default_factory=utcnow)

    def model_post_init(self, __context: object) -> None:
        require_user_id(self.user_id, context="CrmInboundRecord")
