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

from utils.reference_validation import (
    is_generic_reference,
    is_megacap_company,
    validate_references_not_only_incumbent_domains,
)


class ScoutOutput(TypedDict):
    """Strict schema for Scout discoveries. `name` is always a real company; thesis fields frame the investment hypothesis about that company. References are mandatory."""
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
    founder_names: List[str]


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
    # Fixed 2026-08-17 (audit HIGH-A7): a missing name used to be silently
    # fabricated ("Unknown Startup", or the first 4 words of one_line) before
    # reaching here, producing a plausible-looking row for a company that was
    # never actually identified. That fabrication is gone -- an empty name now
    # fails validation here instead, which routes through the existing repair-
    # pass machinery (_finalize_scout_payload_from_llm), and if repair can't
    # produce a real name either, the discovery correctly fails closed instead
    # of persisting a guess (AGENTS.md invariant 5).
    if not str(data["name"]).strip():
        raise ValueError("name is required and must not be empty")
    # Reject obvious mega-cap / large incumbent company names
    if is_megacap_company(data["name"]):
        raise ValueError(
            "name appears to be a large public or mega-scale company. "
            "Scouts must surface venture-scale startups, not incumbents (e.g. Stripe-scale public names)."
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
    validate_references_not_only_incumbent_domains(valid_refs)

    founders = data.get("founder_names", [])
    if founders is None:
        founders = []
    if not isinstance(founders, list) or len(founders) > 8:
        raise ValueError("founder_names must be a list with at most 8 names")
    if any(not isinstance(name, str) or not name.strip() for name in founders):
        raise ValueError("founder_names must contain non-empty strings")

    return ScoutOutput(**data)


def generate_id() -> str:
    """Generate a UUID for Scout discoveries."""
    return str(uuid4())
