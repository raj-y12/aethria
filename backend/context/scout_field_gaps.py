"""Shared Scout field gap checks used by reviewer retrieval and post-review enrichment."""
from __future__ import annotations

from typing import Any


def is_missing_tam(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def is_weak_funding_stage(value: Any) -> bool:
    if value is None:
        return True
    t = str(value).strip().lower()
    return not t or t in ("unknown", "null", "n/a", "na")
