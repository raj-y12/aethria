"""Shared retry-backoff schedule for provider HTTP clients."""

from __future__ import annotations


def retry_delay(attempt: int, *, base: float = 0.25, cap: float = 2.0) -> float:
    """Exponential backoff, capped, for the given zero-indexed retry attempt."""
    return min(base * (2 ** attempt), cap)
