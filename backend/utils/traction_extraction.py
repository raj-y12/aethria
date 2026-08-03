"""Pull firmographic traction facts out of evidence text the pipeline already has.

A live IC pack passed on CameraMatics partly because the reviewer flagged
"Missing revenue or traction data". The data was not missing. It was sitting in
the record, inside a founder-evidence snippet:

    "CameraMatics has 100-150 employees (+10% YoY) and has annual revenue in the
     $1M-$10M range, founded in 2016 ... with 7 prior funding rounds."

Nothing read it. Founder evidence was collected for founder resolution, and the
reviewer prompt never saw those snippets — so retrieved, stored, paid-for
evidence was declared absent and changed a decision.

This module is deliberately **rules only, no LLM** (invariant 8): these are
fixed phrasings that appear in aggregator profile text, and a regex that fails
to match simply yields nothing. Extraction never invents a value — an
unmatched pattern produces no key, so a missing fact stays missing rather than
becoming a plausible guess.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# Bounded so a pathological page cannot dominate the scan.
_MAX_SNIPPET_CHARS = 20_000
_MAX_SNIPPETS = 60

_EMPLOYEES = re.compile(
    r"\b(\d{1,3}(?:[,\d]{0,7})?(?:\s*[-–]\s*\d{1,3}(?:[,\d]{0,7})?)?)\s*\+?\s*employees\b",
    re.IGNORECASE,
)
_REVENUE = re.compile(
    r"annual revenue (?:in the |of )?(\$[\d.]+[KMB]?(?:\s*[-–]\s*\$?[\d.]+[KMB]?)?)",
    re.IGNORECASE,
)
_ARR = re.compile(r"(\$[\d.]+\s*[KMB])\s*(?:in\s+)?ARR\b", re.IGNORECASE)
_FOUNDED = re.compile(r"\bfounded in (\d{4})\b", re.IGNORECASE)
_ROUNDS = re.compile(r"\b(\d{1,2})\s+(?:prior|previous|total)?\s*funding rounds?\b", re.IGNORECASE)
_HEADCOUNT_GROWTH = re.compile(r"\(([+-]\d{1,3})%\s*YoY\)", re.IGNORECASE)


def _iter_snippets(payload: Dict[str, Any]) -> Iterable[str]:
    """Every piece of evidence text attached to a scout payload.

    Founder evidence is included on purpose: it is where the richest
    firmographic text has historically landed, and it was the layer nothing
    downstream ever read.
    """
    for item in (payload.get("source_evidence") or [])[:_MAX_SNIPPETS]:
        if isinstance(item, dict):
            for key in ("snippet", "content", "reference", "supports"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    yield value[:_MAX_SNIPPET_CHARS]

    resolution = payload.get("founder_resolution")
    if isinstance(resolution, dict):
        for founder in (resolution.get("founders") or [])[:_MAX_SNIPPETS]:
            if not isinstance(founder, dict):
                continue
            for evidence in (founder.get("evidence") or []):
                if isinstance(evidence, dict):
                    value = evidence.get("snippet")
                    if isinstance(value, str) and value.strip():
                        yield value[:_MAX_SNIPPET_CHARS]


def _first(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def extract_traction_facts(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Return firmographic facts found verbatim in evidence, or None.

    Returning `None` rather than an empty dict keeps "we found nothing" and "we
    never looked" distinguishable downstream.
    """
    text = "\n".join(_iter_snippets(payload))
    if not text.strip():
        return None

    facts: Dict[str, str] = {}
    employees = _first(_EMPLOYEES, text)
    if employees:
        facts["employees"] = employees
        growth = _first(_HEADCOUNT_GROWTH, text)
        if growth:
            facts["headcount_growth"] = f"{growth}% YoY"
    revenue = _first(_REVENUE, text) or _first(_ARR, text)
    if revenue:
        facts["revenue"] = revenue
    founded = _first(_FOUNDED, text)
    if founded:
        facts["founded"] = founded
    rounds = _first(_ROUNDS, text)
    if rounds:
        facts["funding_rounds"] = rounds

    return facts or None


def render_traction_facts(facts: Optional[Dict[str, str]]) -> str:
    """One line for the reviewer prompt. Empty string when nothing was found."""
    if not facts:
        return ""
    labels = (
        ("employees", "Employees"),
        ("headcount_growth", "Headcount growth"),
        ("revenue", "Revenue"),
        ("founded", "Founded"),
        ("funding_rounds", "Prior funding rounds"),
    )
    parts: List[str] = [f"{label}: {facts[key]}" for key, label in labels if facts.get(key)]
    return "; ".join(parts)
