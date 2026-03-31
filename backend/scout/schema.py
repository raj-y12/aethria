"""
Strict output schema for all Scouts.
All Scouts must emit JSON matching this structure exactly.
Hypothesis-oriented: primary_thesis, key_assumptions, biggest_unknown support
evolution, reviewers, and partners.
References must prove the company exists (URLs, news, Crunchbase, etc.);
generic placeholders like "General domain knowledge" are rejected.
Also, we reject obvious mega-cap incumbents (Google, Microsoft, Amazon, etc.)
as Scout outputs; Scouts should surface VC-scale startups instead.
"""
from typing import TypedDict, List
from uuid import uuid4
import json
import re

from utils.reference_validation import is_generic_reference, is_megacap_company


class ScoutOutput(TypedDict):
    """Strict schema for Scout discoveries (hypothesis-oriented). References are mandatory."""
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
    references: List[str]


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
        "references": list,
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
    # Reject obvious mega-cap / large incumbent company names
    if is_megacap_company(data["name"]):
        raise ValueError(
            "name appears to be a large incumbent (FAANG / hyperscaler). "
            "Scouts must surface venture-scale startups, not mega-cap companies."
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
    
    # references: mandatory, 1-8 non-empty strings; at least one must be a real source
    refs = data["references"]
    if not refs or not isinstance(refs, list):
        raise ValueError("references is required and must be a non-empty list")
    if not (1 <= len(refs) <= 8):
        raise ValueError("references must have between 1 and 8 items")
    for i, r in enumerate(refs):
        if not isinstance(r, str) or not r.strip():
            raise ValueError(
                f"references[{i}] must be a non-empty string, got {type(r).__name__}"
            )
    valid_refs = [r for r in refs if isinstance(r, str) and r.strip() and not is_generic_reference(r)]
    if not valid_refs:
        raise ValueError(
            "references must include at least one real source (URL, news, Crunchbase, etc.) "
            "that proves the company exists. 'General domain knowledge' is not acceptable."
        )
    _url_pat = re.compile(r"https?://", re.I)
    if not any(_url_pat.search(r) for r in valid_refs):
        raise ValueError(
            "references must include at least one http(s) URL per source line (prose-only citations are rejected)."
        )

    return ScoutOutput(**data)


def generate_id() -> str:
    """Generate a UUID for Scout discoveries."""
    return str(uuid4())
