"""
Targeted web retrieval before Reviewer LLM when Scout left key fields empty.

One merged source pack per review job (ReviewerEngine), shared by all personas.
Controlled with REVIEWER_GAP_RETRIEVAL (default on) and REVIEWER_GAP_RETRIEVAL_ONLY_WHEN_GAPS (default on).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _truthy(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes")


def is_reviewer_gap_retrieval_enabled() -> bool:
    return _truthy("REVIEWER_GAP_RETRIEVAL", "true")


def _only_when_gaps() -> bool:
    return _truthy("REVIEWER_GAP_RETRIEVAL_ONLY_WHEN_GAPS", "true")


def _is_missing_tam(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _is_weak_funding_stage(value: Any) -> bool:
    if value is None:
        return True
    t = str(value).strip().lower()
    return not t or t in ("unknown", "null", "n/a", "na")


def scout_has_information_gaps(scout: Dict[str, Any]) -> bool:
    """True when Scout likely needs outside help for market / funding / corroboration."""
    if _is_missing_tam(scout.get("est_tam")):
        return True
    if _is_weak_funding_stage(scout.get("funding_stage")):
        return True
    refs = scout.get("references")
    if not isinstance(refs, list) or len([r for r in refs if isinstance(r, str) and r.strip()]) < 2:
        return True
    return False


def _company_search_label(scout: Dict[str, Any]) -> str:
    name = str(scout.get("name") or "").strip()
    if name and name.lower() not in ("unknown", "unknown startup"):
        return name
    one = str(scout.get("one_line") or "").strip()
    return one[:120] if one else ""


def build_gap_queries(scout: Dict[str, Any]) -> List[str]:
    label = _company_search_label(scout)
    if not label:
        return []
    queries: List[str] = []
    if _is_missing_tam(scout.get("est_tam")):
        queries.append(f"{label} startup TAM market size addressable market revenue")
    if _is_weak_funding_stage(scout.get("funding_stage")):
        queries.append(f"{label} startup funding round investors valuation raised")
    queries.append(f"{label} startup founders team CEO traction customers pilots")
    # De-dupe while preserving order
    seen: set[str] = set()
    out: List[str] = []
    for q in queries:
        qn = q.strip()
        if not qn or qn in seen:
            continue
        seen.add(qn)
        out.append(qn)
    return out[:4]


def fetch_reviewer_gap_pack(scout: Dict[str, Any], user_id: str) -> Dict[str, Any] | None:
    """
    Run merged retrieval when enabled and gaps warrant it. Returns the source pack dict or None.
    """
    uid = (user_id or "").strip()
    if not uid:
        return None
    if not is_reviewer_gap_retrieval_enabled():
        return None
    if _only_when_gaps() and not scout_has_information_gaps(scout):
        return None

    queries = build_gap_queries(scout)
    if not queries:
        return None

    from utils.retrieval_grounding import retrieve_source_pack_merged

    try:
        max_per = int(os.getenv("REVIEWER_GAP_MAX_PER_QUERY", "6"))
    except ValueError:
        max_per = 6
    try:
        max_total = int(os.getenv("REVIEWER_GAP_MAX_SOURCES", "12"))
    except ValueError:
        max_total = 12

    pack = retrieve_source_pack_merged(
        queries=queries,
        user_id=uid,
        max_per_query=max(max_per, 3),
        max_total_sources=max(min(max_total, 20), 5),
    )
    sources = pack.get("sources") or []
    if not sources:
        logger.info(
            "reviewer_gap_retrieval: no sources (queries=%d company=%s)",
            len(queries),
            scout.get("name"),
        )
        return None

    logger.info(
        "reviewer_gap_retrieval: sources=%d provider=%s company=%s",
        len(sources),
        pack.get("provider"),
        scout.get("name"),
    )
    return pack


def build_reviewer_supplement_block(scout: Dict[str, Any], user_id: str) -> str:
    """
    Render retrieved snippets for the reviewer user message, or empty string.
    """
    from utils.retrieval_grounding import render_sources_for_prompt

    pack = fetch_reviewer_gap_pack(scout, user_id)
    if not pack:
        return ""
    return render_sources_for_prompt(pack.get("sources") or [])


def enrich_scout_for_reviewer_llm(scout_output: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Shallow copy of scout payload with optional _reviewer_web_supplement for the Reviewer LLM only.
    Do not persist; deterministic scoring should use the original scout dict.
    """
    from utils.retrieval_grounding import render_sources_for_prompt

    out = dict(scout_output)
    pack = fetch_reviewer_gap_pack(scout_output, user_id)
    if not pack:
        return out
    sources = pack.get("sources") or []
    if not sources:
        return out
    out["_reviewer_web_supplement"] = render_sources_for_prompt(sources)
    allow = pack.get("url_allowlist")
    if allow:
        out["_reviewer_gap_reference_urls"] = list(allow)
    return out
