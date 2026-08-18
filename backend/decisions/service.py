from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from decisions.models import (
    HumanRulingDecision,
    OverrideType,
    WorkflowActionType,
)
from decisions.crm_export import build_crm_export_payload
from utils.partner_codes import ruling_aligns_with_recommendation


def ruling_to_opportunity_state(decision: HumanRulingDecision | str) -> str:
    value = HumanRulingDecision(decision)
    return {
        HumanRulingDecision.ADVANCE: "advance",
        HumanRulingDecision.MONITOR: "monitor",
        HumanRulingDecision.PASS: "pass",
        HumanRulingDecision.INVEST: "invested",
    }[value]


def workflow_state_for_ruling(decision: HumanRulingDecision | str) -> str:
    """Map a human disposition to the canonical authority workflow state."""
    value = HumanRulingDecision(decision)
    return {
        HumanRulingDecision.ADVANCE: "evidence_active",
        HumanRulingDecision.MONITOR: "monitoring",
        HumanRulingDecision.PASS: "completed",
        HumanRulingDecision.INVEST: "completed",
    }[value]


def classify_override(
    *,
    recommendation: Optional[str],
    ruling: HumanRulingDecision,
    requested: Optional[OverrideType],
) -> Optional[OverrideType]:
    aligned = ruling_aligns_with_recommendation(
        recommendation,
        ruling.value,
    )
    if aligned:
        return None
    return requested or OverrideType.CONFIDENCE_DISAGREEMENT


def build_workflow_draft(
    action_type: WorkflowActionType | str,
    missing_evidence: Sequence[str],
    *,
    export_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    action = WorkflowActionType(action_type)
    gaps = [str(item).strip() for item in missing_evidence if str(item).strip()][:30]
    if action is WorkflowActionType.PREPARE_DILIGENCE_QUESTIONS:
        return {
            "questions": [f"What evidence can verify {gap}?" for gap in gaps],
            "requires_approval": False,
            "external_write_performed": False,
        }
    if action is WorkflowActionType.DRAFT_INFORMATION_REQUEST:
        requested = ", ".join(gaps) or "the outstanding diligence information"
        return {
            "draft": f"Please share evidence addressing: {requested}.",
            "requires_approval": True,
            "external_write_performed": False,
        }
    if action is WorkflowActionType.EXPORT_TO_CRM:
        draft: Dict[str, Any] = {
            "summary": "CRM export prepared; no external write has occurred.",
            "requires_approval": True,
            "external_write_performed": False,
        }
        if export_context:
            draft["crm_row"] = build_crm_export_payload(
                company=export_context.get("company") or {},
                ruling=export_context.get("ruling") or {},
                position=export_context.get("position"),
                outcomes=export_context.get("outcomes") or [],
            )
        return draft
    return {
        "missing_evidence": gaps,
        "requires_approval": action in {
            WorkflowActionType.GENERATE_DECISION_PACK,
        },
        "external_write_performed": False,
    }
