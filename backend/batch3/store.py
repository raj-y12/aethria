"""Synchronous portfolio facade over an injected Batch 3 snapshot."""

from typing import Any

from batch3.context import get_state
from batch3.repository import Batch3State, TABLES


def list_get_all(table: str, *, user_id: str, state: Batch3State | None = None) -> list[dict[str, Any]]:
    current = state or get_state()
    if current is None:
        return []
    return current.get_all(table)


def list_upsert(table: str, record: dict[str, Any], *, user_id: str, state: Batch3State | None = None) -> str:
    current = state or get_state()
    if current is None:
        raise RuntimeError("Batch3 portfolio collection requires an asyncpg-backed snapshot")
    return current.upsert(table, record)


def list_replace(table: str, records: list[dict[str, Any]], *, user_id: str, state: Batch3State | None = None) -> None:
    current = state or get_state()
    if current is None:
        raise RuntimeError("Batch3 portfolio collection requires an asyncpg-backed snapshot")
    current.replace(table, records)
