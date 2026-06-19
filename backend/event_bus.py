"""In-process per-user pub/sub backing the SSE stream (GET /api/stream).

Single-instance design: events are fanned out only to the SSE clients connected
to THIS process, over the one uvicorn event loop. The pipeline worker and the
SSE endpoint both run on that loop, so plain dict / asyncio.Queue access is safe
without locking — there is never an ``await`` inside a critical section, so the
event loop cannot interleave two mutations.

If the API is ever scaled to multiple instances, replace the in-process fan-out
here with a shared backplane (Redis pub/sub, Postgres LISTEN/NOTIFY, or Supabase
Realtime) behind the same ``publish()`` / ``subscribe()`` seam — callers do not
need to change.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("event_bus")

# Per-subscriber bound: a slow or stuck client must not grow memory without
# limit. When a subscriber's queue is full the OLDEST event is dropped to make
# room for the newest. This is safe because every delivered event makes the
# frontend do a full refetch (so the latest state is always recovered), and a
# slow backstop poll covers anything dropped entirely.
_MAX_QUEUED_EVENTS = 64

# user_id -> set of subscriber queues (one queue per open SSE connection).
_subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}


def subscribe(user_id: str) -> "asyncio.Queue[Dict[str, Any]]":
    """Register a new SSE subscriber for ``user_id`` and return its event queue.

    Must be called from the running event loop (the SSE endpoint does).
    """
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("subscribe requires a non-empty user_id")
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=_MAX_QUEUED_EVENTS)
    _subscribers.setdefault(uid, set()).add(queue)
    return queue


def unsubscribe(user_id: str, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
    """Remove a subscriber queue; drop the user bucket once it is empty."""
    uid = (user_id or "").strip()
    queues = _subscribers.get(uid)
    if not queues:
        return
    queues.discard(queue)
    if not queues:
        _subscribers.pop(uid, None)


def publish(user_id: str, event: Dict[str, Any]) -> int:
    """Deliver ``event`` to every subscriber of ``user_id``.

    Never raises and never blocks. When nobody is listening (the common case)
    this is a single dict lookup. If a subscriber's queue is full, its oldest
    event is dropped to make room (bounded, lossy-but-recoverable). Returns the
    number of subscribers the event reached.
    """
    uid = (user_id or "").strip()
    if not uid:
        return 0
    queues = _subscribers.get(uid)
    if not queues:
        return 0
    delivered = 0
    for queue in tuple(queues):
        if _offer(queue, event):
            delivered += 1
    return delivered


def _offer(queue: "asyncio.Queue[Dict[str, Any]]", event: Dict[str, Any]) -> bool:
    """Enqueue ``event``, evicting the oldest entry if the queue is full."""
    try:
        queue.put_nowait(event)
        return True
    except asyncio.QueueFull:
        pass
    try:
        queue.get_nowait()
    except asyncio.QueueEmpty:
        pass
    try:
        queue.put_nowait(event)
        return True
    except asyncio.QueueFull:  # pragma: no cover - only under pathological races
        logger.debug("event_bus: dropped event for a saturated subscriber")
        return False


def subscriber_count(user_id: str) -> int:
    """Open SSE connections for ``user_id`` (diagnostics / tests)."""
    return len(_subscribers.get((user_id or "").strip(), ()))


def total_subscribers() -> int:
    """Open SSE connections across all users (diagnostics / connection cap)."""
    return sum(len(queues) for queues in _subscribers.values())
