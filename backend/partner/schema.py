"""
Strict output schema for Partner decisions.
All Partners must emit JSON matching this structure exactly.
Validates against versioned partner rules policy (resources/config via policy_resolver).
"""
from typing import TypedDict, Literal, List


class PartnerOutput(TypedDict, total=False):
    """
    Strict schema for Partner investment decisions (legacy - use PartnerInfo from models.py).
    Supports assumption_risks for hypothesis-aware decisions.
    """
    decision: Literal["YES", "NO", "MAYBE"]
    confidence: int  # 1-10 (legacy - maps to conviction_level)
    conviction_level: int  # 1-10 (canonical)
    rationale: str
    next_action: str
    human_review_required: bool
    partner_agent_id: str  # Optional: Agent identifier for performance tracking
    assumption_risks: List[str]  # Critical unknowns or assumption concerns from Reviewer assumption_feedback / hypothesis


# Canonical decisions per partner policy JSON (active.json version pointer)
VALID_DECISIONS = ["YES", "NO", "MAYBE"]


def validate_partner_output(data: dict) -> PartnerOutput:
    """
    Validate that a dictionary matches the PartnerOutput schema.
    Ensures decision is YES/NO/MAYBE.
    conviction_level (or confidence) must be 1-10.
    assumption_risks defaults to [] if missing.
    Raises ValueError if validation fails.
    """
    required_fields = {
        "decision": str,
        "rationale": str,
        "next_action": str,
        "human_review_required": bool,
    }

    for field, field_type in required_fields.items():
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(data[field], field_type):
            raise ValueError(
                f"Field '{field}' must be of type {field_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
    if not data["rationale"].strip():
        raise ValueError("rationale must be a non-empty string")
    if not data["next_action"].strip():
        raise ValueError("next_action must be a non-empty string")

    if data["decision"] not in VALID_DECISIONS:
        raise ValueError(
            f"decision must be one of {VALID_DECISIONS}, got {data['decision']}"
        )

    conviction = data.get("conviction_level") or data.get("confidence")
    if conviction is None:
        raise ValueError("Either conviction_level or confidence must be present")
    if not isinstance(conviction, int) or not (1 <= conviction <= 10):
        raise ValueError(f"conviction_level/confidence must be between 1 and 10, got {conviction}")

    if "assumption_risks" in data:
        ar = data["assumption_risks"]
        if not isinstance(ar, list):
            raise ValueError("assumption_risks must be a list")
        for item in ar:
            if not isinstance(item, str):
                raise ValueError("All items in assumption_risks must be strings")
    else:
        data = {**data, "assumption_risks": []}

    return PartnerOutput(**data)
