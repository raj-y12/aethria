"""
Supabase-backed storage for list and doc JSON blobs.
All tables are multi-tenant: pass user_id or it is taken from run context (get_run_user_id()).
Uses get_service_client(); tables: portfolio_*, memory, settings, serp_usage, analytics_*, meta_*.
"""
import logging
import time
import random
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")
from uuid import uuid4

from run_context import get_run_user_id
from supabase_client import get_service_client

logger = logging.getLogger(__name__)

_DEFAULT_KEY = "default"
_DEFAULT_USER = "default"
_warned_default_user_fallback = False

# Errno 35 = EAGAIN (Resource temporarily unavailable) under concurrent load
_TRANSIENT_ERRNOS = (35, 11)  # 11 = EAGAIN on some platforms
_MAX_RETRIES = 4
_RETRY_DELAY = 0.12


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, OSError) and getattr(e, "errno", None) in _TRANSIENT_ERRNOS:
        return True
    if isinstance(e, ConnectionError):
        return True
    return False


def _retry_on_transient(fn: Callable[[], T]) -> T:
    """Run fn; on transient OSError/ConnectionError retry up to _MAX_RETRIES times."""
    last: Optional[BaseException] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < _MAX_RETRIES and _is_transient(e):
                # Exponential backoff with small jitter to avoid synchronized retries.
                sleep_for = (_RETRY_DELAY * (2 ** attempt)) + random.uniform(0, 0.05)
                time.sleep(sleep_for)
                continue
            raise
    assert last is not None
    raise last


def _client():
    return get_service_client()


def _user_id(user_id: Optional[str]) -> str:
    """Resolve user_id: explicit or run context; fallback to _DEFAULT_USER for backward compatibility."""
    global _warned_default_user_fallback
    if user_id and user_id.strip():
        return user_id.strip()
    ctx = get_run_user_id()
    if ctx and ctx.strip():
        return ctx.strip()
    if not _warned_default_user_fallback:
        logger.warning(
            "supabase_doc_store using fallback user_id='default' (no explicit user_id and no run context). "
            "This may mix data across tenants in non-request code paths."
        )
        _warned_default_user_fallback = True
    return _DEFAULT_USER


# ---- List tables (user_id + id + data, ordered by created_at) ----
LIST_TABLES = {
    "portfolio_decisions",
    "portfolio_positions",
    "portfolio_rejections",
    "portfolio_watchlist",
    "portfolio_signals",
    "portfolio_agent_metrics",
    "meta_mutation_log",
    "meta_reports",
}


def list_get_all(table: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all rows for user as list of dicts (data column). Order by created_at."""
    uid = _user_id(user_id)
    try:
        def _fetch():
            return (
                _client()
                .table(table)
                .select("data,created_at")
                .eq("user_id", uid)
                .order("created_at")
                .execute()
            )
        r = _retry_on_transient(_fetch)
        rows = (r.data or []) if hasattr(r, "data") else []
        out = []
        for row in rows:
            d = row.get("data")
            if isinstance(d, dict):
                out.append(d)
        return out
    except Exception as e:
        logger.warning("supabase_doc_store list_get_all %s: %s", table, e)
        return []


def list_upsert(
    table: str, record: Dict[str, Any], id_field: str = "id", user_id: Optional[str] = None
) -> str:
    """Insert or update by (user_id, id). record must have id_field. Returns id."""
    uid = _user_id(user_id)
    rid = record.get(id_field) or str(uuid4())
    if id_field != "id":
        record = dict(record)
        record["id"] = rid
    try:
        _client().table(table).upsert(
            {"user_id": uid, "id": rid, "data": record},
            on_conflict="user_id,id",
        ).execute()
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_upsert %s: %s", table, e)
        raise


def list_append(
    table: str, record: Dict[str, Any], id_field: str = "id", user_id: Optional[str] = None
) -> str:
    """Append a row for user. record gets id if missing. Returns id."""
    uid = _user_id(user_id)
    rid = record.get(id_field) or str(uuid4())
    record = dict(record)
    record["id"] = rid
    try:
        _client().table(table).insert({"user_id": uid, "id": rid, "data": record}).execute()
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_append %s: %s", table, e)
        raise


def list_append_only(table: str, record: Dict[str, Any], user_id: Optional[str] = None) -> str:
    """Append with generated id (for mutation_log, meta_reports). Returns id."""
    uid = _user_id(user_id)
    rid = str(uuid4())
    record = dict(record)
    record["id"] = rid
    try:
        _client().table(table).insert({"user_id": uid, "id": rid, "data": record}).execute()
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_append_only %s: %s", table, e)
        raise


# ---- Doc tables (user_id + key + data) ----
DOC_TABLES = {
    "portfolio_budgets",
    "memory",
    "settings",
    "serp_usage",
    "analytics_sector_concentration",
    "meta_prompt_library",
    "meta_scout_weights",
    "meta_calibration_state",
    "meta_cycle_counters",
}


def doc_get(table: str, key: str = _DEFAULT_KEY, user_id: Optional[str] = None) -> Optional[Any]:
    """Return data for (user_id, key), or None if missing."""
    uid = _user_id(user_id)
    try:
        def _fetch():
            return (
                _client()
                .table(table)
                .select("data")
                .eq("user_id", uid)
                .eq("key", key)
                .limit(1)
                .execute()
            )
        r = _retry_on_transient(_fetch)
        rows = (r.data or []) if hasattr(r, "data") else []
        if not rows:
            return None
        return rows[0].get("data")
    except Exception as e:
        logger.warning("supabase_doc_store doc_get %s %s: %s", table, key, e)
        return None


def doc_set(
    table: str, data: Any, key: str = _DEFAULT_KEY, user_id: Optional[str] = None
) -> None:
    """Upsert (user_id, key) -> data."""
    uid = _user_id(user_id)
    try:
        _client().table(table).upsert(
            {"user_id": uid, "key": key, "data": data},
            on_conflict="user_id,key",
        ).execute()
    except Exception as e:
        logger.warning("supabase_doc_store doc_set %s %s: %s", table, key, e)
        raise


def doc_get_int(
    table: str, key: str = _DEFAULT_KEY, user_id: Optional[str] = None
) -> int:
    """Get single int (e.g. cycle counter). Returns 0 if missing."""
    val = doc_get(table, key, user_id)
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    if isinstance(val, dict) and "value" in val:
        return int(val["value"]) if val["value"] is not None else 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def doc_set_int(
    table: str, value: int, key: str = _DEFAULT_KEY, user_id: Optional[str] = None
) -> None:
    """Set single int (e.g. cycle counter)."""
    doc_set(table, {"value": value}, key, user_id)
