from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from decisions.models import (
    HumanRulingDecision,
    OverrideType,
    WorkflowActionType,
)
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


def investment_transition_is_allowed(current_ruling: str | None) -> bool:
    """Only an opportunity already advanced to diligence can be invested."""
    return str(current_ruling or "").strip().lower() == "advance"


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
    action_type: WorkflowActionType | str, missing_evidence: Sequence[str]
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
        return {
            "summary": "CRM export prepared; no external write has occurred.",
            "requires_approval": True,
            "external_write_performed": False,
        }
    return {
        "missing_evidence": gaps,
        "requires_approval": action in {
            WorkflowActionType.GENERATE_DECISION_PACK,
        },
        "external_write_performed": False,
    }
