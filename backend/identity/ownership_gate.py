"""Fail-closed ownership/acquisition conflict detection for Partner.

known-issues.md "Partial canonical-authority rollout leaves investment records
internally contradictory" — a 2022 Series B and historical customer-growth
narrative were treated as current traction for a company acquired in 2023.
Acquired companies are ineligible for an automatic decision unless
independently verified as a new spinout; this module is deliberately
conservative (regex over grounded/reviewer text, same rule-based style as
utils/scout_post_review_enrichment.py's funding-stage inference) and routes a
hit to human review rather than ever auto-deciding PASS or INVEST on it.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

_ACQUISITION_PATTERNS = [
    re.compile(r"\bacquired\s+by\b", re.IGNORECASE),
    re.compile(r"\bacquisition\s+of\b.{0,80}\bby\b", re.IGNORECASE),
    re.compile(r"\bwas\s+acquired\b", re.IGNORECASE),
    re.compile(r"\bhas\s+been\s+acquired\b", re.IGNORECASE),
    re.compile(r"\bnow\s+(a\s+)?(wholly[- ]owned\s+)?subsidiary\s+of\b", re.IGNORECASE),
    re.compile(r"\bacqui-?hired\s+by\b", re.IGNORECASE),
]

_SPINOUT_OVERRIDE_KEYS = ("ownership_verified_spinout",)


def _collect_text(scout_output: Dict[str, Any], review_output: Dict[str, Any]) -> str:
    parts = []
    for key in ("one_line", "problem", "solution", "why_now"):
        value = scout_output.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    for key in ("overall_summary", "investment_thesis", "competition_analysis"):
        value = review_output.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v).strip() for v in value if isinstance(v, str) and str(v).strip())
    return " \n ".join(parts)


def detect_acquisition_signal(text: str) -> Optional[str]:
    """Return the matched phrase, or None if no acquisition language is present."""
    if not text or not text.strip():
        return None
    for pattern in _ACQUISITION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def check_ownership_conflict(
    scout_output: Dict[str, Any], review_output: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Return a block payload when acquisition language is present and no
    operator has independently verified the company as a new spinout;
    otherwise None (clear to proceed to the normal decision logic)."""
    if any(bool(scout_output.get(key) or review_output.get(key)) for key in _SPINOUT_OVERRIDE_KEYS):
        return None
    text = _collect_text(scout_output, review_output)
    matched = detect_acquisition_signal(text)
    if matched is None:
        return None
    return {
        "code": "ownership_conflict_detected",
        "matched_text": matched,
        "detail": (
            "Evidence suggests this company was acquired; acquired companies "
            "are ineligible for an automatic decision unless independently "
            "verified as a new spinout."
        ),
    }
