"""LLM-grounded disambiguation for Company Resolver's identity pick.

The heuristic candidate scoring in company_resolver.py (slug similarity,
name-token overlap) has a ceiling for common/short company names -- several
distinct patches this month (Vercel/Hashimoto, Anthropic/anthropic.io,
General Electric/Motors, Notion) each fixed one text-matching collision.
This reads the actual candidate content and judges instead, per
docs/superpowers/specs/2026-08-18-company-identity-llm-disambiguation-design.md.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel

from utils.openai_client import build_openai_client
from partner.decision import _parse_llm_json_object
from security.prompt_safety import isolate_untrusted_text, prompt_safety_instruction

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5-nano"
# Fixed after live-dispatch validation (Task 5): gpt-5-nano is a reasoning
# model that spends completion tokens on internal reasoning before any
# visible output. 1024 -- believed a safe floor from an earlier reviewer.py
# bug fix -- was live-observed to be fully consumed by reasoning alone
# (finish_reason="length", content="", reasoning_tokens=1024), leaving zero
# tokens for the JSON response and forcing every real call through the
# "malformed model response" fail-closed path. reviewer/base.py's actual
# working default for the same model is 16384 (DEFAULT_MAX_COMPLETION_TOKENS);
# 1024 there is only the floor a caller-supplied override is clamped to, not
# what's actually used day to day.
_MAX_COMPLETION_TOKENS = 16384


class DisambiguationResult(BaseModel):
    picked_url: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    called: bool = False


def _safe_default(reasoning: str) -> DisambiguationResult:
    return DisambiguationResult(picked_url=None, confidence=0.0, reasoning=reasoning, called=False)


def _build_prompt(company_name: str, candidates: List[Any]) -> tuple[str, str]:
    system = (
        "You are disambiguating which of several search-result candidates is the "
        "real company a user typed a name for. Respond with exactly one JSON object: "
        '{"picked_url": "<one of the candidate URLs, or null if none confidently match>", '
        '"confidence": <0.0-1.0>, "reasoning": "<one sentence>"}. '
        "No markdown, no other text. "
        + prompt_safety_instruction()
    )
    safe_name = isolate_untrusted_text(company_name, label="typed_company_name")
    lines = [f"Typed company name: {safe_name}", "", "Candidates:"]
    for i, c in enumerate(candidates):
        safe_title = isolate_untrusted_text(c.title, label=f"candidate_{i}_title")
        safe_snippet = isolate_untrusted_text(c.snippet, label=f"candidate_{i}_snippet")
        lines.append(f"- URL: {c.url}\n  Title: {safe_title}\n  Snippet: {safe_snippet}")
    return system, "\n".join(lines)


def disambiguate_identity(
    company_name: str,
    candidates: List[Any],
    *,
    user_id: str,
    cost_controller: Any = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> DisambiguationResult:
    if not api_key:
        return _safe_default("disambiguation unavailable: no api key configured")
    if len(candidates) < 2:
        return _safe_default("disambiguation skipped: fewer than 2 candidates")

    effective_model = model or _DEFAULT_MODEL

    if cost_controller is not None:
        allowed, reason = cost_controller.check_budget(
            "identity_disambiguation", user_id, estimated_tokens=_MAX_COMPLETION_TOKENS
        )
        if not allowed:
            logger.warning(
                "identity_disambiguation: budget denied user_id=%s reason=%s", user_id, reason
            )
            return _safe_default(f"disambiguation unavailable: {reason}")

    try:
        system, user = _build_prompt(company_name, candidates)
        client = build_openai_client(api_key)
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
        )
        content = response.choices[0].message.content
    except Exception as e:
        logger.warning("identity_disambiguation: call failed user_id=%s: %s", user_id, e)
        return _safe_default(f"disambiguation unavailable: {e}")

    if cost_controller is not None:
        tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
        cost_controller.record_usage(
            "identity_disambiguation", user_id, tokens_used, model=effective_model
        )

    parsed = _parse_llm_json_object(content or "")
    if not parsed:
        return _safe_default("disambiguation unavailable: malformed model response")

    picked_url = parsed.get("picked_url")
    if picked_url is not None and not isinstance(picked_url, str):
        picked_url = None
    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    reasoning = str(parsed.get("reasoning") or "").strip()

    return DisambiguationResult(
        picked_url=picked_url, confidence=confidence, reasoning=reasoning, called=True
    )
