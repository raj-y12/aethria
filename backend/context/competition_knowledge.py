"""Bounded, source-grounded competition knowledge extraction.

Only explicit competitor and overlap language is promoted. Reviewer judgments
such as crowded, differentiated, or strong moat remain non-canonical.
"""

from __future__ import annotations

import re
from typing import Any


_COMPETITOR_LIST = re.compile(
    r"(?i)(?:competes?\s+with|competitors?\s+(?:include|are)|alternatives?\s+(?:include|are))\s+([^.;\n]+)"
)
_SEGMENT = re.compile(r"(?i)\b(?:enterprise|smb|small and medium businesses|consumer|b2b|b2c|logistics|retail|healthcare|financial services)\b")
_GEOGRAPHY = re.compile(r"(?i)\b(?:europe|european|ireland|uk|united kingdom|us|united states|north america|asia|global)\b")
_SEPARATOR = re.compile(r"\s*(?:,|\band\b|\s/\s|\s+vs\.?\s+)\s*", re.I)
_NOISE = {"the same segment", "other platforms", "established incumbents", "several competitors"}


def _source_text(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    return " ".join(
        str(source.get(key) or "").strip()
        for key in ("snippet", "content", "excerpt", "quote", "supports")
        if str(source.get(key) or "").strip()
    )[:4000]


def _names(raw: str) -> list[str]:
    names: list[str] = []
    raw = re.split(r"(?i)\s+for\s+|\s+serving\s+|\s+across\s+", raw, maxsplit=1)[0]
    for value in _SEPARATOR.split(raw.strip(" ,:()")):
        cleaned = re.sub(r"\s+", " ", value.strip(" .,:;()[]{}"))
        if not cleaned or cleaned.casefold() in _NOISE or len(cleaned) > 100:
            continue
        if cleaned.casefold().startswith(("for ", "in ", "across ", "serving ")):
            continue
        if cleaned not in names:
            names.append(cleaned)
    return names[:10]


def derive_competition_claims(scout_output: dict[str, Any]) -> list[dict[str, Any]]:
    sources = [item for item in (scout_output.get("source_evidence") or []) if isinstance(item, dict)]
    claims: list[dict[str, Any]] = []
    company_name = str(scout_output.get("name") or "").strip()
    for index, source in enumerate(sources):
        text = _source_text(source)
        if not text:
            continue
        match = _COMPETITOR_LIST.search(text)
        if not match:
            continue
        names = _names(match.group(1))
        segments = sorted({item.group(0) for item in _SEGMENT.finditer(text)})
        geographies = sorted({item.group(0) for item in _GEOGRAPHY.finditer(text)})
        for competitor in names:
            value = {
                "target_company_name": company_name or None,
                "competitor_name": competitor,
                "source_status": "supported",
            }
            base = {
                "normalized_value": value,
                "display_text": text[:700],
                "assertion_class": "externally_verified",
                "confidence": float(source.get("confidence") or source.get("source_quality") or 0.7),
                "support_strength": 0.8,
                "material": True,
                "_supporting_indexes": [index],
            }
            claims.append({"claim_type": "competitor_existence", **base})
            claims.append({"claim_type": "competitor_product_overlap", **base})
            if segments:
                claims.append({
                    "claim_type": "competitor_segment_overlap",
                    **base,
                    "normalized_value": {**value, "segments": segments},
                })
            if geographies:
                claims.append({
                    "claim_type": "competitor_geography_overlap",
                    **base,
                    "normalized_value": {**value, "geographies": geographies},
                })
    return claims
