"""
Persist reviewer / scorer-backed facts onto ScoutInfo after a successful review.

Fills gaps only (does not overwrite non-empty scout fields except reference merge).
Controlled by SCOUT_POST_REVIEW_ENRICHMENT (default on).

Env toggles (see also CLAUDE.md):
- SCOUT_POST_REVIEW_ENRICHMENT: master switch (default on).
- SCOUT_ENRICH_MIN_CONFIDENCE: min structured confidence to accept reviewer TAM (default 0.4).
- SCOUT_ENRICH_MAX_REFERENCES: cap appended gap URLs (default 12).
- SCOUT_ENRICH_INFER_FUNDING_STAGE: infer funding_stage from reviewer prose (default off; high feedback-loop risk).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from models import ScoutInfo
from research.reference_verify import extract_http_urls, normalize_url_for_match
from context.scout_field_gaps import is_missing_tam, is_weak_funding_stage

logger = logging.getLogger(__name__)

_ALLOWED_FUNDING = frozenset(
    {"Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Series C+", "Unknown"}
)


def _truthy(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).strip().lower() in ("1", "true", "yes")


def is_scout_post_review_enrichment_enabled() -> bool:
    return _truthy("SCOUT_POST_REVIEW_ENRICHMENT", "true")


def infer_funding_stage_from_review_text_enabled() -> bool:
    """When false (default), funding_stage is never inferred from reviewer narrative."""
    return _truthy("SCOUT_ENRICH_INFER_FUNDING_STAGE", "false")


def _min_conf() -> float:
    try:
        return float(os.getenv("SCOUT_ENRICH_MIN_CONFIDENCE", "0.4"))
    except ValueError:
        return 0.4


def _ref_url_keys(refs: Optional[List[Any]]) -> set[str]:
    keys: set[str] = set()
    for r in refs or []:
        if not isinstance(r, str):
            continue
        for u in extract_http_urls(r):
            k = normalize_url_for_match(u)
            if k:
                keys.add(k)
    return keys


def _tam_cell_from_review(review_output: Dict[str, Any]) -> Tuple[Optional[str], float]:
    trace = review_output.get("structured_scoring") or {}
    raw = trace.get("raw_signals") or {}
    market = raw.get("market") if isinstance(raw.get("market"), dict) else {}
    cell = market.get("tam") if isinstance(market.get("tam"), dict) else {}
    if cell:
        v = cell.get("value")
        if isinstance(v, str) and v.strip():
            try:
                c = float(cell.get("confidence", 0.5))
            except (TypeError, ValueError):
                c = 0.5
            return v.strip(), max(0.0, min(1.0, c))
    sig = review_output.get("structured_signals") or {}
    m = sig.get("market") if isinstance(sig.get("market"), dict) else {}
    tcell = m.get("tam") if isinstance(m.get("tam"), dict) else {}
    if tcell:
        v = tcell.get("value")
        if isinstance(v, str) and v.strip():
            try:
                c = float(tcell.get("confidence", 0.5))
            except (TypeError, ValueError):
                c = 0.5
            return v.strip(), max(0.0, min(1.0, c))
    return None, 0.0


def _collect_review_text_blobs(review_output: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in (
        "overall_summary",
        "investment_thesis",
        "team_analysis",
        "business_model_analysis",
        "competition_analysis",
    ):
        v = review_output.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x).strip() for x in v if isinstance(x, str) and str(x).strip())
    return " \n ".join(parts)


def infer_funding_stage_from_text(text: str) -> Optional[str]:
    """Return highest funding stage clearly mentioned (subset of ScoutInfo literals)."""
    if not text or not text.strip():
        return None
    tl = text.lower()
    if re.search(r"series\s*c\s*\+", tl) or re.search(r"\bseries\s+[def]\b", tl):
        return "Series C+"
    if re.search(r"\bseries\s+c\b", tl) and "series c+" not in tl:
        return "Series C"
    if re.search(r"\bseries\s+b\b", tl):
        return "Series B"
    if re.search(r"\bseries\s+a\b", tl):
        return "Series A"
    if "pre-seed" in tl or "pre seed" in tl or "angel round" in tl or "angel funding" in tl:
        return "Pre-Seed"
    if re.search(r"\bseed\b", tl):
        return "Seed"
    return None


def merge_scout_info_enrichment(
    scout_info: ScoutInfo,
    *,
    review_output: Dict[str, Any],
    gap_reference_urls: Optional[List[str]] = None,
) -> ScoutInfo:
    """
    Return ScoutInfo with est_tam, funding_stage, and/or references filled when previously weak.
    """
    if not is_scout_post_review_enrichment_enabled():
        return scout_info

    patches: Dict[str, Any] = {}
    min_c = _min_conf()

    if is_missing_tam(scout_info.est_tam):
        tam_s, conf = _tam_cell_from_review(review_output)
        if tam_s and conf >= min_c:
            # Ignore useless placeholder extraction
            low = tam_s.lower()
            if "scout payload" not in low and "missing" not in low[:32]:
                patches["est_tam"] = tam_s
                logger.info(
                    "scout_enrichment: filled est_tam from review (conf=%.2f)",
                    conf,
                )

    if is_weak_funding_stage(scout_info.funding_stage) and infer_funding_stage_from_review_text_enabled():
        inferred = infer_funding_stage_from_text(_collect_review_text_blobs(review_output))
        if inferred and inferred in _ALLOWED_FUNDING:
            patches["funding_stage"] = inferred
            logger.info("scout_enrichment: filled funding_stage=%s from review text", inferred)

    gap_urls = [str(u).strip() for u in (gap_reference_urls or []) if str(u).strip()]
    try:
        ref_cap = int(os.getenv("SCOUT_ENRICH_MAX_REFERENCES", "12"))
    except ValueError:
        ref_cap = 12
    ref_cap = max(4, min(ref_cap, 20))

    if gap_urls:
        refs = list(scout_info.references or [])
        seen = _ref_url_keys(refs)
        added = 0
        for u in gap_urls:
            if u.startswith("//"):
                u = "https:" + u
            if not u.lower().startswith(("http://", "https://")):
                u = "https://" + u.lstrip("/")
            nk = normalize_url_for_match(u)
            if not nk or nk in seen:
                continue
            seen.add(nk)
            refs.append(u)
            added += 1
            if len(refs) >= ref_cap:
                break
        if added:
            patches["references"] = refs[:ref_cap]
            logger.info("scout_enrichment: appended %d reference(s) from gap retrieval", added)

    if not patches:
        return scout_info

    prov = dict(scout_info.field_provenance or {})
    derived = dict(getattr(scout_info, "derived_compatibility", None) or {})
    if "est_tam" in patches:
        prov["est_tam"] = "reviewer_extraction"
        derived["est_tam"] = "reviewer_extraction"
    if "funding_stage" in patches:
        prov["funding_stage"] = "reviewer_text_inference"
        derived["funding_stage"] = "reviewer_text_inference"
    if "references" in patches:
        prov["references"] = "gap_retrieval"
        derived["references"] = "gap_retrieval"
    patches["field_provenance"] = prov
    patches["derived_compatibility"] = derived

    return scout_info.model_copy(update=patches)
