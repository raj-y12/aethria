"""
Strict output schema for Partner decisions.
All Partner outputs must emit JSON matching this structure exactly.
"""
from typing import TypedDict, Literal, List, Optional, Dict, Any


class PartnerSnapshot(TypedDict, total=False):
    one_liner: str
    stage: Optional[str]
    key_signal: Optional[str]


class PartnerOutput(TypedDict, total=False):
    """Strict schema for Partner investment decisions."""
    thesis: str
    why_this_matters: str
    snapshot: PartnerSnapshot
    market_insight: str
    product_edge: str
    traction_signals: Optional[str]
    risks: List[str]
    recommendation: Literal["INVEST", "PASS", "MONITOR"]
    decision_rationale: str
    confidence: float  # 0.0–1.0
    next_action: str
    human_review_required: bool
    # Metadata — set by engine, not validated here
    partner_agent_id: Optional[str]
    llm_fallback_reason: Optional[str]
    prompt_version: Optional[str]


VALID_RECOMMENDATIONS = ["INVEST", "PASS", "MONITOR"]


def validate_partner_output(data: dict) -> PartnerOutput:
    """
    Validate that a dict matches the PartnerOutput schema.
    Raises ValueError if validation fails.
    """
    required_str_fields = ["thesis", "why_this_matters", "market_insight", "product_edge",
                           "recommendation", "decision_rationale", "next_action"]
    for field in required_str_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(data[field], str):
            raise ValueError(f"Field '{field}' must be a string, got {type(data[field]).__name__}")

    for field in ["thesis", "why_this_matters", "market_insight", "product_edge",
                  "decision_rationale", "next_action"]:
        if not data[field].strip():
            raise ValueError(f"Field '{field}' must be non-empty")

    if data["recommendation"] not in VALID_RECOMMENDATIONS:
        raise ValueError(
            f"recommendation must be one of {VALID_RECOMMENDATIONS}, got {data['recommendation']!r}"
        )

    if "confidence" not in data:
        raise ValueError("Missing required field: confidence")
    try:
        conf = float(data["confidence"])
    except (TypeError, ValueError):
        raise ValueError(f"confidence must be a number, got {data['confidence']!r}")
    if not (0.0 <= conf <= 1.0):
        raise ValueError(f"confidence must be between 0.0 and 1.0, got {conf}")

    if "snapshot" not in data:
        raise ValueError("Missing required field: snapshot")
    snap = data["snapshot"]
    if not isinstance(snap, dict):
        raise ValueError(f"snapshot must be a dict, got {type(snap).__name__}")
    if "one_liner" not in snap or not isinstance(snap["one_liner"], str):
        raise ValueError("snapshot.one_liner must be a string")

    if "risks" not in data:
        raise ValueError("Missing required field: risks")
    if not isinstance(data["risks"], list):
        raise ValueError(f"risks must be a list, got {type(data['risks']).__name__}")
    for item in data["risks"]:
        if not isinstance(item, str):
            raise ValueError("All items in risks must be strings")

    if "human_review_required" not in data:
        raise ValueError("Missing required field: human_review_required")
    if not isinstance(data["human_review_required"], bool):
        raise ValueError(
            f"human_review_required must be bool, got {type(data['human_review_required']).__name__}"
        )

    return PartnerOutput(**{k: v for k, v in data.items() if k in PartnerOutput.__annotations__})
