"""Shared helpers for applying Founder Resolver output to scout payloads.

Used by two call sites so both persist identical shapes and provenance:
- `ScoutEngine.run_named_lookup` — the founder stage that runs right after
  company resolution on an on-demand lookup.
- `SupabaseStorage.add_review` / `Storage` — reviewer gap enrichment, which
  previously threw its retrieval pack away once the reviewer prompt was built.

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
from typing import Any, Dict, List, Optional

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
        if name and confidence >= floor and name not in names:
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


def allow_reviewer_founder_fallback_retrieval() -> bool:
    """Whether reviewer-side founder resolution may run extra searches.

    Off by default: the reviewer path already performs blocking retrieval, and
    reusing the gap pack must not silently add another round of provider calls.
    """
    return _truthy("REVIEWER_FOUNDER_FALLBACK_RETRIEVAL", "false")


def founder_resolution_for_review(
    scout_output: Dict[str, Any],
    scout_for_llm: Dict[str, Any],
    user_id: str,
) -> Any:
    """Founder resolution for a review, reusing the reviewer gap-retrieval pack.

    Gap-fill only: returns None when the row already has founder names, so a
    review never overwrites founders the Scout stage already grounded.
    """
    if not is_founder_resolution_enabled():
        return None
    if _has_names(scout_output.get("founder_names")):
        return None
    sources = scout_for_llm.get("_reviewer_gap_sources")
    if not isinstance(sources, list) or not sources:
        return None
    pack = {
        "sources": sources,
        "provider": scout_for_llm.get("_reviewer_gap_provider"),
    }
    try:
        return founder_resolution_from_gap_pack(
            scout_output,
            user_id=user_id,
            pack=pack,
            allow_fallback_retrieval=allow_reviewer_founder_fallback_retrieval(),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("founder_enrichment: reviewer-side resolution failed: %s", exc)
        return None


def founder_resolution_from_gap_pack(
    scout: Dict[str, Any],
    *,
    user_id: str,
    pack: Optional[Dict[str, Any]] = None,
    allow_fallback_retrieval: bool = True,
) -> Any:
    """Resolve founders for a scout row, reusing an already-fetched gap pack.

    The reviewer gap retrieval pack is retrieval the pipeline has already paid
    for; feeding it to the founder extractor avoids a second round of searches
    when it already contains team/about pages. When the pack yields no founders
    and `allow_fallback_retrieval` is set, a founder-specific retrieval runs.
    """
    from resolver.founder_resolver import (
        FounderEvidence,
        build_resolution_from_evidence,
        extract_founder_candidates,
        resolve_founders,
    )

    company = str(scout.get("name") or "").strip()
    if not company or not is_founder_resolution_enabled():
        return None
    website = str(scout.get("lookup_website") or "").strip() or None

    sources = [s for s in list((pack or {}).get("sources") or []) if isinstance(s, dict)]
    if sources:
        evidence = [
            FounderEvidence(
                url=str(s.get("url") or "").strip(),
                title=str(s.get("title") or "").strip(),
                snippet=str(s.get("snippet") or "").strip()[:12000],
                supports="Founder or team evidence",
                access_class=(
                    str(s.get("access_class") or "public")
                    if str(s.get("access_class") or "public")
                    in {"public", "tenant_confidential", "restricted"}
                    else "restricted"
                ),
            )
            for s in sources
            if str(s.get("url") or "").strip()
        ]
        candidates = extract_founder_candidates(evidence)
        if candidates:
            return build_resolution_from_evidence(
                company,
                candidates,
                website=website,
                retrieval_provider=str((pack or {}).get("provider") or "") or None,
                stage="reviewer_gap_pack",
                reason="Reused the reviewer gap-retrieval pack; no extra searches.",
                sources_found=len(evidence),
            )

    # The gap pack named nobody — fall back to founder-specific retrieval only
    # when the caller accepts the extra provider round-trips.
    if not allow_fallback_retrieval:
        return None
    return resolve_founders(
        company,
        user_id=user_id,
        website=website,
        location=str(scout.get("location") or "").strip() or None,
        known_founder_names=[
            str(n).strip()
            for n in (scout.get("founder_names") or [])
            if str(n).strip()
        ],
    )
