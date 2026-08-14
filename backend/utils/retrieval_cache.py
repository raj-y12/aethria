"""Shared durable retrieval cache boundary.

The cache stores observations about external retrieval, not canonical knowledge.
It is deliberately tenant-scoped in this first slice; public reuse can be added
later without changing the query/content identity model.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from tenant_context import require_user_id

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}
_CATEGORY_DEFAULT_TTL = {"news": 6 * 3600, "people": 7 * 24 * 3600, "company": 7 * 24 * 3600, "general": 24 * 3600}
_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def normalize_retrieval_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "").strip().casefold())


def normalize_retrieval_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return raw.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_PARAMS and not key.casefold().startswith("utm_")
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, urlencode(query), ""))


def build_retrieval_identity(*, query: str, category: str, time_range: str | None = None, days: int | None = None, target_company_id: str | None = None, target_person_id: str | None = None) -> str:
    normalized = "|".join(
        (
            normalize_retrieval_query(query),
            str(category or "general").strip().casefold(),
            str(time_range or "").strip().casefold(),
            str(days if days is not None else ""),
            str(target_company_id or "").strip(),
            str(target_person_id or "").strip(),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def freshness_ttl_seconds(category: str, *, environ: Mapping[str, str] | None = None) -> int:
    env = environ or os.environ
    normalized = str(category or "general").strip().casefold()
    default = _CATEGORY_DEFAULT_TTL.get(normalized, _CATEGORY_DEFAULT_TTL["general"])
    raw = env.get(f"RETRIEVAL_CACHE_TTL_{normalized.upper()}_SECONDS", str(default))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def content_hash(content: str) -> str:
    return hashlib.sha256(str(content or "").encode("utf-8")).hexdigest()


def _run_async(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


class RetrievalCache:
    """Synchronous bridge used by the synchronous provider retrieval path."""

    def __init__(self, repository: Any):
        self.repository = repository

    def get_fresh(self, *, user_id: str, query: str, category: str, time_range: str | None, days: int | None, max_results: int, target_company_id: str | None = None, target_person_id: str | None = None) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="RetrievalCache.get_fresh")
        identity = build_retrieval_identity(query=query, category=category, time_range=time_range, days=days, target_company_id=target_company_id, target_person_id=target_person_id)
        return _run_async(self.repository.get_fresh(
            user_id=uid, query_identity=identity, category=category,
            max_results=max_results, ttl_seconds=freshness_ttl_seconds(category),
        ))

    def persist_success(self, *, user_id: str, query: str, category: str, time_range: str | None, days: int | None, provider: str, diagnostics: dict[str, Any], sources: list[dict[str, Any]], max_results: int, target_company_id: str | None = None, target_person_id: str | None = None) -> dict[str, int]:
        uid = require_user_id(user_id, context="RetrievalCache.persist_success")
        identity = build_retrieval_identity(query=query, category=category, time_range=time_range, days=days, target_company_id=target_company_id, target_person_id=target_person_id)
        prepared = []
        for source in sources:
            row = dict(source)
            row["canonical_url"] = normalize_retrieval_url(row.get("url", ""))
            row["content_hash"] = content_hash(row.get("snippet", ""))
            prepared.append(row)
        return _run_async(self.repository.persist_success(
            user_id=uid, query_identity=identity, normalized_query=normalize_retrieval_query(query),
            category=category, provider=provider, diagnostics=diagnostics, sources=prepared,
            max_results=max_results, target_company_id=target_company_id,
            target_person_id=target_person_id,
        ))

    def persist_failure(self, *, user_id: str, query: str, category: str, time_range: str | None, days: int | None, provider: str, diagnostics: dict[str, Any], target_company_id: str | None = None, target_person_id: str | None = None) -> None:
        uid = require_user_id(user_id, context="RetrievalCache.persist_failure")
        identity = build_retrieval_identity(query=query, category=category, time_range=time_range, days=days, target_company_id=target_company_id, target_person_id=target_person_id)
        _run_async(self.repository.persist_failure(
            user_id=uid, query_identity=identity, category=category,
            provider=provider, diagnostics=diagnostics,
        ))


def key_lock(identity: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        return _KEY_LOCKS.setdefault(identity, threading.Lock())
