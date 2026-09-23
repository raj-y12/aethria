"""Shared helpers for applying Founder Resolver output to scout payloads.

Used by Scout lookup and historical storage adapters to preserve founder provenance.

Gap-fill only: an existing non-empty `founder_names` is never overwritten. The
full structured resolution is always attached, so a weak founder result is
visible and auditable rather than silently discarded.

Env toggles:
- FOUNDER_RESOLUTION_ENABLED: master switch (default on).
- FOUNDER_RESOLUTION_MIN_CONFIDENCE: min candidate confidence to accept a name
  into `founder_names` (default 0.35). The structured resolution is stored
  regardless so low-confidence candidates stay inspectable.
- FOUNDER_RESOLUTION_MAX_NAMES: cap on promoted names (default 8, the ScoutInfo limit).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List
from resolver.founder_resolver import is_non_person_label

logger = logging.getLogger(__name__)

FOUNDER_PROVENANCE = "founder_resolver"


def _truthy(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes")


def is_founder_resolution_enabled() -> bool:
    return _truthy("FOUNDER_RESOLUTION_ENABLED", "true")


def _min_confidence() -> float:
    try:
        value = float(os.getenv("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "0.35"))
    except ValueError:
        value = 0.35
    return max(0.0, min(value, 1.0))


def _max_names() -> int:
    try:
        value = int(os.getenv("FOUNDER_RESOLUTION_MAX_NAMES", "8"))
    except ValueError:
        value = 8
    # ScoutInfo rejects more than 8 founder names.
    return max(1, min(value, 8))


def _has_names(value: Any) -> bool:
    return isinstance(value, list) and any(str(v).strip() for v in value)


def accepted_founder_names(resolution: Any) -> List[str]:
    """Names clearing the confidence floor, most confident first."""
    if resolution is None:
        return []
    floor = _min_confidence()
    names: List[str] = []
    for candidate in getattr(resolution, "founders", []) or []:
        name = str(getattr(candidate, "name", "") or "").strip()
        confidence = float(getattr(candidate, "confidence", 0.0) or 0.0)
        if name and not is_non_person_label(name) and confidence >= floor and name not in names:
            names.append(name)
    return names[: _max_names()]


def apply_founder_resolution_to_payload(
    payload: Dict[str, Any],
    resolution: Any,
) -> Dict[str, Any]:
    """Attach founder resolution to a scout payload dict (gap-fill semantics)."""
    if resolution is None:
        return payload
    out = dict(payload)
    out["founder_resolution"] = resolution.model_dump(mode="json")

    names = accepted_founder_names(resolution)
    if names and not _has_names(out.get("founder_names")):
        out["founder_names"] = names
        provenance = dict(out.get("field_provenance") or {})
        provenance["founder_names"] = FOUNDER_PROVENANCE
        out["field_provenance"] = provenance
        logger.info(
            "founder_enrichment: filled %d founder name(s) from founder resolver (status=%s)",
            len(names),
            getattr(resolution, "resolution_status", "?"),
        )
    return out


def merge_founder_resolution_into_scout_info(scout_info: Any, resolution: Any) -> Any:
    """Return ScoutInfo with founder data + provenance persisted (gap-fill only)."""
    if resolution is None:
        return scout_info

    patches: Dict[str, Any] = {"founder_resolution": resolution.model_dump(mode="json")}
    names = accepted_founder_names(resolution)
    if names and not _has_names(getattr(scout_info, "founder_names", None)):
        patches["founder_names"] = names
        provenance = dict(getattr(scout_info, "field_provenance", None) or {})
        provenance["founder_names"] = FOUNDER_PROVENANCE
        patches["field_provenance"] = provenance
        logger.info(
            "founder_enrichment: persisted %d founder name(s) onto ScoutInfo (status=%s)",
            len(names),
            getattr(resolution, "resolution_status", "?"),
        )
    return scout_info.model_copy(update=patches)
