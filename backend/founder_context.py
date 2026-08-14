"""Bounded, evidence-backed founder context for Founder-Market Fit review.

This is the founder analogue of ``regulatory_context``. It consumes the existing
Founder Resolver contract, preserves source provenance and conflicts, and emits a
small criterion-specific packet. It does not infer founder quality and does not
create a people graph.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_ALLOWED_ACCESS = {"public", "tenant_confidential"}
_UNSUPPORTED_STRENGTH_RE = re.compile(
    r"\b(?:proven|deep|extensive|exceptional|impressive|strong)\s+"
    r"(?:founder|founding|startup|technical|commercial|leadership|domain|"
    r"fundraising|prior\s+experience|track\s+record)\b",
    re.IGNORECASE,
)
_FACT_PATTERNS = (
    ("founder_startup_experience", re.compile(r"\b(?:previously\s+)?(?:founded|co-founded|started|built)\b", re.I)),
    ("founder_domain_experience", re.compile(r"\b(?:experience|expertise|businesses?|operations?)\s+(?:in|across)|\b(?:logistics|delivery|healthcare|fintech|cybersecurity|climate|robotics|aerospace)\b", re.I)),
    ("founder_technical_experience", re.compile(r"\b(?:engineering|engineer|technical|technology|software|developer|CTO|computer science)\b", re.I)),
    ("founder_leadership_experience", re.compile(r"\b(?:led|leadership|executive|managed|ran)\b", re.I)),
    ("founder_fundraising_experience", re.compile(r"\b(?:raised|fundraising|funded|venture funding|series [A-Z]|investment round)\b", re.I)),
    ("founder_exit_outcome", re.compile(r"\b(?:acquired|acquisition|exit|exited|sold|ipo|public offering)\b", re.I)),
)


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _allowed_evidence(candidate: Any) -> List[Any]:
    return [
        evidence
        for evidence in (_value(candidate, "evidence", []) or [])
        if str(_value(evidence, "access_class", "public") or "public") in _ALLOWED_ACCESS
    ]


def _claim(
    *,
    claim_type: str,
    founder_name: str,
    value: Any,
    text: str,
    evidence: Iterable[Any],
    confidence: float,
) -> Dict[str, Any]:
    sources = [str(_value(item, "url", "")).strip() for item in evidence]
    return {
        "claim_type": claim_type,
        "founder_name": founder_name,
        "normalized_value": value,
        "display_text": text[:700],
        "confidence": max(0.0, min(float(confidence or 0), 1.0)),
        "supporting_sources": [source for source in sources if source],
    }


def build_founder_context(
    resolution: Any,
    *,
    max_chars: int = 4000,
) -> Dict[str, Any]:
    """Build a bounded founder packet without converting uncertainty into praise."""
    claims: List[Dict[str, Any]] = []
    missing: set[str] = set(str(item) for item in (_value(resolution, "missing_fields", []) or []))
    founders = list(_value(resolution, "founders", []) or [])

    for candidate in founders[:8]:
        name = str(_value(candidate, "name", "")).strip()
        if not name:
            continue
        evidence = _allowed_evidence(candidate)
        if not evidence:
            missing.add("founder_identity_evidence")
            continue
        confidence = float(_value(candidate, "confidence", 0) or 0)
        claims.append(_claim(
            claim_type="founder_identity",
            founder_name=name,
            value={"name": name},
            text=f"{name} is identified in founder/team evidence.",
            evidence=evidence,
            confidence=confidence,
        ))

        role = str(_value(candidate, "role", "") or "").strip()
        if role:
            claims.append(_claim(
                claim_type="founder_current_role",
                founder_name=name,
                value={"role": role},
                text=f"{name}'s evidenced current role: {role}.",
                evidence=evidence,
                confidence=float((_value(candidate, "field_confidence", {}) or {}).get("role", confidence)),
            ))
        else:
            missing.add("current_role")

        previous = [str(item).strip() for item in (_value(candidate, "previous_employment", []) or []) if str(item).strip()]
        if previous:
            claims.append(_claim(
                claim_type="founder_previous_role",
                founder_name=name,
                value={"organizations": previous},
                text=f"{name}'s evidenced previous employment includes: {', '.join(previous)}.",
                evidence=evidence,
                confidence=float((_value(candidate, "field_confidence", {}) or {}).get("previous_employment", confidence)),
            ))
        else:
            missing.add("previous_employment")

        education = [str(item).strip() for item in (_value(candidate, "education", []) or []) if str(item).strip()]
        if education:
            claims.append(_claim(
                claim_type="founder_education",
                founder_name=name,
                value={"institutions": education},
                text=f"{name}'s evidenced education includes: {', '.join(education)}.",
                evidence=evidence,
                confidence=float((_value(candidate, "field_confidence", {}) or {}).get("education", confidence)),
            ))

        for claim_type, pattern in _FACT_PATTERNS:
            matching = [
                item for item in evidence
                if pattern.search(str(_value(item, "snippet", "") or ""))
            ]
            if matching:
                text = str(_value(matching[0], "snippet", "") or _value(matching[0], "title", "")).strip()
                claims.append(_claim(
                    claim_type=claim_type,
                    founder_name=name,
                    value={"evidenced": True},
                    text=text,
                    evidence=matching,
                    confidence=confidence,
                ))

        for conflict in (_value(candidate, "conflicts", []) or []):
            field = str(_value(conflict, "field", "unknown"))
            values = [str(item) for item in (_value(conflict, "values", []) or [])]
            sources = [str(item) for item in (_value(conflict, "source_urls", []) or [])]
            claims.append({
                "claim_type": "founder_conflict",
                "founder_name": name,
                "normalized_value": {"field": field, "values": values},
                "display_text": f"Founder fact conflict for {name}: {field} is reported as {', '.join(values)}.",
                "confidence": 0.0,
                "supporting_sources": sources,
            })

    has_identity = any(claim["claim_type"] == "founder_identity" for claim in claims)
    has_history = any(
        claim["claim_type"] not in {"founder_identity", "founder_current_role", "founder_conflict"}
        for claim in claims
    )
    has_conflict = any(claim["claim_type"] == "founder_conflict" for claim in claims)
    if founders and not has_history:
        missing.add("founder_history")
    if not founders:
        missing.update({"founder_identity", "founder_history"})

    lines = [
        "FOUNDER EVIDENCE CONTEXT",
        "Use evidenced founder history for Founder-Market Fit; do not infer founder quality from missing fields.",
    ]
    for claim in claims:
        lines.append(
            f"CLAIM [{claim['claim_type']}] founder={claim['founder_name']} "
            f"confidence={claim['confidence']:.2f}: {claim['display_text']}"
        )
        if claim["supporting_sources"]:
            lines.append(f"SOURCES: {', '.join(claim['supporting_sources'][:4])}")
    if missing:
        lines.append("UNKNOWN: " + ", ".join(sorted(missing)))
    rendered = "\n".join(lines)
    if len(rendered) > max_chars:
        rendered = rendered[: max(0, max_chars - 24)].rstrip() + "\n[context truncated]"
    packet = {
        "text": rendered,
        "chars": len(rendered),
        "claims": claims,
        "founder_count": len(founders),
        "has_verified_identity": has_identity,
        "has_history": has_history,
        "has_conflict": has_conflict,
        "missing_information": sorted(missing),
    }
    from context_assembler import add_context_contract

    founder_evidence = [
        {
            "claim_id": claim.get("claim_id") or claim.get("claim_type"),
            "relationship": "supports",
            "source_locator": source,
            "display_excerpt": claim.get("display_text"),
            "verification_state": "verified" if claim.get("confidence", 0) >= 0.8 else "unverified",
            "access_class": "public",
        }
        for claim in claims
        for source in claim.get("supporting_sources", [])
    ]
    return add_context_contract(
        packet,
        criterion="founder",
        claims=claims,
        evidence=founder_evidence,
    )


def apply_founder_grounding_guard(value: Any, context: Dict[str, Any]) -> Any:
    """Prevent unsupported founder-strength language from becoming a judgment."""
    if isinstance(value, dict):
        return {key: apply_founder_grounding_guard(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [apply_founder_grounding_guard(item, context) for item in value]
    if not isinstance(value, str) or not _UNSUPPORTED_STRENGTH_RE.search(value):
        return value
    if context.get("has_conflict"):
        replacement = "Founder-Market Fit is uncertain because founder history evidence is contradictory."
    elif not context.get("has_history"):
        replacement = "Founder-Market Fit is uncertain because the available founder history evidence is insufficient."
    else:
        return value
    return _UNSUPPORTED_STRENGTH_RE.sub(replacement, value)
