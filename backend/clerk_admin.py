"""Small Clerk Backend API client for admin-only user/session reads."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_CLERK_API_BASE = "https://api.clerk.com/v1"
_CACHE_TTL_SECONDS = 30.0
_cache: dict[str, tuple[float, Any]] = {}


def _secret_key() -> str:
    return os.getenv("CLERK_SECRET_KEY", "").strip()


def _cache_get(key: str) -> Any | None:
    cached = _cache.get(key)
    if not cached:
        return None
    cached_at, value = cached
    if time.monotonic() - cached_at > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> Any:
    _cache[key] = (time.monotonic(), value)
    return value


def _get_json(path: str, params: Dict[str, Any] | None = None) -> Any:
    secret = _secret_key()
    if not secret:
        return None
    query = f"?{urlencode(params or {})}" if params else ""
    request = Request(
        f"{_CLERK_API_BASE}{path}{query}",
        headers={
            "Authorization": f"Bearer {secret}",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _paginated_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    return []


def list_clerk_users() -> List[Dict[str, Any]]:
    cached = _cache_get("users")
    if cached is not None:
        return cached
    try:
        payload = _get_json("/users", {"limit": 500, "offset": 0})
        return _cache_set("users", _paginated_items(payload))
    except Exception as exc:
        logger.warning("Unable to fetch Clerk users for admin overview: %s", exc)
        return _cache_set("users", [])


def list_active_sessions_by_user(user_ids: Iterable[str]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for user_id in sorted({uid for uid in user_ids if uid}):
        cache_key = f"sessions:{user_id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            out[user_id] = cached
            continue
        try:
            payload = _get_json(
                "/sessions",
                {"user_id": user_id, "status": "active", "limit": 20, "offset": 0},
            )
            out[user_id] = _cache_set(cache_key, _paginated_items(payload))
        except Exception as exc:
            logger.warning("Unable to fetch Clerk sessions for %s: %s", user_id[:12], exc)
            out[user_id] = _cache_set(cache_key, [])
    return out

