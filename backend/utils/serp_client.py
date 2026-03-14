"""
Thin SERP API client for Scouts.

Design:
- Uses SERP_API_KEY from environment.
- Rate-limited via a simple per-day budget stored in data/serp_usage.json.
- Intended for *light* enrichment only (e.g. adding 1–3 verified URLs as references),
  not for every Scout call; default budget is very low to respect a 250/month quota.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen

import certifi
from utils.settings_loader import get_scout_region, is_scout_serp_enabled, get_scout_serp_daily_budget
from supabase_doc_store import doc_get, doc_set

logger = logging.getLogger("serp")

_SERP_TABLE = "serp_usage"


def _load_usage() -> List[float]:
    data = doc_get(_SERP_TABLE)
    if isinstance(data, list):
        return [float(x) for x in data]
    return []


def _save_usage(timestamps: List[float]) -> None:
    doc_set(_SERP_TABLE, timestamps)


def _within_daily_budget(now: float) -> bool:
    """Return True if we are still under today's SERP budget."""
    if not is_scout_serp_enabled():
        return False
    budget = get_scout_serp_daily_budget()
    if budget <= 0:
        return False
    day_seconds = 24 * 60 * 60
    usage = _load_usage()
    # Keep only last 24h
    recent = [t for t in usage if now - t <= day_seconds]
    if len(recent) >= budget:
        return False
    return True


def _record_usage(now: float) -> None:
    usage = _load_usage()
    usage.append(now)
    # Keep only last 30 days to bound file size
    month_seconds = 30 * 24 * 60 * 60
    recent = [t for t in usage if now - t <= month_seconds]
    _save_usage(recent)


def _region_to_location(region: str) -> str:
    """Map internal scout_region to a SERP location string."""
    if region == "europe":
        return "Europe"
    return "World"


def _serp_search(query: str, region: str, num_results: int = 3) -> List[Dict[str, Any]]:
    """
    Call SERP API (Google search engine) and return a small list of organic results.
    Obeys simple per-day budget and silently fails closed on errors.
    """
    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        return []

    now = time.time()
    if not _within_daily_budget(now):
        logger.info("SERP budget exhausted or disabled; skipping search")
        return []

    # Use Google Light engine per SerpApi docs:
    # https://serpapi.com/google-light-api
    # We avoid the fragile `location` parameter (which often 400s) and instead
    # bias via `gl` + `google_domain`.
    if region == "europe":
        google_domain = "google.co.uk"
        gl = "uk"  # SerpApi example; approximates Europe focus
    else:
        google_domain = "google.com"
        gl = "us"

    params = {
        "engine": "google_light",
        "q": query,
        "google_domain": google_domain,
        "hl": "en",
        "gl": gl,
        "device": "desktop",
        "num": max(1, min(num_results, 10)),
        "api_key": api_key,
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)

    # Use certifi CA bundle so SSL verification works on macOS (avoids CERTIFICATE_VERIFY_FAILED)
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(url, timeout=8, context=ssl_ctx) as resp:
            payload = resp.read()
        data = json.loads(payload.decode("utf-8"))
        organic = data.get("organic_results") or []
        _record_usage(now)
        out: List[Dict[str, Any]] = []
        for item in organic[:num_results]:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            link = item.get("link")
            if not title or not link:
                continue
            out.append({"title": title, "link": link})
        return out
    except Exception as e:
        logger.warning(f"SERP search failed: {e}")
        return []


def maybe_enrich_references(output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optionally enrich ScoutOutput.references with a few SERP URLs.

    - Only runs if SERP is enabled in settings.
    - Respects per-day budget.
    - Never overwrites existing references; only appends new links.
    """
    if not is_scout_serp_enabled():
        return output

    name = (output.get("name") or "").strip()
    if not name:
        return output

    region = get_scout_region()
    sector = (output.get("sector") or "").strip()
    query_parts = [name, "startup"]
    if sector:
        query_parts.append(sector)
    if region == "europe":
        query_parts.append("Europe")
    query = " ".join(query_parts)

    results = _serp_search(query=query, region=region, num_results=3)
    if not results:
        return output

    refs = output.get("references") or []
    if not isinstance(refs, list):
        refs = []

    existing = set(str(r) for r in refs)
    for item in results:
        link = item.get("link")
        title = item.get("title")
        if not link:
            continue
        label = f"{title} - {link}" if title else link
        if label not in existing:
            refs.append(label)
            existing.add(label)

    output["references"] = refs
    return output

