"""Thesis-derived retrieval queries for open scout discovery.

Open discovery used two hardcoded strings per persona:

    "{lens} early-stage startup VC funding seed series traction news"
    "{lens} startup customers pilots revenue growth founders team"

The active FundThesis was injected into the LLM prompt but never into the search,
so retrieval was mandate-blind: every cycle searched the same generic phrases and
the model was asked to find a thesis fit inside whatever came back. Sector, stage
and geography constraints now shape the queries themselves.

Deterministic and side-effect free — no LLM, no I/O. When no usable thesis is
available the persona-only queries are returned unchanged, so behaviour without a
mandate is exactly what it was.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

# Mandate facets used to steer retrieval, in priority order.
_MAX_SECTORS = 2
_MAX_GEOS = 2
_MAX_STAGES = 2


def _clean_terms(value: Any, *, limit: int) -> List[str]:
    """Lowercased, de-duplicated short phrases from a mandate list field."""
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = value
    else:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        text = re.sub(r"\s+", " ", str(item or "")).strip()
        if not text or len(text) > 48:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _default_max_queries() -> int:
    try:
        value = int(os.getenv("SCOUT_DISCOVERY_MAX_QUERIES", "3"))
    except ValueError:
        value = 3
    return max(1, min(value, 6))


def thesis_terms(thesis_ctx: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Extract the retrieval-relevant mandate facets from a thesis context."""
    if not isinstance(thesis_ctx, dict):
        return {}
    parsed = thesis_ctx.get("parsed_json")
    if not isinstance(parsed, dict):
        return {}
    terms = {
        "sectors": _clean_terms(parsed.get("sectors"), limit=_MAX_SECTORS),
        "stages": _clean_terms(parsed.get("stage_focus"), limit=_MAX_STAGES),
        "geographies": _clean_terms(parsed.get("geography"), limit=_MAX_GEOS),
    }
    return {k: v for k, v in terms.items() if v}


def build_discovery_queries(
    lens: str,
    *,
    thesis_ctx: Optional[Dict[str, Any]] = None,
    region_label: Optional[str] = None,
    max_queries: Optional[int] = None,
) -> List[str]:
    """Build open-discovery retrieval queries for one scout persona.

    `lens` is the persona's cognitive angle (e.g. "market driven"). Without a
    usable thesis this returns the original persona-only queries.
    """
    lens = re.sub(r"\s+", " ", str(lens or "")).strip()
    cap = _default_max_queries() if max_queries is None else max(1, max_queries)

    baseline = [
        f"{lens} early-stage startup VC funding seed series traction news",
        f"{lens} startup customers pilots revenue growth founders team",
    ]

    terms = thesis_terms(thesis_ctx)
    if not terms:
        return baseline[:cap]

    sectors = terms.get("sectors") or []
    stages = terms.get("stages") or []
    geographies = terms.get("geographies") or []

    sector_phrase = " OR ".join(f'"{s}"' for s in sectors)
    stage_phrase = " ".join(stages)
    geo_phrase = " ".join(geographies)

    queries: List[str] = []
    if sector_phrase:
        # Funding/momentum query anchored on the mandate's sectors and stages.
        queries.append(
            " ".join(
                part
                for part in (
                    sector_phrase,
                    "startup",
                    stage_phrase,
                    "funding round raised",
                    geo_phrase,
                )
                if part
            )
        )
        # Traction/company query, so the pack is not only funding-announcement pages.
        queries.append(
            " ".join(
                part
                for part in (
                    sector_phrase,
                    f"{lens} startup" if lens else "startup",
                    "customers pilots revenue founders team",
                    geo_phrase,
                )
                if part
            )
        )
    else:
        # Stage/geography-only mandate still narrows the generic persona query.
        queries.append(
            " ".join(
                part
                for part in (lens, "startup", stage_phrase, "funding round raised", geo_phrase)
                if part
            )
        )

    # Always keep one persona-shaped query so a narrow mandate cannot starve the
    # persona's distinct point of view out of the source pack entirely.
    queries.append(baseline[0])

    deduped: List[str] = []
    seen: set[str] = set()
    for query in queries:
        text = re.sub(r"\s+", " ", query).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped[:cap]


def build_discovery_recency_query(
    lens: str,
    *,
    thesis_ctx: Optional[Dict[str, Any]] = None,
) -> str:
    """Label for the recency/news query, narrowed to the mandate's sectors."""
    from research.recency import recency_query

    terms = thesis_terms(thesis_ctx)
    sectors = terms.get("sectors") or []
    label = f"{sectors[0]} startup" if sectors else f"{lens} startup"
    return recency_query(label)
