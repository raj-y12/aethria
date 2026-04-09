"""
Thin Tavily API client for scout retrieval grounding.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
from typing import Any, Dict, List
from urllib.request import Request, urlopen

import certifi

logger = logging.getLogger("tavily")


def _normalize_result(item: Dict[str, Any]) -> Dict[str, str] | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("content") or item.get("snippet") or "").strip()
    if not title or not url:
        return None
    return {"title": title, "url": url, "snippet": snippet}


def tavily_search(query: str, max_results: int = 6, timeout: float = 8.0) -> List[Dict[str, str]]:
    """
    Return normalized Tavily results as [{title, url, snippet}, ...].
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        logger.info("Tavily key missing; retrieval disabled")
        return []

    body = {
        "api_key": api_key,
        "query": query,
        "max_results": max(1, min(int(max_results), 10)),
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    payload = json.dumps(body).encode("utf-8")
    req = Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        results = data.get("results") or []
        raw_urls = [
            str(item.get("url") or "").strip()
            for item in results
            if isinstance(item, dict) and str(item.get("url") or "").strip()
        ]
        logger.info("DEBUG tavily raw_urls=%s", raw_urls)
        out: List[Dict[str, str]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_result(item)
            if normalized:
                out.append(normalized)
        return out
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []
