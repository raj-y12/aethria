"""Bounded, evidence-native context for regulatory evaluation.

This module deliberately stays deterministic. It turns retrieved source rows into
small claim inputs and a provenance-preserving reviewer context; it does not make
investment judgments or replace the versioned evaluation policy.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_KEYS = {"fbclid", "gclid", "ref", "utm_campaign", "utm_medium", "utm_source", "utm_term"}
_OPERATION_RE = re.compile(
    r"\b(?:operates?\s+(?:commercially|in|across|throughout)|currently serves?(?: customers)?|"
    r"commercially available|live in|launched in|delivering in)\b",
    re.IGNORECASE,
)
_EXPANSION_RE = re.compile(
    r"\b(?:expan\w*|enter\w*|launch\w*|roll\w* out)\b.{0,120}\b"
    r"(?:jurisdiction\w*|country|countries|market\w*|region\w*)\b|"
    r"\b(?:requires?|subject to)\b.{0,80}\b(?:regulatory approval|licen[cs]e|authorization)\b",
    re.IGNORECASE,
)
_BLOCKER_RE = re.compile(
    r"\b(?:prohibited|banned|illegal|not permitted|cannot operate|unable to operate|"
    r"regulatory ban|legally impossible|execution impossible)\b",
    re.IGNORECASE,
)
_JURISDICTION_RE = re.compile(
    r"\b(?:in|across|throughout)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b"
)
_CURRENT_IMPOSSIBILITY_RE = re.compile(
    r"\b(?:currently\s+)?(?:cannot|can't|unable to|impossible to|not possible to)\s+"
    r"(?:currently\s+)?(?:operate|serve|launch|commerciali[sz]e|execute)\b|"
    r"\b(?:currently\s+)?(?:regulatory|legal(?:ly)?)\s+impossib(?:le|ility)\b|"
    r"\b(?:current\s+operation|current\s+operations)\s+is\s+impossible\b",
    re.IGNORECASE,
)


def _normalized_url(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url or "").strip().lower()
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_KEYS
        )
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), query, ""))


def deduplicate_references(references: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep one source row per content/access pair while preserving order."""
    result: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in references:
        ref = dict(raw)
        content = str(ref.get("content") or ref.get("excerpt") or ref.get("url") or "").strip()
        access_class = str(ref.get("access_class") or "public").strip() or "public"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        key = (content_hash, access_class)
        if key in seen:
            continue
        seen.add(key)
        ref["url"] = str(ref.get("url") or ref.get("source_uri") or "").strip()
        ref["_normalized_url"] = _normalized_url(ref["url"])
        ref["_content_hash"] = content_hash
        result.append(ref)
    return result


def _jurisdiction(text: str) -> str | None:
    match = _JURISDICTION_RE.search(text)
    return match.group(1).strip() if match else None


