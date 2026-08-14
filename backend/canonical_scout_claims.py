"""Bounded, deterministic Scout-to-canonical claim extraction.

This module only converts structured Scout facts when a matching source snippet
is present. Narrative Scout fields remain compatibility data and are never
promoted to claims by themselves.
"""
from __future__ import annotations

import re
import hashlib
from typing import Any, Dict, List

from evidence.models import (
    AccessClass,
    ArtifactType,
    AssertionClass,
    ClaimEvidenceLinkInput,
    ClaimInput,
    EvidenceArtifactInput,
    EvidenceItemInput,
    EvidenceRelationship,
    TrustClass,
    VerificationState,
)
from evidence.service import detect_prompt_injection
from competition_knowledge import derive_competition_claims
from commercial_knowledge import derive_commercial_claims
from tenant_context import require_user_id


_EVIDENCE_KEYS = ("snippet", "content", "excerpt", "quote", "reference", "supports")
_MATCHERS = {
    "traction_revenue": re.compile(r"\b(?:revenue|arr|mrr|customers?|pilots?|users?|usage|deployments?)\b", re.I),
    "market_size": re.compile(r"(?:\b(?:tam|total addressable market|market size)\b|\$\s?[\d,.]+\s?[mbk]\b)", re.I),
    "funding_stage": re.compile(r"\b(?:pre-?seed|seed|series\s+[a-z]|funding|raised|round)\b", re.I),
    "product_capability": re.compile(r"\b(?:product|platform|software|technology|workflow|api|infrastructure|technical)\b", re.I),
}


def _source_text(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    return " ".join(
        str(source.get(key) or "").strip()
        for key in _EVIDENCE_KEYS
        if str(source.get(key) or "").strip()
    )[:4000]


def _supporting_indexes(sources: list[dict[str, Any]], matcher: re.Pattern[str]) -> list[int]:
    return [index for index, source in enumerate(sources) if matcher.search(_source_text(source))]


def _claim(*, claim_type: str, value: dict[str, Any], sources: list[dict[str, Any]], indexes: list[int]) -> dict[str, Any]:
    first = _source_text(sources[indexes[0]])
    return {
        "claim_type": claim_type,
        "normalized_value": value,
        "display_text": first[:700],
        "assertion_class": "externally_verified",
        "confidence": 0.8,
        "support_strength": 0.8,
        "material": True,
        "_supporting_indexes": indexes,
    }


def derive_scout_claims(scout_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return only source-grounded claims for load-bearing Scout facts."""
    sources = [item for item in (scout_output.get("source_evidence") or []) if isinstance(item, dict)]
    if not sources:
        return []
    claims: list[dict[str, Any]] = []

    funding_stage = str(scout_output.get("funding_stage") or "").strip()
    indexes = _supporting_indexes(sources, _MATCHERS["funding_stage"])
    if funding_stage and funding_stage.casefold() != "unknown" and indexes:
        claims.append(_claim(claim_type="funding_stage", value={"stage": funding_stage}, sources=sources, indexes=indexes))

    est_tam = str(scout_output.get("est_tam") or "").strip()
    indexes = _supporting_indexes(sources, _MATCHERS["market_size"])
    if est_tam and indexes:
        claims.append(_claim(claim_type="market_size", value={"estimate": est_tam}, sources=sources, indexes=indexes))

    traction = scout_output.get("traction_facts")
    if isinstance(traction, dict) and traction:
        indexes = _supporting_indexes(sources, _MATCHERS["traction_revenue"])
        revenue = str(traction.get("revenue") or "").strip()
        if indexes and revenue:
            claims.append(_claim(claim_type="traction_revenue", value={"revenue": revenue}, sources=sources, indexes=indexes))

    indexes = _supporting_indexes(sources, _MATCHERS["product_capability"])
    if indexes and str(scout_output.get("solution") or "").strip():
        claims.append(_claim(
            claim_type="product_capability",
            value={"description": str(scout_output["solution"]).strip()[:500]},
            sources=sources,
            indexes=indexes,
        ))
    claims.extend(derive_competition_claims(scout_output))
    claims.extend(derive_commercial_claims(scout_output))
    return claims


async def persist_scout_claims(
    *, user_id: str, company_id: str, opportunity_id: str, observation_id: str,
    scout_output: Dict[str, Any], evidence_repository: Any,
) -> Dict[str, int]:
    """Persist source-backed Scout claims without altering the Scout payload."""
    uid = require_user_id(user_id, context="persist_scout_claims")
    sources = [item for item in (scout_output.get("source_evidence") or []) if isinstance(item, dict)]
    usable = [item for item in sources if str(item.get("url") or "").strip() and _source_text(item)]
    if not usable:
        return {"claims_created": 0, "artifacts_ingested": 0}
    usable_output = {**scout_output, "source_evidence": usable}
    claims = derive_scout_claims(usable_output)
    if not claims:
        return {"claims_created": 0, "artifacts_ingested": 0}

    evidence_items: list[Any] = []
    for source in usable:
        url = str(source.get("url") or "").strip()
        content = _source_text(source)
        access = str(source.get("access_class") or AccessClass.PUBLIC.value)
        if access not in {item.value for item in AccessClass}:
            access = AccessClass.PUBLIC.value
        artifact, items = await evidence_repository.ingest_artifact(
            EvidenceArtifactInput(
                user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
                source_observation_id=observation_id, artifact_type=ArtifactType.WEB_PAGE,
                source_uri=url, title=source.get("title"),
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                trust_class=TrustClass.OFFICIAL if source.get("official") else TrustClass.UNKNOWN,
                access_class=AccessClass(access), untrusted_input=True,
                prompt_injection_detected=detect_prompt_injection(content),
            ),
            items=[EvidenceItemInput(
                user_id=uid, item_type="scout_source_excerpt",
                normalized_value={}, display_excerpt=content[:2000], source_locator=url,
                verification_state=VerificationState.UNVERIFIED,
                source_quality=float(source.get("source_quality") or 0),
                extraction_confidence=float(source.get("confidence") or 0),
            )],
        )
        evidence_items.append(items[0])

    created = 0
    for raw in claims:
        links = [
            ClaimEvidenceLinkInput(
                user_id=uid, evidence_item_id=str(evidence_items[index].evidence_item_id),
                relationship=EvidenceRelationship.SUPPORTS,
                support_strength=float(raw.get("support_strength") or 0),
            )
            for index in raw.get("_supporting_indexes", [])
            if 0 <= index < len(evidence_items)
        ]
        await evidence_repository.create_claim(
            ClaimInput(
                user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
                claim_type=str(raw["claim_type"]), normalized_value=dict(raw.get("normalized_value") or {}),
                display_text=str(raw.get("display_text") or "").strip(),
                assertion_class=AssertionClass.EXTERNALLY_VERIFIED,
                confidence=float(raw.get("confidence") or 0), material=True,
            ),
            links=links, created_by=uid,
        )
        created += 1
    return {"claims_created": created, "artifacts_ingested": len(usable)}
