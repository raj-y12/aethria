"""Durable retrieval-cache domain: observations about external retrieval, not
canonical knowledge (tenant-scoped; see `cache.py`'s module docstring).

- cache: query/URL normalisation, TTL policy, in-process locking, and the
  `RetrievalCache` boundary Scout's research chain calls through.
- repository: the durable Postgres-backed `RetrievalCacheRepository`.

External code should import from `retrieval_cache` directly
(`from retrieval_cache import RetrievalCache`).
"""
from __future__ import annotations

from retrieval_cache.cache import (
    RetrievalCache,
    build_retrieval_identity,
    content_hash,
    freshness_ttl_seconds,
    key_lock,
    normalize_retrieval_query,
    normalize_retrieval_url,
)
from retrieval_cache.repository import RetrievalCacheRepository

__all__ = [
    "RetrievalCache",
    "RetrievalCacheRepository",
    "build_retrieval_identity",
    "content_hash",
    "freshness_ttl_seconds",
    "key_lock",
    "normalize_retrieval_query",
    "normalize_retrieval_url",
]