def derive_regulatory_claims(references: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derive bounded, source-grounded regulatory claims from retrieved text."""
    refs = list(references)
    operation_indexes = [i for i, ref in enumerate(refs) if _OPERATION_RE.search(str(ref.get("content") or ref.get("excerpt") or ""))]
    expansion_indexes = [i for i, ref in enumerate(refs) if _EXPANSION_RE.search(str(ref.get("content") or ref.get("excerpt") or ""))]
    blocker_indexes = [i for i, ref in enumerate(refs) if _BLOCKER_RE.search(str(ref.get("content") or ref.get("excerpt") or ""))]
    claims: List[Dict[str, Any]] = []

    if operation_indexes:
        first_text = str(refs[operation_indexes[0]].get("content") or refs[operation_indexes[0]].get("excerpt") or "").strip()
        jurisdiction = _jurisdiction(first_text)
        text = first_text[:500]
        claims.append({
            "claim_type": "operational_feasibility",
            "normalized_value": {"value": True, **({"jurisdiction": jurisdiction} if jurisdiction else {})},
            "display_text": text,
            "assertion_class": "externally_verified",
            "confidence": 0.9,
            "support_strength": 0.9,
            "material": True,
            "_supporting_indexes": operation_indexes,
            "_contradicting_indexes": blocker_indexes,
        })

    if expansion_indexes:
        text = str(refs[expansion_indexes[0]].get("content") or refs[expansion_indexes[0]].get("excerpt") or "").strip()
        claims.append({
            "claim_type": "regulatory_expansion_risk",
            "normalized_value": {"value": True},
            "display_text": text[:500],
            "assertion_class": "externally_verified",
            "confidence": 0.8,
            "support_strength": 0.8,
            "material": True,
            "_supporting_indexes": expansion_indexes,
        })

    if blocker_indexes:
        text = str(refs[blocker_indexes[0]].get("content") or refs[blocker_indexes[0]].get("excerpt") or "").strip()
        claims.append({
            "claim_type": "regulatory_blocker",
            "normalized_value": {"value": True},
            "display_text": text[:500],
            "assertion_class": "externally_verified",
            "confidence": 0.85,
            "support_strength": 0.85,
            "material": True,
            "_supporting_indexes": blocker_indexes,
            "_contradicting_indexes": operation_indexes,
        })
    return claims


def assemble_regulatory_context(
    *, claims: Iterable[Dict[str, Any]], evidence: Iterable[Dict[str, Any]], max_chars: int = 4000
) -> str:
    """Render a bounded claim/evidence packet for a regulatory reviewer."""
    evidence_by_claim: Dict[str, List[Dict[str, Any]]] = {}
    for item in evidence:
        evidence_by_claim.setdefault(str(item.get("claim_id") or ""), []).append(item)
    lines: List[str] = ["REGULATORY EVIDENCE CONTEXT", "Use current operational evidence separately from future expansion risk."]
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        lines.append(
            f"CLAIM {claim_id} [{claim.get('claim_type')}] status={claim.get('status', 'current')} "
            f"confidence={float(claim.get('confidence') or 0):.2f}: {str(claim.get('display_text') or '')[:500]}"
        )
        for item in evidence_by_claim.get(claim_id, []):
            lines.append(
                f"EVIDENCE relationship={item.get('relationship')} "
                f"source={item.get('source_locator') or 'unknown'}: "
                f"{str(item.get('display_excerpt') or '')[:700]}"
            )
    rendered = "\n".join(lines)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max(0, max_chars - 24)].rstrip() + "\n[context truncated]"


def build_reviewer_regulatory_context(
    *, claims: Iterable[Dict[str, Any]], evidence: Iterable[Dict[str, Any]], max_chars: int = 4000
) -> Dict[str, Any]:
    """Build the bounded packet and deterministic grounding facts for the legacy Reviewer."""
    claim_rows = [dict(row) for row in claims]
    evidence_rows = [dict(row) for row in evidence]
    text = assemble_regulatory_context(claims=claim_rows, evidence=evidence_rows, max_chars=max_chars)
    claim_by_id = {str(row.get("claim_id") or ""): row for row in claim_rows}
    links_by_claim: Dict[str, List[Dict[str, Any]]] = {}
    for row in evidence_rows:
        links_by_claim.setdefault(str(row.get("claim_id") or ""), []).append(row)

    def has_supported(claim_type: str) -> bool:
        for claim in claim_rows:
            if claim.get("claim_type") != claim_type or claim.get("status", "current") in {
                "contradicted", "superseded", "withdrawn"
            }:
                continue
            links = links_by_claim.get(str(claim.get("claim_id") or ""), [])
            if any(
                link.get("relationship") in {"supports", "partially_establishes"}
                and link.get("verification_state", "verified") == "verified"
                and link.get("access_class", "public") in {"public", "tenant_confidential"}
                for link in links
            ):
                return True
        return False

    has_contradiction = any(
        link.get("relationship") == "contradicts"
        or claim_by_id.get(str(link.get("claim_id") or ""), {}).get("status") == "contradicted"
        for link in evidence_rows
    )
    packet = {
        "text": text,
        "chars": len(text),
        "has_verified_current_operation": has_supported("operational_feasibility"),
        "has_supported_blocker": has_supported("regulatory_blocker"),
        "has_expansion_risk": has_supported("regulatory_expansion_risk"),
        "has_contradiction": has_contradiction,
    }
    from context.assembler import add_context_contract

    return add_context_contract(
        packet,
        criterion="regulatory",
        claims=claim_rows,
        evidence=evidence_rows,
    )


def apply_regulatory_grounding_guard(value: Any, context: Dict[str, Any]) -> Any:
    """Prevent categorical current-feasibility claims unsupported by canonical evidence."""
    if isinstance(value, dict):
        return {key: apply_regulatory_grounding_guard(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [apply_regulatory_grounding_guard(item, context) for item in value]
    if not isinstance(value, str) or not _CURRENT_IMPOSSIBILITY_RE.search(value):
        return value
    if context.get("has_contradiction"):
        replacement = "Regulatory feasibility is uncertain because the current evidence is contradictory."
    elif context.get("has_verified_current_operation"):
        replacement = (
            "Current operation is supported by verified evidence; remaining regulatory risk concerns "
            "future expansion or jurisdiction-specific requirements."
        )
    elif not context.get("has_supported_blocker"):
        replacement = "Regulatory feasibility is uncertain because the available evidence is insufficient."
    else:
        return value
    return _CURRENT_IMPOSSIBILITY_RE.sub(replacement, value)


class CanonicalReviewerRegulatoryContextProvider:
    """Read the legacy startup projection through canonical async repositories."""

    def __init__(self, identity_repository: Any, evidence_repository: Any):
        self.identity_repository = identity_repository
        self.evidence_repository = evidence_repository

    async def __call__(self, user_id: str, startup_id: str) -> Dict[str, Any]:
        from tenant_context import require_user_id

        uid = require_user_id(
            user_id, context="CanonicalReviewerRegulatoryContextProvider"
        )
        opportunity = await self.identity_repository.get_opportunity_by_legacy_projection(
            user_id=uid, legacy_startup_id=startup_id
        )
        if opportunity is None:
            return build_reviewer_regulatory_context(claims=[], evidence=[])
        ledger = await self.evidence_repository.get_ledger(
            user_id=uid, opportunity_id=str(opportunity.opportunity_id)
        )
        allowed_types = {
            "operational_feasibility",
            "regulatory_expansion_risk",
            "regulatory_blocker",
        }
        claims = [
            dict(row)
            for row in ledger.get("claims", [])
            if row.get("claim_type") in allowed_types
        ]
        claim_ids = {str(row.get("claim_id")) for row in claims}
        items = {
            str(row.get("evidence_item_id")): row
            for row in ledger.get("evidence_items", [])
        }
        artifacts = {
            str(row.get("artifact_id")): row
            for row in ledger.get("artifacts", [])
        }
        evidence: List[Dict[str, Any]] = []
        for link in ledger.get("claim_evidence_links", []):
            if str(link.get("claim_id")) not in claim_ids:
                continue
            item = items.get(str(link.get("evidence_item_id")))
            artifact = artifacts.get(str(item.get("artifact_id"))) if item else None
            if not item or not artifact:
                continue
            if artifact.get("access_class") not in {"public", "tenant_confidential"}:
                continue
            if artifact.get("prompt_injection_detected"):
                continue
            evidence.append({
                **dict(link),
                "display_excerpt": item.get("display_excerpt"),
                "source_locator": item.get("source_locator") or artifact.get("source_uri"),
                "verification_state": item.get("verification_state"),
                "access_class": artifact.get("access_class"),
            })
        return build_reviewer_regulatory_context(claims=claims, evidence=evidence)
