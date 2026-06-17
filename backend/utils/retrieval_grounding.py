"""
Scout retrieval grounding: provider selection, source normalization, and prompt context.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Set

from utils.reference_verify import extract_http_urls, normalize_url_for_match
from utils.tavily_client import tavily_search
from security.prompt_safety import flag_prompt_injection, isolate_untrusted_text, prompt_safety_instruction

logger = logging.getLogger("retrieval_grounding")


def _snippet_char_cap() -> int:
    raw = os.getenv("RETRIEVAL_SNIPPET_MAX_CHARS", "2800")
    try:
        n = int(raw)
    except ValueError:
        n = 2800
    return max(400, min(n, 12000))


def _default_max_results() -> int:
    raw = os.getenv("SCOUT_RETRIEVAL_MAX_RESULTS", "10")
    try:
        n = int(raw)
    except ValueError:
        n = 10
    return max(3, min(n, 15))


def _source_id(i: int) -> str:
    return f"S{i + 1}"


def _normalize_sources(raw_results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cap = _snippet_char_cap()
    out: List[Dict[str, str]] = []
    for i, row in enumerate(raw_results):
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        if not title or not url:
            continue
        if len(snippet) > cap:
            snippet = snippet[:cap]
        out.append(
            {
                "source_id": _source_id(i),
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )
    return out


def retrieve_source_pack(
    *,
    query: str,
    user_id: str,
    max_results: int | None = None,
    time_range: str | None = None,
    topic: str | None = None,
    days: int | None = None,
) -> Dict[str, Any]:
    """
    Build retrieval source pack with provider metadata and URL allowlist.

    time_range: optional Tavily recency filter ("day"|"week"|"month"|"year").
    topic/days: optional Tavily news-topic recency controls.
    """
    if max_results is None:
        max_results = _default_max_results()
    used_provider = "tavily"
    raw: List[Dict[str, str]] = tavily_search(
        query=query, max_results=max_results, time_range=time_range, topic=topic, days=days
    )

    sources = _normalize_sources(raw)
    allowlist: Set[str] = {s["url"] for s in sources if s.get("url")}
    normalized_allowlist = sorted(
        {
            normalize_url_for_match(url)
            for url in allowlist
            if isinstance(url, str) and normalize_url_for_match(url)
        }
    )
    logger.info("DEBUG retrieval normalized_allowlist=%s", normalized_allowlist)
    logger.info(
        "retrieval_grounding: provider=%s query=%s results=%d",
        used_provider,
        query[:100],
        len(sources),
    )
    return {
        "provider": used_provider,
        "query": query,
        "sources": sources,
        "url_allowlist": allowlist,
    }


def retrieve_source_pack_merged(
    *,
    queries: List[str],
    user_id: str,
    max_per_query: int | None = None,
    max_total_sources: int | None = None,
    recency_query: str | None = None,
    recency_time_range: str | None = None,
) -> Dict[str, Any]:
    """
    Run retrieval for several queries, merge by normalized URL (first occurrence wins),
    cap total sources, and re-number [S1], [S2], ... for the prompt.

    recency_query: optional extra query run with a Tavily time filter so fresh,
    dated pages (funding/M&A/leadership) actually surface. The time filter is
    scoped to ONLY this query — the identity/general queries stay unfiltered.
    """
    if max_per_query is None:
        max_per_query = max(4, min(_default_max_results(), 10))
    if max_total_sources is None:
        max_total_sources = int(os.getenv("SCOUT_RETRIEVAL_MERGED_CAP", "16"))
    max_total_sources = max(5, min(max_total_sources, 24))

    general_queries = [str(q).strip() for q in queries if str(q).strip()]
    rq = str(recency_query or "").strip()
    if not general_queries and not rq:
        return {
            "provider": "tavily",
            "query": "",
            "sources": [],
            "url_allowlist": set(),
        }

    merged_rows: List[Dict[str, str]] = []
    seen_norm: Set[str] = set()
    used_provider = "tavily"

    def _ingest(rows: List[Dict[str, str]], limit: int | None) -> None:
        added = 0
        for row in rows or []:
            if len(merged_rows) >= max_total_sources:
                return
            if limit is not None and added >= limit:
                return
            url = str(row.get("url") or "").strip()
            nu = normalize_url_for_match(url)
            if not nu or nu in seen_norm:
                continue
            seen_norm.add(nu)
            merged_rows.append(
                {
                    "title": str(row.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(row.get("snippet") or "").strip(),
                }
            )
            added += 1

    # Recency FIRST, with a reserved quota, so a breaking event (acquisition, IPO,
    # round) is never starved out of the source pack by the general queries hitting
    # the cap. The recency query runs against Tavily's news topic (recency-ranked),
    # with a general-search fallback if news returns nothing.
    if rq:
        from utils.recency import recency_window_days, tavily_time_range

        tr = recency_time_range or tavily_time_range()
        reserved = int(os.getenv("SCOUT_RECENCY_RESERVED_SLOTS", "5"))
        reserved = max(2, min(reserved, max_total_sources - 1))
        news = retrieve_source_pack(
            query=rq,
            user_id=user_id,
            max_results=max_per_query,
            time_range=tr,
            topic="news",
            days=recency_window_days(),
        )
        rows = news.get("sources") or []
        if not rows:
            rows = (
                retrieve_source_pack(
                    query=rq, user_id=user_id, max_results=max_per_query, time_range=tr
                ).get("sources")
                or []
            )
        _ingest(rows, limit=reserved)

    # General queries fill the remaining slots.
    for q in general_queries:
        if len(merged_rows) >= max_total_sources:
            break
        pack = retrieve_source_pack(query=q, user_id=user_id, max_results=max_per_query)
        _ingest(pack.get("sources"), limit=None)

    cleaned_queries = ([rq] if rq else []) + general_queries
    sources = _normalize_sources(merged_rows)
    allowlist: Set[str] = {s["url"] for s in sources if s.get("url")}
    logger.info(
        "retrieval_grounding merged: queries=%d unique_urls=%d provider=%s",
        len(cleaned_queries),
        len(sources),
        used_provider,
    )
    return {
        "provider": used_provider,
        "query": " | ".join(cleaned_queries[:4]),
        "sources": sources,
        "url_allowlist": allowlist,
    }


def render_sources_for_prompt(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return "No retrieved sources available."
    lines: List[str] = [
        "Retrieved sources (ONLY these may be cited):",
        prompt_safety_instruction(),
    ]
    for s in sources:
        snippet = isolate_untrusted_text(
            s["snippet"],
            label=f'{s["source_id"]} snippet',
        )
        safety = flag_prompt_injection(s["snippet"])
        suffix = " safety=PROMPT_INJECTION_SUSPECTED" if safety.suspicious else ""
        lines.append(
            f'[{s["source_id"]}] title="{s["title"]}" url="{s["url"]}"{suffix} snippet="{snippet}"'
        )
    return "\n".join(lines)


def log_pre_filter_cited_urls(refs: Any) -> None:
    """
    Temporary debug log for URLs cited by the model before allowlist filtering.
    """
    if not isinstance(refs, list):
        logger.info("DEBUG retrieval llm_cited_urls_pre_filter=[]")
        return
    cited: List[str] = []
    for r in refs:
        if not isinstance(r, str):
            continue
        for u in extract_http_urls(r):
            nu = normalize_url_for_match(u)
            if nu:
                cited.append(nu)
    logger.info("DEBUG retrieval llm_cited_urls_pre_filter=%s", cited)
