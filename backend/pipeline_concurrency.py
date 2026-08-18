"""
Limit concurrent pipeline / lookup work to protect single-instance hosts (e.g. Render 512MB).

- Process-local semaphore: caps simultaneous cycles across all users within
  this one process (default 1) -- NOT a cluster-wide cap. Horizontally
  scaling to multiple worker processes/pods multiplies the effective
  concurrency by the process count; this does not coordinate across them.
- Per-user lock: prevent queue worker + persistent loop from running two cycles for one user.
"""
from __future__ import annotations

import asyncio
import os
import weakref
from contextlib import asynccontextmanager
from typing import Optional

_global_sem: Optional[asyncio.Semaphore] = None
_lookup_sem: Optional[asyncio.Semaphore] = None
# Weak-valued: once no coroutine holds a strong reference to a tenant's lock
# (i.e. nothing is currently waiting on/holding it), it's collected on its
# own. A plain dict grew one entry per distinct user_id ever seen, forever.
_user_locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()


def max_concurrent_pipeline_cycles() -> int:
    return max(1, int(os.getenv("MAX_CONCURRENT_PIPELINE_CYCLES", "1")))


def max_concurrent_lookups() -> int:
    return max(1, int(os.getenv("MAX_CONCURRENT_LOOKUPS", "2")))


def _get_global_sem() -> asyncio.Semaphore:
    global _global_sem
    if _global_sem is None:
        _global_sem = asyncio.Semaphore(max_concurrent_pipeline_cycles())
    return _global_sem


def _get_lookup_sem() -> asyncio.Semaphore:
    global _lookup_sem
    if _lookup_sem is None:
        _lookup_sem = asyncio.Semaphore(max_concurrent_lookups())
    return _lookup_sem


def _get_user_lock(user_id: str) -> asyncio.Lock:
    uid = user_id.strip()
    lock = _user_locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[uid] = lock
    return lock


@asynccontextmanager
async def pipeline_execution_slot(user_id: str):
    """Serialize heavy pipeline work globally and per user."""
    uid = (user_id or "").strip()
    if not uid:
        yield
        return
    sem = _get_global_sem()
    user_lock = _get_user_lock(uid)
    await sem.acquire()
    await user_lock.acquire()
    try:
        yield
    finally:
        user_lock.release()
        sem.release()


@asynccontextmanager
async def lookup_execution_slot(user_id: str):
    """Concurrency slot for on-demand lookups.

    Independent of the periodic-cycle semaphore (and its per-user lock) so a
    lookup never waits behind a full scout->reviewer->partner->portfolio->meta
    cycle. Bounded by its own MAX_CONCURRENT_LOOKUPS to protect memory.
    """
    uid = (user_id or "").strip()
    if not uid:
        yield
        return
    sem = _get_lookup_sem()
    await sem.acquire()
    try:
        yield
    finally:
        sem.release()
