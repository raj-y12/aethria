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
    # Legacy compatibility fields
    decision: Optional[Literal["YES", "NO", "MAYBE"]]
    rationale: Optional[str]
    conviction_level: Optional[int]
    assumption_risks: Optional[List[str]]
    decision_drivers: Optional[List[str]]


VALID_RECOMMENDATIONS = ["INVEST", "PASS", "MONITOR"]


def validate_partner_output(data: dict) -> PartnerOutput:
    data = dict(data)
    legacy_decision_map = {"YES": "INVEST", "NO": "PASS", "MAYBE": "MONITOR"}
    if "recommendation" not in data and isinstance(data.get("decision"), str):
        data["recommendation"] = legacy_decision_map.get(str(data["decision"]).strip().upper(), data["decision"])
    if "decision_rationale" not in data and isinstance(data.get("rationale"), str):
        data["decision_rationale"] = data["rationale"]
    if "decision" in data and "recommendation" in data:
        data.setdefault("thesis", "N/A")
        data.setdefault("why_this_matters", "N/A")
        data.setdefault("market_insight", "N/A")
        data.setdefault("product_edge", "N/A")
        data.setdefault("next_action", "N/A")
        data.setdefault("snapshot", {"one_liner": "N/A"})
        data.setdefault("risks", [])
    if "confidence" not in data and data.get("conviction_level") is not None:
        try:
            conv = float(data["conviction_level"])
            if not 1.0 <= conv <= 10.0:
                raise ValueError("conviction_level must be between 1 and 10")
            data["confidence"] = max(0.0, min(1.0, conv / 10.0))
        except (TypeError, ValueError):
            if isinstance(data.get("conviction_level"), (int, float)):
                raise
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

    for field in ["thesis", "why_this_matters", "market_insight", "product_edge"]:
        if not data[field].strip():
            raise ValueError(f"Field '{field}' must be non-empty")
    if not data["decision_rationale"].strip():
        raise ValueError("rationale must be a non-empty string")
    if not data["next_action"].strip():
        raise ValueError("next_action must be a non-empty string")

    # Backfill legacy output keys for compatibility.
    if "decision" not in data:
        data["decision"] = {"INVEST": "YES", "PASS": "NO", "MONITOR": "MAYBE"}.get(
            data["recommendation"], "MAYBE"
        )
    if "rationale" not in data:
        data["rationale"] = data["decision_rationale"]
    if "conviction_level" not in data:
        data["conviction_level"] = max(1, min(10, int(round(conf * 9)) + 1))

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
