"""
Shared, lightweight deal context builders for pipeline stages.

Centralizes which scout fields participate in deterministic text blobs so prompts and
rule-based alignment stay aligned when new scout fields are added.

DealContextV1: stable digests for tracing and optional LLM prompt prefixes (token-aware).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple, TypedDict

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


class DealContextV1(TypedDict, total=False):
    """Versioned cross-stage digest bundle (additive; safe to log)."""

    version: str
    scout_digest: str
    thesis_version_id: str
    structured_signals_digest: str


def scout_digest_v1(scout_output: Dict[str, Any]) -> str:
    """Deterministic 16-hex digest from normalized scout scalars (stable across processes)."""
    blob = scout_text_blob_lower(scout_output)
    name = str(scout_output.get("name") or "").strip()
    payload = json.dumps({"blob": blob, "name": name}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _structured_signals_digest(review_output: Optional[Dict[str, Any]]) -> Optional[str]:
    if not review_output:
        return None
    raw = review_output.get("structured_signals")
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        ser = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(ser.encode("utf-8")).hexdigest()[:16]


def build_deal_context_v1(
    scout_output: Dict[str, Any],
    review_output: Optional[Dict[str, Any]] = None,
    fund_thesis: Optional[Dict[str, Any]] = None,
) -> DealContextV1:
    """
    Build a stable DealContextV1 for logging and optional partner LLM digest lines.
    Does not perform I/O.
    """
    ctx: DealContextV1 = {
        "version": "1",
        "scout_digest": scout_digest_v1(scout_output),
    }
    if fund_thesis and fund_thesis.get("version_id"):
        ctx["thesis_version_id"] = str(fund_thesis.get("version_id") or "")
    sig_d = _structured_signals_digest(review_output)
    if sig_d:
        ctx["structured_signals_digest"] = sig_d
    return ctx


def format_deal_context_digest_prompt_line(ctx: DealContextV1) -> str:
    """Single prompt line for LLM context (keep short)."""
    parts = [f"version={ctx.get('version', '1')}", f"scout_digest={ctx.get('scout_digest', '')}"]
    if ctx.get("thesis_version_id"):
        parts.append(f"thesis_version_id={ctx['thesis_version_id']}")
    if ctx.get("structured_signals_digest"):
        parts.append(f"structured_signals_digest={ctx['structured_signals_digest']}")
    return "DEAL_CONTEXT_V1 " + " ".join(parts)
