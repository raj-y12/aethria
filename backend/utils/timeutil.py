"""Timezone-aware datetime helpers.

The backend standardizes on **timezone-aware UTC** datetimes everywhere. Mixing
naive (`datetime.now()`) and aware (`datetime.now(timezone.utc)`) values is the
classic source of `TypeError: can't subtract offset-naive and offset-aware
datetimes` — and that crash only shows up at runtime on the comparison path, not
in unit tests that happen to use one or the other consistently.

Use these helpers instead of calling ``datetime.now()`` / ``datetime.utcnow()``
directly:

- ``utcnow()`` — the current time, always tz-aware UTC.
- ``ensure_aware(dt)`` — coerce a possibly-naive datetime (e.g. one parsed from a
  legacy ISO string stored without an offset) to aware UTC.
- ``parse_iso(s)`` — parse an ISO-8601 string to an aware UTC datetime, tolerating
  a trailing ``Z`` and naive (offset-less) strings. Returns ``None`` on failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce ``dt`` to tz-aware UTC. Naive datetimes are assumed to be UTC.

    ``None`` passes through so callers can use it on optional fields without a
    guard. Aware datetimes are normalized to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 string (or pass through a datetime) to aware UTC.

    Tolerates a trailing ``Z`` and offset-less ("naive") strings, which are
    treated as UTC. Returns ``None`` for empty input or unparseable strings so
    callers can fall back without a try/except at every site.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return ensure_aware(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None
