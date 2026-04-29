"""
Shared, lightweight deal context builders for pipeline stages.

Centralizes which scout fields participate in deterministic text blobs so prompts and
rule-based alignment stay aligned when new scout fields are added.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

# Order preserved for stable concatenation in thesis matching / search blobs.
SCOUT_SCALAR_KEYS_FOR_TEXT_BLOB: Tuple[str, ...] = (
    "name",
    "one_line",
    "sector",
    "problem",
    "solution",
    "target_users",
    "why_now",
)


def scout_text_blob_lower(scout_output: Dict[str, Any]) -> str:
    """
    Lowercased, space-joined scalar scout fields for keyword / overlap checks
    (e.g. rule-based fund thesis alignment). Not for LLM narrative prompts.
    """
    parts = [scout_output.get(k) for k in SCOUT_SCALAR_KEYS_FOR_TEXT_BLOB]
    return " ".join(str(p) for p in parts if p).lower()
