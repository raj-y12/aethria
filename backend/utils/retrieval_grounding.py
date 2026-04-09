"""
Scout retrieval grounding: provider selection, source normalization, and prompt context.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from utils.reference_verify import extract_http_urls, normalize_url_for_match
from utils.settings_loader import get_scout_retrieval_provider
from utils.tavily_client import tavily_search

logger = logging.getLogger("retrieval_grounding")


def _source_id(i: int) -> str:
    return f"S{i + 1}"


def _normalize_sources(raw_results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for i, row in enumerate(raw_results):
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        if not title or not url:
            continue
        out.append(
            {
                "source_id": _source_id(i),
                "title": title,
                "url": url,
                "snippet": snippet[:600],
            }
        )
    return out


def retrieve_source_pack(*, query: str, user_id: str, max_results: int = 6) -> Dict[str, Any]:
    """
    Build retrieval source pack with provider metadata and URL allowlist.
    """
    provider = get_scout_retrieval_provider(user_id)
    raw: List[Dict[str, str]] = []
    used_provider = provider

    if provider == "tavily":
        raw = tavily_search(query=query, max_results=max_results)
        if not raw:
            try:
                from utils.serp_client import search_serp_results

                raw = search_serp_results(query=query, user_id=user_id, num_results=max_results)
                if raw:
                    used_provider = "serpapi"
            except Exception:
                raw = []
    elif provider == "serpapi":
        from utils.serp_client import search_serp_results

        raw = search_serp_results(query=query, user_id=user_id, num_results=max_results)

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


def render_sources_for_prompt(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return "No retrieved sources available."
    lines: List[str] = [
        "Retrieved sources (ONLY these may be cited):",
    ]
    for s in sources:
        lines.append(
            f'[{s["source_id"]}] title="{s["title"]}" url="{s["url"]}" snippet="{s["snippet"]}"'
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
