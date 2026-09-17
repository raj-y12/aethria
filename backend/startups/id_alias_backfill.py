"""Validation and application helpers for the approved 4B.5C mapping artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ARTIFACT = Path(__file__).resolve().parents[1] / "db" / "reconciliation" / "portfolio_startup_aliases.json"
EXPECTED_MAPPING_COUNT = 133


def load_reconciliation_artifact(path: Path = ARTIFACT) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mappings = payload.get("mappings")
    if payload.get("approved_batch") != "4B.5C" or payload.get("source") != "portfolio_startups":
        raise ValueError("unexpected startup alias reconciliation artifact provenance")
    if payload.get("mapping_count") != EXPECTED_MAPPING_COUNT or len(mappings or []) != EXPECTED_MAPPING_COUNT:
        raise ValueError("startup alias reconciliation artifact must contain exactly 133 mappings")
    keys: set[tuple[str, str]] = set()
    for mapping in mappings:
        key = (str(mapping.get("user_id") or ""), str(mapping.get("legacy_startup_id") or ""))
        if not all(key) or not str(mapping.get("canonical_startup_id") or "").strip():
            raise ValueError("startup alias mapping is incomplete")
        if key in keys:
            raise ValueError(f"duplicate startup alias mapping: {key!r}")
        keys.add(key)
    return list(mappings)


def repository_rows(mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "user_id": item["user_id"],
            "legacy_startup_id": item["legacy_startup_id"],
            "canonical_startup_id": item["canonical_startup_id"],
            "source": "portfolio_startups",
            "source_reference": f"portfolio_startups:{item['legacy_startup_id']}",
            "evidence": item.get("evidence") or {},
        }
        for item in mappings
    ]
