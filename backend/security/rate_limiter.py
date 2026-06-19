"""Tenant-aware fixed-window rate limits and short-lived queue locks."""

from __future__ import annotations

import json
import logging
import os
import env_config
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi.responses import JSONResponse

logger = logging.getLogger("security.rate_limiter")


@dataclass(frozen=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    current_count: int
    limit: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _window_start(now: datetime, window_seconds: int) -> datetime:
    ts = int(now.timestamp())
    return datetime.fromtimestamp(ts - (ts % window_seconds), tz=timezone.utc)


def rate_limit_exceeded(*, retry_after_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after_seconds": max(1, int(retry_after_seconds)),
        },
    )


class InMemorySecurityStore:
    """Process-local fallback for tests and local dev."""

    def __init__(self, *, now: Optional[Callable[[], datetime]] = None) -> None:
        self._now = now or _utcnow
        self._counters: Dict[Tuple[str, int], Tuple[int, datetime]] = {}
        self._locks: Dict[str, datetime] = {}
        self._lock = Lock()

    def increment_fixed_window(self, key: str, *, window_seconds: int) -> Tuple[int, datetime]:
        now = self._now()
        start = _window_start(now, window_seconds)
        expires_at = start + timedelta(seconds=window_seconds)
        store_key = (key, window_seconds)
        with self._lock:
            current, current_expires = self._counters.get(store_key, (0, expires_at))
            if current_expires <= now:
                current = 0
                current_expires = expires_at
            current += 1
            self._counters[store_key] = (current, current_expires)
            return current, current_expires

    def acquire_lock(self, key: str, *, ttl_seconds: int) -> bool:
        now = self._now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._lock:
            existing = self._locks.get(key)
            if existing and existing > now:
                return False
            self._locks[key] = expires_at
            return True

    def release_lock(self, key: str) -> None:
        with self._lock:
            self._locks.pop(key, None)


class SupabaseSecurityStore:
    """Supabase-backed store. Uses RPCs from the security_limits migration."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._fallback = InMemorySecurityStore()
        self._warned_fallback = False

    def _warn_once(self, exc: Exception) -> None:
        if not self._warned_fallback:
            logger.warning(
                "Supabase security RPC unavailable; using in-memory fallback until migration is applied: %s",
                exc,
            )
            self._warned_fallback = True

    def increment_fixed_window(self, key: str, *, window_seconds: int) -> Tuple[int, datetime]:
        try:
            response = self._client.rpc(
                "security_check_rate_limit",
                {
                    "p_key": key,
                    "p_window_seconds": int(window_seconds),
                },
            ).execute()
            data = getattr(response, "data", None)
            row = data[0] if isinstance(data, list) and data else data
            if not isinstance(row, dict):
                raise RuntimeError("security_check_rate_limit returned no row")
            count = int(row.get("current_count") or 0)
            expires_raw = str(row.get("expires_at") or "")
            expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
            return count, expires_at
        except Exception as exc:
            self._warn_once(exc)
            return self._fallback.increment_fixed_window(key, window_seconds=window_seconds)

    def acquire_lock(self, key: str, *, ttl_seconds: int) -> bool:
        try:
            response = self._client.rpc(
                "security_acquire_lock",
                {
                    "p_key": key,
                    "p_ttl_seconds": int(ttl_seconds),
                },
            ).execute()
            data = getattr(response, "data", None)
            if isinstance(data, list):
                data = data[0] if data else False
            return bool(data)
        except Exception as exc:
            self._warn_once(exc)
            return self._fallback.acquire_lock(key, ttl_seconds=ttl_seconds)

    def release_lock(self, key: str) -> None:
        try:
            self._client.rpc("security_release_lock", {"p_key": key}).execute()
        except Exception as exc:
            self._warn_once(exc)
            self._fallback.release_lock(key)


class FixedWindowRateLimiter:
    def __init__(
        self,
        *,
        store: InMemorySecurityStore | SupabaseSecurityStore,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._store = store
        self._now = now or _utcnow

    def check(self, key: str, policy: RateLimitPolicy) -> RateLimitDecision:
        count, expires_at = self._store.increment_fixed_window(
            f"rate:{policy.name}:{key}",
            window_seconds=policy.window_seconds,
        )
        now = self._now()
        retry_after = max(1, int((expires_at - now).total_seconds()))
        return RateLimitDecision(
            allowed=count <= policy.limit,
            retry_after_seconds=retry_after,
            current_count=count,
            limit=policy.limit,
        )


_MEMORY_STORE = InMemorySecurityStore()
_WARNED_MEMORY_FALLBACK = False


def build_security_store() -> InMemorySecurityStore | SupabaseSecurityStore:
    """Prefer Supabase in production-capable deployments; fall back to memory for dev/test."""
    global _WARNED_MEMORY_FALLBACK
    use_supabase = env_config.use_supabase_storage()
    if use_supabase and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            from supabase_client import get_service_client

            return SupabaseSecurityStore(get_service_client())
        except Exception as exc:
            logger.warning("Supabase security store unavailable; using in-memory fallback: %s", exc)
    if not _WARNED_MEMORY_FALLBACK:
        logger.warning("Using in-memory security rate-limit store; this is only suitable for local/dev.")
        _WARNED_MEMORY_FALLBACK = True
    return _MEMORY_STORE


def security_event_detail(**kwargs: Any) -> Dict[str, Any]:
    """Return JSON-serializable audit detail without leaking arbitrary objects."""
    return json.loads(json.dumps(kwargs, default=str))
