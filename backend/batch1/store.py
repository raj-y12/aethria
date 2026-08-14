"""Batch 1 storage facade.

When an async pipeline/request has preloaded a Batch1State, these operations are
pure in-memory work and are flushed through Batch1Repository at the boundary.
The legacy fallback exists only for isolated legacy/unit seams without a pool.
"""

from __future__ import annotations

from typing import Any

from batch1.context import get_state

_BATCH1_DOCUMENTS = frozenset({
    "analytics_sector_concentration",
    "portfolio_budgets",
    "meta_prompt_library",
    "meta_scout_weights",
    "meta_calibration_state",
    "meta_cycle_counters",
    "meta_churn_signals",
})
_BATCH1_LISTS = frozenset({"meta_mutation_log", "meta_reports"})
_OFFLINE_DOCUMENTS: dict[tuple[str, str, str], Any] = {}
_OFFLINE_LISTS: dict[tuple[str, str], list[dict[str, Any]]] = {}


def doc_get(table: str, key: str = "default", *, user_id: str) -> Any | None:
    state = get_state()
    if state is not None:
        try:
            return state.get_document(table, key)
        except ValueError:
            pass
    if table in _BATCH1_DOCUMENTS:
        return _OFFLINE_DOCUMENTS.get((user_id, table, key))
    raise ValueError(f"table is outside Batch 1 persistence: {table}")


def doc_set(table: str, data: Any, key: str = "default", *, user_id: str) -> None:
    state = get_state()
    if state is not None:
        try:
            state.set_document(table, data, key)
            return
        except ValueError:
            pass
    if table in _BATCH1_DOCUMENTS:
        _OFFLINE_DOCUMENTS[(user_id, table, key)] = data
        return
    raise ValueError(f"table is outside Batch 1 persistence: {table}")


def doc_get_int(table: str, key: str = "default", *, user_id: str) -> int:
    state = get_state()
    if state is not None:
        try:
            value = state.get_document(table, key)
            if value is None:
                return 0
            if isinstance(value, int):
                return value
            if isinstance(value, dict) and "value" in value:
                return int(value["value"] or 0)
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        except ValueError:
            pass
    if table in _BATCH1_DOCUMENTS:
        value = _OFFLINE_DOCUMENTS.get((user_id, table, key))
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, dict) and "value" in value:
            return int(value["value"] or 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    raise ValueError(f"table is outside Batch 1 persistence: {table}")


def doc_set_int(table: str, value: int, key: str = "default", *, user_id: str) -> None:
    state = get_state()
    if state is not None:
        try:
            state.set_document(table, {"value": value}, key)
            return
        except ValueError:
            pass
    if table in _BATCH1_DOCUMENTS:
        _OFFLINE_DOCUMENTS[(user_id, table, key)] = {"value": value}
        return
    raise ValueError(f"table is outside Batch 1 persistence: {table}")


def list_get_all(table: str, *, user_id: str) -> list[dict[str, Any]]:
    state = get_state()
    if state is not None:
        try:
            return state.get_list(table)
        except ValueError:
            pass
    if table in _BATCH1_LISTS:
        return list(_OFFLINE_LISTS.get((user_id, table), []))
    raise ValueError(f"table is outside Batch 1 persistence: {table}")


def list_append_only(table: str, record: dict[str, Any], *, user_id: str) -> str:
    state = get_state()
    if state is not None:
        try:
            return state.append_list(table, record)
        except ValueError:
            pass
    if table in _BATCH1_LISTS:
        from uuid import uuid4
        item = dict(record)
        item["id"] = str(item.get("id") or uuid4())
        _OFFLINE_LISTS.setdefault((user_id, table), []).append(item)
        return item["id"]
    raise ValueError(f"table is outside Batch 1 persistence: {table}")
