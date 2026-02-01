"""
Strict output schema for all Scouts.
All Scouts must emit JSON matching this structure exactly.
Hypothesis-oriented: primary_thesis, key_assumptions, biggest_unknown support
evolution, reviewers, and partners.
"""
from typing import TypedDict, List
from uuid import uuid4
import json


class ScoutOutput(TypedDict):
    """Strict schema for Scout discoveries (hypothesis-oriented)."""
    id: str
    scout_type: str
    name: str
    one_line: str
    sector: str
    problem: str
    solution: str
    target_users: str
    why_now: str
    confidence: float
    primary_thesis: str
    key_assumptions: List[str]
    biggest_unknown: str


def validate_scout_output(data: dict) -> ScoutOutput:
    """
    Validate that a dictionary matches the ScoutOutput schema.
    Raises ValueError if validation fails.
    """
    required_fields = {
        "id": str,
        "scout_type": str,
        "name": str,
        "one_line": str,
        "sector": str,
        "problem": str,
        "solution": str,
        "target_users": str,
        "why_now": str,
        "confidence": float,
        "primary_thesis": str,
        "key_assumptions": list,
        "biggest_unknown": str,
    }
    
    # Check all required fields exist
    for field, field_type in required_fields.items():
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(data[field], field_type):
            raise ValueError(
                f"Field '{field}' must be of type {field_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
    
    # Validate confidence is between 0 and 1
    if not (0.0 <= data["confidence"] <= 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")
    
    # key_assumptions: list of strings, length 2-4
    assumptions = data["key_assumptions"]
    if not (2 <= len(assumptions) <= 4):
        raise ValueError("key_assumptions must have between 2 and 4 items")
    for i, a in enumerate(assumptions):
        if not isinstance(a, str):
            raise ValueError(
                f"key_assumptions[{i}] must be a string, got {type(a).__name__}"
            )
    
    return ScoutOutput(**data)


def generate_id() -> str:
    """Generate a UUID for Scout discoveries."""
    return str(uuid4())
