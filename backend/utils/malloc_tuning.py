"""glibc allocator tuning to bound RSS on small instances.

FastAPI runs sync endpoints across a threadpool, and glibc spawns one malloc
arena per thread. Each arena retains freed buffers from large transient
allocations (e.g. JSON payloads), so without a cap RSS climbs and plateaus high
instead of returning to baseline. We cap the arena count and periodically return
freed pages to the OS.

Every operation is best-effort and a no-op off glibc/Linux (e.g. macOS dev).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os

logger = logging.getLogger("malloc_tuning")

# glibc mallopt parameter id for the max arena count (from <malloc.h>: M_ARENA_MAX).
_M_ARENA_MAX = -8

# None = not yet probed; False = unavailable; otherwise the loaded CDLL.
_libc: object = None


def _get_libc():
    global _libc
    if _libc is not None:
        return _libc
    try:
        name = ctypes.util.find_library("c") or "libc.so.6"
        _libc = ctypes.CDLL(name, use_errno=True)
    except Exception as exc:  # pragma: no cover - platform dependent
        logger.debug("libc unavailable; malloc tuning disabled: %s", exc)
        _libc = False
    return _libc


def cap_malloc_arenas(max_arenas: int | None = None) -> None:
    """Limit glibc per-thread arenas so freed buffers aren't retained per-thread.

    Call once, as early as possible at startup (before the threadpool grows under
    load). Honours the MALLOC_ARENA_MAX env var; defaults to 2.
    """
    if max_arenas is None:
        try:
            max_arenas = int(os.getenv("MALLOC_ARENA_MAX", "2"))
        except ValueError:
            max_arenas = 2
    libc = _get_libc()
    if not libc or not hasattr(libc, "mallopt"):
        return
    try:
        rc = libc.mallopt(_M_ARENA_MAX, int(max_arenas))
        logger.info("mallopt(M_ARENA_MAX=%d) -> %d", max_arenas, rc)
    except Exception as exc:  # pragma: no cover - platform dependent
        logger.debug("mallopt failed: %s", exc)


def trim_malloc() -> None:
    """Return free heap pages to the OS (glibc malloc_trim). Best-effort."""
    libc = _get_libc()
    if not libc or not hasattr(libc, "malloc_trim"):
        return
    try:
        libc.malloc_trim(0)
    except Exception as exc:  # pragma: no cover - platform dependent
        logger.debug("malloc_trim failed: %s", exc)
