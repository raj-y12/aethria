"""
Thin Tavily API client for scout retrieval grounding.

Env (optional):
  TAVILY_SEARCH_DEPTH=basic|advanced (default advanced — richer snippets, more credits)
  TAVILY_INCLUDE_RAW_CONTENT=0|1 (default 1 — uses raw page text when returned, capped)
  TAVILY_RAW_CONTENT_MAX_CHARS (default 4500) — per-result cap to control prompt size
  TAVILY_MAX_RESULTS_CAP (default 15) — upper bound passed to the API
  TAVILY_TIMEOUT seconds (default 12)
"""
from __future__ import annotations

import json
import logging
import os
import ssl
from typing import Any, Dict, List
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import certifi

logger = logging.getLogger("tavily")


def _tavily_body_config(max_results: int) -> tuple[int, str, bool, int, float]:
    cap = int(os.getenv("TAVILY_MAX_RESULTS_CAP", "15"))
    cap = max(5, min(cap, 20))
    n = max(1, min(int(max_results), cap))
    depth = os.getenv("TAVILY_SEARCH_DEPTH", "advanced").strip().lower()
    if depth not in ("basic", "advanced"):
        depth = "advanced"
    raw_flag = os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    raw_max = int(os.getenv("TAVILY_RAW_CONTENT_MAX_CHARS", "4500"))
    raw_max = max(800, min(raw_max, 12000))
    timeout = float(os.getenv("TAVILY_TIMEOUT", "12.0"))
    timeout = max(4.0, min(timeout, 45.0))
    return n, depth, raw_flag, raw_max, timeout


def _normalize_result(
    item: Dict[str, Any],
    *,
    raw_max_chars: int,
    include_raw: bool,
) -> Dict[str, str] | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("content") or item.get("snippet") or "").strip()
    if include_raw:
        raw = str(item.get("raw_content") or "").strip()
        if raw:
            snippet = raw if len(raw) <= raw_max_chars else raw[:raw_max_chars]
    if not title or not url:
        return None
    return {"title": title, "url": url, "snippet": snippet}


def tavily_search(query: str, max_results: int = 10, timeout: float | None = None) -> List[Dict[str, str]]:
    """
    Return normalized Tavily results as [{title, url, snippet}, ...].
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        logger.info("Tavily key missing; retrieval disabled")
        return []

    n, depth, raw_flag, raw_max, default_timeout = _tavily_body_config(max_results)
    eff_timeout = default_timeout if timeout is None else float(timeout)

    body = {
        "api_key": api_key,
        "query": query,
        "max_results": n,
        "search_depth": depth,
        "include_answer": False,
        "include_raw_content": raw_flag,
    }
    payload = json.dumps(body).encode("utf-8")
    req = Request(
        "https://api.tavily.com/search",
        data=payload,
        # Tavily's current standard is Bearer auth; the legacy `api_key` in the body is
        # kept too for backward compatibility. Sending the header avoids silent auth
        # failures (and therefore empty retrieval) if the legacy body method is rejected.
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(req, timeout=eff_timeout, context=ssl_ctx) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        results = data.get("results") or []
        raw_urls = [
            str(item.get("url") or "").strip()
            for item in results
            if isinstance(item, dict) and str(item.get("url") or "").strip()
        ]
        logger.debug("tavily depth=%s raw=%s raw_urls=%s", depth, raw_flag, raw_urls)
        out: List[Dict[str, str]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_result(
                item,
                raw_max_chars=raw_max,
                include_raw=raw_flag,
            )
            if normalized:
                out.append(normalized)
        return out
    except HTTPError as e:
        # Surface the status + Tavily's error detail (e.g. invalid api key, usage limit
        # exceeded) so a dark-retrieval outage is diagnosable from logs instead of silent.
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        logger.warning("Tavily search failed: HTTP %s %s", getattr(e, "code", "?"), detail)
        return []
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []
