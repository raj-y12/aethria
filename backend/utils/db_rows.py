"""Normalize direct-PostgreSQL values at the Pydantic/API boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict
from uuid import UUID


def json_ready_db_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_ready_db_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready_db_value(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready_db_value(item) for item in value]
    return value


def db_row(row: Any) -> Dict[str, Any]:
    return json_ready_db_value(dict(row))
