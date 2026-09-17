"""
Supabase-backed storage for list and doc JSON blobs.
Every operation requires an explicit user_id (no run_context or default tenant).
Uses get_service_client() for legacy domains that have not yet moved to the
provider-neutral Batch 1 persistence boundary.
"""
import logging
import time
import random
from typing import Any, Callable, Dict, List, TypeVar

T = TypeVar("T")
from uuid import uuid4

from tenant_context import require_user_id
from legacy_supabase.client import get_service_client

logger = logging.getLogger(__name__)

_DEFAULT_KEY = "default"

# Errno 35 = EAGAIN (Resource temporarily unavailable) under concurrent load
_TRANSIENT_ERRNOS = (35, 11)  # 11 = EAGAIN on some platforms
_MAX_RETRIES = 6
_RETRY_DELAY = 0.08


def _is_transient(e: BaseException) -> bool:
    if isinstance(e, OSError) and getattr(e, "errno", None) in _TRANSIENT_ERRNOS:
        return True
    if isinstance(e, ConnectionError):
        return True
    return False


def _retry_on_transient(fn: Callable[[], T]) -> T:
    """Run fn; on transient OSError/ConnectionError retry up to _MAX_RETRIES times."""
    last: BaseException | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < _MAX_RETRIES and _is_transient(e):
                sleep_for = (_RETRY_DELAY * (2**attempt)) + random.uniform(0, 0.05)
                time.sleep(sleep_for)
                continue
            raise
    assert last is not None
    raise last


def _run_with_retry(fn: Callable[[], T]) -> T:
    """Retry transient transport errors for both reads and writes."""
    return _retry_on_transient(fn)


def _client():
    return get_service_client()


# ---- List tables (user_id + id + data, ordered by created_at) ----
LIST_TABLES = {
    "fund_policy_versions",
    "lookup_job_outcomes",
}


def list_get_all(table: str, *, user_id: str) -> List[Dict[str, Any]]:
    """Return all rows for user as list of dicts (data column). Order by created_at."""
    uid = require_user_id(user_id, context=f"list_get_all({table})")
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


def list_get_all_strict(table: str, *, user_id: str) -> List[Dict[str, Any]]:
    """Return tenant rows while preserving transport/storage failures.

    Most legacy document consumers intentionally treat an unavailable optional
    store like an empty collection. Durable execution state cannot do that: an
    empty result means "no outcome exists", while an exception means the state
    is unknowable and must be surfaced to the caller.
    """
    uid = require_user_id(user_id, context=f"list_get_all_strict({table})")

    def _fetch():
        return (
            _client()
            .table(table)
            .select("data,created_at")
            .eq("user_id", uid)
            .order("created_at")
            .execute()
        )

    response = _retry_on_transient(_fetch)
    rows = (response.data or []) if hasattr(response, "data") else []
    return [row["data"] for row in rows if isinstance(row.get("data"), dict)]


def list_get_by_id(table: str, row_id: str, *, user_id: str) -> Dict[str, Any] | None:
    """Return data JSON for one list row (user_id, id), or None if missing."""
    uid = require_user_id(user_id, context=f"list_get_by_id({table})")
    rid = (row_id or "").strip()
    if not rid:
        return None
    try:
        def _fetch():
            return (
                _client()
                .table(table)
                .select("data")
                .eq("user_id", uid)
                .eq("id", rid)
                .limit(1)
                .execute()
            )

        r = _retry_on_transient(_fetch)
        rows = (r.data or []) if hasattr(r, "data") else []
        if not rows:
            return None
        d = rows[0].get("data")
        return d if isinstance(d, dict) else None
    except Exception as e:
        logger.warning("supabase_doc_store list_get_by_id %s %s: %s", table, rid, e)
        return None


def list_upsert(
    table: str, record: Dict[str, Any], id_field: str = "id", *, user_id: str
) -> str:
    """Insert or update by (user_id, id). record must have id_field. Returns id."""
    uid = require_user_id(user_id, context=f"list_upsert({table})")
    rid = record.get(id_field) or str(uuid4())
    if id_field != "id":
        record = dict(record)
        record["id"] = rid
    try:
        _run_with_retry(
            lambda: _client()
            .table(table)
            .upsert(
                {"user_id": uid, "id": rid, "data": record},
                on_conflict="user_id,id",
            )
            .execute()
        )
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_upsert %s: %s", table, e)
        raise


def list_append(
    table: str, record: Dict[str, Any], id_field: str = "id", *, user_id: str
) -> str:
    """Append a row for user. record gets id if missing. Returns id."""
    uid = require_user_id(user_id, context=f"list_append({table})")
    rid = record.get(id_field) or str(uuid4())
    record = dict(record)
    record["id"] = rid
    try:
        _run_with_retry(
            lambda: _client().table(table).insert({"user_id": uid, "id": rid, "data": record}).execute()
        )
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_append %s: %s", table, e)
        raise


def list_append_only(table: str, record: Dict[str, Any], *, user_id: str) -> str:
    """Append a legacy list row with a generated id. Returns id."""
    uid = require_user_id(user_id, context=f"list_append_only({table})")
    rid = str(uuid4())
    record = dict(record)
    record["id"] = rid
    try:
        _run_with_retry(
            lambda: _client().table(table).insert({"user_id": uid, "id": rid, "data": record}).execute()
        )
        return rid
    except Exception as e:
        logger.warning("supabase_doc_store list_append_only %s: %s", table, e)
        raise


# ---- Doc tables (user_id + key + data) ----
DOC_TABLES = {
    "memory",
}


def doc_get(table: str, key: str = _DEFAULT_KEY, *, user_id: str) -> Any | None:
    """Return data for (user_id, key), or None if missing."""
    uid = require_user_id(user_id, context=f"doc_get({table})")
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


def doc_get_strict(table: str, key: str = _DEFAULT_KEY, *, user_id: str) -> Any | None:
    """Return a tenant document without converting store failure to absence."""
    uid = require_user_id(user_id, context=f"doc_get_strict({table})")

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

    response = _retry_on_transient(_fetch)
    rows = (response.data or []) if hasattr(response, "data") else []
    if not rows:
        return None
    return rows[0].get("data")


def doc_set(table: str, data: Any, key: str = _DEFAULT_KEY, *, user_id: str) -> None:
    """Upsert (user_id, key) -> data."""
    uid = require_user_id(user_id, context=f"doc_set({table})")
    try:
        _run_with_retry(
            lambda: _client()
            .table(table)
            .upsert(
                {"user_id": uid, "key": key, "data": data},
                on_conflict="user_id,key",
            )
            .execute()
        )
    except Exception as e:
        logger.warning("supabase_doc_store doc_set %s %s: %s", table, key, e)
        raise


def doc_get_int(table: str, key: str = _DEFAULT_KEY, *, user_id: str) -> int:
    """Get single int (e.g. cycle counter). Returns 0 if missing."""
    val = doc_get(table, key, user_id=user_id)
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


def doc_set_int(table: str, value: int, key: str = _DEFAULT_KEY, *, user_id: str) -> None:
    """Set single int (e.g. cycle counter)."""
    doc_set(table, {"value": value}, key, user_id=user_id)
