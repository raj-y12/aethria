"""
Limit concurrent pipeline / lookup work to protect single-instance hosts (e.g. Render 512MB).

- Global semaphore: cap simultaneous cycles across all users (default 1).
- Per-user lock: prevent queue worker + persistent loop from running two cycles for one user.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Dict, Optional

_global_sem: Optional[asyncio.Semaphore] = None
_user_locks: Dict[str, asyncio.Lock] = {}


def max_concurrent_pipeline_cycles() -> int:
    return max(1, int(os.getenv("MAX_CONCURRENT_PIPELINE_CYCLES", "1")))


def _get_global_sem() -> asyncio.Semaphore:
    global _global_sem
    if _global_sem is None:
        _global_sem = asyncio.Semaphore(max_concurrent_pipeline_cycles())
    return _global_sem


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
