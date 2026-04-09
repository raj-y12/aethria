"""
Thin SERP API client for Scouts.

Rate-limited via per-day budget stored in Supabase serp_usage (explicit user_id).
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import time
from typing import Any, Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen

import certifi
from tenant_context import require_user_id
from utils.settings_loader import get_scout_region, is_scout_serp_enabled, get_scout_serp_daily_budget
from supabase_doc_store import doc_get, doc_set

logger = logging.getLogger("serp")

_SERP_TABLE = "serp_usage"


def _load_usage(user_id: str) -> List[float]:
    uid = require_user_id(user_id, context="serp_usage")
    data = doc_get(_SERP_TABLE, user_id=uid)
    if isinstance(data, list):
        return [float(x) for x in data]
    return []


def _save_usage(timestamps: List[float], user_id: str) -> None:
    uid = require_user_id(user_id, context="serp_usage")
    doc_set(_SERP_TABLE, timestamps, user_id=uid)


def _within_daily_budget(now: float, user_id: str) -> bool:
    if not is_scout_serp_enabled(user_id):
        return False
    budget = get_scout_serp_daily_budget(user_id)
    if budget <= 0:
        return False
    day_seconds = 24 * 60 * 60
    usage = _load_usage(user_id)
    recent = [t for t in usage if now - t <= day_seconds]
    if len(recent) >= budget:
        return False
    return True


def _record_usage(now: float, user_id: str) -> None:
    usage = _load_usage(user_id)
    usage.append(now)
    month_seconds = 30 * 24 * 60 * 60
    recent = [t for t in usage if now - t <= month_seconds]
    _save_usage(recent, user_id)


def _serp_search(query: str, region: str, user_id: str, num_results: int = 3) -> List[Dict[str, Any]]:
    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        return []

    now = time.time()
    if not _within_daily_budget(now, user_id):
        logger.info("SERP budget exhausted or disabled; skipping search")
        return []

    if region == "europe":
        google_domain = "google.co.uk"
        gl = "uk"
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

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(url, timeout=8, context=ssl_ctx) as resp:
            payload = resp.read()
        data = json.loads(payload.decode("utf-8"))
        organic = data.get("organic_results") or []
        _record_usage(now, user_id)
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
        logger.warning("SERP search failed: %s", e)
        return []


def search_serp_results(query: str, user_id: str, num_results: int = 6) -> List[Dict[str, str]]:
    """
    Public normalized SERP search helper used by retrieval grounding fallback.
    """
    region = get_scout_region(user_id)
    rows = _serp_search(query=query, region=region, user_id=user_id, num_results=num_results)
    out: List[Dict[str, str]] = []
    for item in rows:
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        if not title or not link:
            continue
        out.append({"title": title, "url": link, "snippet": ""})
    return out


def maybe_enrich_references(output: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Optionally enrich ScoutOutput.references with a few SERP URLs (tenant-scoped budget).
    """
    require_user_id(user_id, context="maybe_enrich_references")
    if not is_scout_serp_enabled(user_id):
        return output

    name = (output.get("name") or "").strip()
    if not name:
        return output

    region = get_scout_region(user_id)
    sector = (output.get("sector") or "").strip()
    query_parts = [name, "startup"]
    if sector:
        query_parts.append(sector)
    if region == "europe":
        query_parts.append("Europe")
    query = " ".join(query_parts)

    results = _serp_search(query=query, region=region, user_id=user_id, num_results=3)
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
