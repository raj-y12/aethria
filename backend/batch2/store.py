"""Synchronous domain facade over an explicitly injected Batch 2 snapshot."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from batch2.context import get_state
from batch2.repository import Batch2State


def _state(explicit: Batch2State | None = None) -> Batch2State | None:
    return explicit or get_state()


def feed_cache_get(*, user_id: str, state: Batch2State | None = None) -> dict[str, Any] | None:
    current = _state(state)
    return current.get_feed_cache() if current else None


def feed_cache_set(items: list[dict[str, Any]], *, user_id: str, state: Batch2State | None = None) -> None:
    current = _state(state)
    if current is None:
        raise RuntimeError("Batch2 feed cache requires an asyncpg-backed snapshot")
    existing = current.get_feed_cache() or {"id": str(uuid4()), "user_id": user_id}
    existing.update({"cached_at": time.time(), "items": items})
    current.set_feed_cache(existing)


def rejection_patterns_get(*, user_id: str, state: Batch2State | None = None) -> dict[str, Any] | None:
    current = _state(state)
    row = current.get_rejection_patterns() if current else None
    return row.get("stats") if row else None


def rejection_patterns_set(stats: dict[str, Any], *, user_id: str, state: Batch2State | None = None) -> None:
    current = _state(state)
    if current is None:
        raise RuntimeError("Batch2 rejection patterns require an asyncpg-backed snapshot")
    existing = current.get_rejection_patterns() or {"id": str(uuid4()), "user_id": user_id}
    existing["stats"] = stats
    current.set_rejection_patterns(existing)


def metrics_get_all(*, user_id: str, state: Batch2State | None = None) -> list[dict[str, Any]]:
    current = _state(state)
    if current is None:
        return []
    return current.get_metrics()


def metric_append(record: dict[str, Any], *, user_id: str, state: Batch2State | None = None) -> str:
    current = _state(state)
    if current is None:
        raise RuntimeError("Batch2 metrics require an asyncpg-backed snapshot")
    return current.append_metric(record)
