"""Helpers for single-user conviction-state history.

Today the authenticated user owns these records. Future fund/org ownership should
switch at the adapter boundary that calls this helper, not inside the history
record shape.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from utils.partner_codes import LEGACY_TO_RECOMMENDATION


_SCORE_KEYS = (
    "market_score",
    "product_score",
    "technical_score",
    "execution_score",
    "defensibility_score",
    "overall_score",
    "confidence_adjusted_score",
    "thesis_alignment_score",
    "fund_thesis_alignment_score",
)


def _current_decision(raw: Dict[str, Any]) -> Optional[str]:
    human = raw.get("human_resolution")
    if isinstance(human, dict) and human.get("decision"):
        return str(human.get("decision"))
    state = raw.get("conviction_state")
    current = state.get("current_ruling") if isinstance(state, dict) else None
    if isinstance(current, dict) and current.get("decision"):
        return str(current.get("decision"))
    return None


def _score_snapshot(raw: Dict[str, Any]) -> Dict[str, Any]:
    review = raw.get("review_info") if isinstance(raw.get("review_info"), dict) else {}
    return {key: review.get(key) for key in _SCORE_KEYS if review.get(key) is not None}


def _confidence(raw: Dict[str, Any]) -> Optional[float]:
    partner = raw.get("partner_info") if isinstance(raw.get("partner_info"), dict) else {}
    value = partner.get("confidence")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_conviction_patch(
    startup_id: str,
    existing: Dict[str, Any],
    *,
    decision: str,
    rationale: str,
    resolved_at: str,
    risk_acknowledged: bool = False,
    mandate_exception: bool = False,
    config_version: Optional[str] = None,
) -> Dict[str, Any]:
    previous_decision = _current_decision(existing)
    score_snapshot = _score_snapshot(existing)
    confidence = _confidence(existing)
    state = dict(existing.get("conviction_state") or {})
    history = list(state.get("decision_history") or [])
    score_changes = list(state.get("score_changes") or [])
    confidence_changes = list(state.get("confidence_changes") or [])
    risk_acks = list(state.get("risk_acknowledgements") or [])

    record = {
        "company_id": startup_id,
        "previous_decision": previous_decision,
        "new_decision": decision,
        "timestamp": resolved_at,
        "rationale": rationale,
        "confidence": confidence,
        "score_snapshot": score_snapshot,
        "risk_acknowledged": risk_acknowledged,
        "config_version": config_version,
    }
    history.append(record)

    if history and len(history) > 1:
        prev_snapshot = history[-2].get("score_snapshot") if isinstance(history[-2], dict) else None
        if isinstance(prev_snapshot, dict) and prev_snapshot != score_snapshot:
            score_changes.append(
                {
                    "company_id": startup_id,
                    "timestamp": resolved_at,
                    "previous_snapshot": prev_snapshot,
                    "new_snapshot": score_snapshot,
                    "config_version": config_version,
                }
            )
        prev_conf = history[-2].get("confidence") if isinstance(history[-2], dict) else None
        if prev_conf != confidence and confidence is not None:
            confidence_changes.append(
                {
                    "company_id": startup_id,
                    "timestamp": resolved_at,
                    "previous_confidence": prev_conf,
                    "new_confidence": confidence,
                    "config_version": config_version,
                }
            )

    if risk_acknowledged:
        risk_acks.append(
            {
                "company_id": startup_id,
                "timestamp": resolved_at,
                "acknowledged": True,
                "rationale": rationale,
                "config_version": config_version,
            }
        )

    current_ruling = {
        "decision": decision,
        "rationale": rationale,
        "resolved_at": resolved_at,
        "confidence": confidence,
        "score_snapshot": score_snapshot,
        "config_version": config_version,
    }

    hr = {
        "decision": decision,
        "notes": rationale,
        "resolved_at": resolved_at,
    }
    if mandate_exception:
        # Audit trail: a human knowingly invested past the mandate-fit gate.
        hr["mandate_exception"] = True
        record["mandate_exception"] = True
        current_ruling["mandate_exception"] = True
    partner_patch: Dict[str, Any] = {}
    if isinstance(existing.get("partner_info"), dict):
        partner_patch = {
            **existing["partner_info"],
            "recommendation": LEGACY_TO_RECOMMENDATION.get(decision, existing["partner_info"].get("recommendation")),
            "human_review_required": False,
        }
        if mandate_exception:
            # Exception granted: clear the hold, but keep the fit read honest.
            partner_patch["mandate_override_required"] = False
            partner_patch["mandate_gate"] = "exception_granted"

    return {
        "human_resolution": hr,
        "conviction_state": {
            **state,
            "current_ruling": current_ruling,
            "decision_history": history,
            "ruling_rationale": rationale,
            "risk_acknowledgements": risk_acks,
            "score_changes": score_changes,
            "confidence_changes": confidence_changes,
            "escalation_events": list(state.get("escalation_events") or []),
        },
        **({"partner_info": partner_patch} if partner_patch else {}),
    }
