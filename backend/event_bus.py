"""Per-user pub/sub backing the SSE stream (GET /api/stream).

Default (single-instance) design: events are fanned out only to the SSE clients
connected to THIS process, over the one uvicorn event loop. The pipeline worker
and the SSE endpoint both run on that loop, so plain dict / asyncio.Queue access
is safe without locking — there is never an ``await`` inside a critical section,
so the event loop cannot interleave two mutations.

Multi-instance backplane (opt-in): set ``EVENT_BUS_BACKPLANE=postgres`` with a
``DATABASE_URL`` (a direct Postgres connection string — Supabase exposes one)
and call :func:`start_backplane` at startup. ``publish()`` then *also* emits a
Postgres ``NOTIFY`` so sibling instances deliver the event to *their* local
subscribers, and a ``LISTEN`` connection feeds inbound notifications back into
the local fan-out. The public ``publish`` / ``subscribe`` / ``unsubscribe`` API
is unchanged, and ``publish`` still returns the number of *local* subscribers it
reached. With the backplane off, none of this code runs and behavior is
identical to before.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Set

import env_config

logger = logging.getLogger("event_bus")

# Per-subscriber bound: a slow or stuck client must not grow memory without
# limit. When a subscriber's queue is full the OLDEST event is dropped to make
# room for the newest. This is safe because every delivered event makes the
# frontend do a full refetch (so the latest state is always recovered), and a
# slow backstop poll covers anything dropped entirely.
_MAX_QUEUED_EVENTS = 64

# user_id -> set of subscriber queues (one queue per open SSE connection).
_subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}

# --- Multi-instance backplane state (only used when started) ----------------
# Unique per process so we can ignore NOTIFYs we ourselves emitted.
_INSTANCE_ID = uuid.uuid4().hex
_NOTIFY_CHANNEL = "aethria_events"
# Bound the outbound notify queue so a backplane stall can't grow memory.
_MAX_PENDING_NOTIFY = 1024

_backplane_active = False
_notify_queue: "Optional[asyncio.Queue[Dict[str, Any]]]" = None
_listen_conn: Any = None
_notify_conn: Any = None
_sender_task: "Optional[asyncio.Task]" = None


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


def _fan_out_local(user_id: str, event: Dict[str, Any]) -> int:
    """Deliver ``event`` to this process's subscribers of ``user_id``.

    Never raises and never blocks. Returns the number of local subscribers
    reached. This is the single delivery path: both ``publish`` and inbound
    backplane notifications funnel through here.
    """
    queues = _subscribers.get(user_id)
    if not queues:
        return 0
    delivered = 0
    for queue in tuple(queues):
        if _offer(queue, event):
            delivered += 1
    return delivered


def publish(user_id: str, event: Dict[str, Any]) -> int:
    """Deliver ``event`` to every *local* subscriber of ``user_id``.

    Never raises and never blocks. When nobody local is listening (the common
    case) this is a single dict lookup. Returns the number of local subscribers
    reached. When the multi-instance backplane is active, the event is also
    queued for a Postgres NOTIFY so sibling instances deliver it to their own
    local subscribers — that fan-out is fire-and-forget and does not affect the
    returned (local) count.
    """
    uid = (user_id or "").strip()
    if not uid:
        return 0
    delivered = _fan_out_local(uid, event)
    if _backplane_active and _notify_queue is not None:
        _enqueue_notify(uid, event)
    return delivered


def _enqueue_notify(user_id: str, event: Dict[str, Any]) -> None:
    """Best-effort enqueue for the outbound NOTIFY sender (drop-oldest if full)."""
    assert _notify_queue is not None
    msg = {"instance": _INSTANCE_ID, "user_id": user_id, "event": event}
    # Same bounded drop-oldest policy as subscriber delivery — reuse _offer.
    _offer(_notify_queue, msg)


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


# ---------------------------------------------------------------------------
# Multi-instance backplane (Postgres LISTEN/NOTIFY)
# ---------------------------------------------------------------------------
def backplane_enabled() -> bool:
    """True when EVENT_BUS_BACKPLANE selects the postgres backplane."""
    return (os.getenv("EVENT_BUS_BACKPLANE", "memory") or "memory").strip().lower() == "postgres"


def _database_url() -> str:
    return (os.getenv("DATABASE_URL", "") or os.getenv("SUPABASE_DB_URL", "") or "").strip()


def _on_notification(_conn: Any, _pid: int, _channel: str, payload: str) -> None:
    """asyncpg listener callback: re-deliver a sibling instance's event locally.

    Notifications we emitted ourselves are ignored (a LISTEN connection receives
    its own NOTIFYs), so an event is never double-delivered on the origin.
    """
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return
    if not isinstance(data, dict) or data.get("instance") == _INSTANCE_ID:
        return
    uid = str(data.get("user_id") or "").strip()
    event = data.get("event")
    if uid and isinstance(event, dict):
        _fan_out_local(uid, event)


async def _sender_loop() -> None:
    """Drain the outbound queue and issue Postgres NOTIFYs."""
    assert _notify_queue is not None
    while True:
        try:
            msg = await _notify_queue.get()
            try:
                if _notify_conn is not None:
                    await _notify_conn.execute(
                        "SELECT pg_notify($1, $2)", _NOTIFY_CHANNEL, json.dumps(msg)
                    )
            except Exception as e:  # pragma: no cover - transport hiccup
                logger.error(
                    "event_bus_backplane_unavailable operation=publish backend=postgres error=%s",
                    e,
                )
            finally:
                _notify_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:  # pragma: no cover - never let the sender task die
            # An unexpected error in get()/serialization must not kill the loop —
            # otherwise publish() keeps enqueuing and cross-instance fan-out is
            # silently dead while the local path still works.
            logger.warning("event_bus: sender loop iteration failed (continuing): %s", e)


Connector = Callable[[str], Awaitable[Any]]


async def start_backplane(
    *,
    dsn: Optional[str] = None,
    channel: Optional[str] = None,
    connect: Optional[Connector] = None,
) -> bool:
    """Start the Postgres LISTEN/NOTIFY backplane. Returns True if it started.

    ``connect`` is injectable for tests; in production it defaults to
    ``asyncpg.connect``. Safe to call when disabled/misconfigured — it logs and
    returns False, leaving the in-process bus fully functional.
    """
    global _backplane_active, _notify_queue, _listen_conn, _notify_conn, _sender_task, _NOTIFY_CHANNEL

    if _backplane_active:
        return True
    if connect is None and not backplane_enabled():
        return False

    resolved_dsn = (dsn or _database_url()).strip()
    if connect is None and not resolved_dsn:
        message = (
            "event_bus_backplane_unavailable; EVENT_BUS_BACKPLANE=postgres requires "
            "DATABASE_URL or SUPABASE_DB_URL"
        )
        if env_config.is_production_env() and not env_config.allow_process_local_state():
            raise RuntimeError(message)
        logger.warning("%s; using explicitly allowed local event bus", message)
        return False

    if channel:
        _NOTIFY_CHANNEL = channel

    if connect is None:
        try:
            import asyncpg  # type: ignore
        except ImportError:
            message = "event_bus_backplane_unavailable; asyncpg is not installed"
            if env_config.is_production_env() and not env_config.allow_process_local_state():
                raise RuntimeError(message)
            logger.warning("%s; using explicitly allowed local event bus", message)
            return False
        connect = asyncpg.connect

    try:
        _listen_conn = await connect(resolved_dsn)
        _notify_conn = await connect(resolved_dsn)
        await _listen_conn.add_listener(_NOTIFY_CHANNEL, _on_notification)
    except Exception as e:
        await _close_backplane_conns()
        message = f"event_bus_backplane_unavailable; postgres connection failed: {e}"
        if env_config.is_production_env() and not env_config.allow_process_local_state():
            raise RuntimeError(message) from e
        logger.warning("%s; using explicitly allowed local event bus", message)
        return False

    _notify_queue = asyncio.Queue(maxsize=_MAX_PENDING_NOTIFY)
    _sender_task = asyncio.create_task(_sender_loop())
    _backplane_active = True
    logger.info("event_bus: postgres backplane active (instance=%s channel=%s)", _INSTANCE_ID[:8], _NOTIFY_CHANNEL)
    return True


async def _close_backplane_conns() -> None:
    global _listen_conn, _notify_conn
    for conn_attr in ("_listen_conn", "_notify_conn"):
        conn = globals().get(conn_attr)
        if conn is not None:
            try:
                close = getattr(conn, "close", None)
                if close is not None:
                    res = close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as e:  # pragma: no cover
                logger.debug("event_bus: backplane conn close failed: %s", e)
    _listen_conn = None
    _notify_conn = None


async def stop_backplane() -> None:
    """Tear down the backplane (idempotent). Local subscribers are untouched."""
    global _backplane_active, _notify_queue, _sender_task
    if _sender_task is not None:
        _sender_task.cancel()
        try:
            await _sender_task
        except (asyncio.CancelledError, Exception):  # pragma: no cover
            pass
        _sender_task = None
    if _listen_conn is not None:
        try:
            await _listen_conn.remove_listener(_NOTIFY_CHANNEL, _on_notification)
        except Exception as e:  # pragma: no cover
            logger.debug("event_bus: remove_listener failed: %s", e)
    await _close_backplane_conns()
    _notify_queue = None
    _backplane_active = False
