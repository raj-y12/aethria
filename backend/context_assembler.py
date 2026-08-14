"""Deterministic, criterion-specific assembly over canonical claims/evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from tenant_context import require_user_id


_CRITERION_CLAIMS: dict[str, set[str]] = {
    "regulatory": {"operational_feasibility", "regulatory_expansion_risk", "regulatory_blocker"},
    "founder": set(),  # founder_* is matched by prefix below
    "funding": {"funding_stage"},
    "traction": {"traction_revenue"},
    "market": {"market_size"},
    "product": {"product_capability"},
    "technical": {"product_capability"},
    "competition": {
        "competitor_existence",
        "competitor_product_overlap",
        "competitor_segment_overlap",
        "competitor_geography_overlap",
    },
    "commercial": {
        "payer_type", "revenue_model", "pricing", "revenue_amount", "gross_margin",
        "contribution_margin", "unit_economics", "customer_concentration", "retention_churn",
        "contract_structure", "customer_count",
    },
}
_ALLOWED_ACCESS = {"public", "tenant_confidential"}
_INACTIVE_STATUSES = {"stale", "superseded", "withdrawn", "revoked"}
CONTEXT_SCHEMA_VERSION = "canonical-context-v1"


def add_context_contract(
    packet: dict[str, Any],
    *,
    criterion: str,
    claims: Iterable[dict[str, Any]],
    evidence: Iterable[dict[str, Any]],
    max_chars: int = 4000,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Add the shared snapshot fields while retaining legacy packet fields."""
    claim_rows = [dict(row) for row in claims if isinstance(row, dict)]
    evidence_rows = [dict(row) for row in evidence if isinstance(row, dict)]
    supporting = [row for row in evidence_rows if row.get("relationship") in {"supports", "partially_establishes"}]
    contradicting = [row for row in evidence_rows if row.get("relationship") == "contradicts"]
    packet.update({
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "criterion": str(criterion).strip().casefold(),
        "claims": claim_rows,
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "missing_information": list(packet.get("missing_information") or []),
        "freshness": {
            "as_of": (as_of or datetime.now(timezone.utc)).isoformat(),
            "effective_timestamps": [row.get("effective_at") for row in evidence_rows if row.get("effective_at")],
            "expiry_timestamps": [row.get("expires_at") or row.get("evidence_expires_at") for row in evidence_rows if row.get("expires_at") or row.get("evidence_expires_at")],
        },
        "bounded": {"max_chars": max_chars, "actual_chars": int(packet.get("chars") or len(str(packet.get("text") or "")))},
    })
    packet.setdefault("current_supported_claims", claim_rows)
    packet.setdefault("evidence", evidence_rows)
    packet.setdefault("materially_contradicted_claims", [])
    packet.setdefault("has_canonical_coverage", bool(claim_rows and supporting))
    packet.setdefault("fallback", None if claim_rows and supporting else "legacy_context")
    return packet


def _when(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _matches(criterion: str, claim_type: str) -> bool:
    if criterion == "founder":
        return claim_type.startswith("founder_")
    return claim_type in _CRITERION_CLAIMS.get(criterion, set())


class ContextAssembler:
    """Assemble facts only; it never scores, judges, or generates narrative."""

    def assemble(
        self,
        *,
        user_id: str,
        criterion: str,
        claims: Iterable[dict[str, Any]],
        evidence: Iterable[dict[str, Any]],
        max_chars: int = 4000,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        uid = require_user_id(user_id, context="ContextAssembler.assemble")
        criterion_name = str(criterion or "").strip().casefold()
        current = now or datetime.now(timezone.utc)
        claim_rows = [dict(row) for row in claims]
        evidence_rows = [dict(row) for row in evidence]
        for row in [*claim_rows, *evidence_rows]:
            row_uid = str(row.get("user_id") or "").strip()
            if row_uid and row_uid != uid:
                raise ValueError("ContextAssembler tenant mismatch")

        eligible_evidence = []
        for row in evidence_rows:
            if str(row.get("access_class") or "public") not in _ALLOWED_ACCESS:
                continue
            if bool(row.get("prompt_injection_detected")):
                continue
            expires = _when(row.get("expires_at") or row.get("evidence_expires_at"))
            if expires is not None and expires < current:
                continue
            eligible_evidence.append(row)
        eligible_evidence.sort(key=lambda row: (
            str(row.get("claim_id") or ""),
            str(row.get("relationship") or ""),
            str(row.get("source_locator") or ""),
        ))
        evidence_by_claim: dict[str, list[dict[str, Any]]] = {}
        for row in eligible_evidence:
            evidence_by_claim.setdefault(str(row.get("claim_id") or ""), []).append(row)

        selected = [
            row for row in claim_rows
            if _matches(criterion_name, str(row.get("claim_type") or ""))
        ]
        selected.sort(key=lambda row: (str(row.get("claim_type") or ""), str(row.get("claim_id") or "")))
        supported: list[dict[str, Any]] = []
        contradicted: list[dict[str, Any]] = []
        packet_evidence: list[dict[str, Any]] = []
        missing: list[str] = []
        for claim in selected:
            claim_id = str(claim.get("claim_id") or "")
            links = evidence_by_claim.get(claim_id, [])
            if str(claim.get("status") or "current") in _INACTIVE_STATUSES:
                continue
            supports = [link for link in links if str(link.get("relationship") or "") in {"supports", "partially_establishes"}]
            contradictions = [link for link in links if str(link.get("relationship") or "") == "contradicts"]
            if supports:
                supported.append({
                    "claim_id": claim_id,
                    "claim_type": claim.get("claim_type"),
                    "normalized_value": claim.get("normalized_value") or {},
                    "display_text": str(claim.get("display_text") or "")[:700],
                    "confidence": float(claim.get("confidence") or 0),
                    "status": claim.get("status") or "current",
                })
            else:
                missing.append(str(claim.get("claim_type") or criterion_name))
            if contradictions:
                contradicted.append({
                    "claim_id": claim_id,
                    "claim_type": claim.get("claim_type"),
                    "display_text": str(claim.get("display_text") or "")[:700],
                })
            for link in [*supports, *contradictions]:
                packet_evidence.append({
                    "claim_id": claim_id,
                    "relationship": link.get("relationship"),
                    "display_excerpt": str(link.get("display_excerpt") or "")[:700],
                    "source_locator": link.get("source_locator"),
                    "access_class": link.get("access_class") or "public",
                    "verification_state": link.get("verification_state") or "unverified",
                    "source_quality": link.get("source_quality", 0),
                    "effective_at": link.get("effective_at") or link.get("evidence_effective_at"),
                    "expires_at": link.get("expires_at") or link.get("evidence_expires_at"),
                })
        if not selected or not supported:
            missing = [criterion_name] if not missing else sorted(set(missing))
        if criterion_name == "commercial":
            present_types = {str(row.get("claim_type") or "") for row in supported}
            missing.extend(sorted(_CRITERION_CLAIMS["commercial"] - present_types))

        lines = [f"CANONICAL CONTEXT [{criterion_name}]", "Use only the structured claims and evidence below; missing means unknown."]
        for claim in supported:
            lines.append(f"CLAIM [{claim['claim_type']}] confidence={claim['confidence']:.2f}: {claim['display_text']}")
        for item in packet_evidence:
            lines.append(f"EVIDENCE [{item['relationship']}] source={item['source_locator'] or 'unknown'}: {item['display_excerpt']}")
        if contradicted:
            lines.append("CONTRADICTIONS: " + ", ".join(str(item["claim_type"]) for item in contradicted))
        if missing:
            lines.append("UNKNOWN: " + ", ".join(sorted(set(missing))))
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[: max(0, max_chars - 24)].rstrip() + "\n[context truncated]"
        packet = {
            "criterion": criterion_name,
            "text": text,
            "chars": len(text),
            "current_supported_claims": supported,
            "materially_contradicted_claims": contradicted,
            "evidence": packet_evidence,
            "missing_information": sorted(set(missing)),
            "has_canonical_coverage": bool(supported),
            "fallback": None if supported else "legacy_context",
        }
        return add_context_contract(
            packet,
            criterion=criterion_name,
            claims=supported,
            evidence=packet_evidence,
            max_chars=max_chars,
            as_of=current,
        )


class CanonicalContextProvider:
    """Resolve one legacy startup to tenant-safe criterion packets."""

    def __init__(self, identity_repository: Any, evidence_repository: Any, *, assembler: ContextAssembler | None = None):
        self.identity_repository = identity_repository
        self.evidence_repository = evidence_repository
        self.assembler = assembler or ContextAssembler()

    async def __call__(self, user_id: str, startup_id: str) -> dict[str, Any]:
        uid = require_user_id(user_id, context="CanonicalContextProvider")
        opportunity = await self.identity_repository.get_opportunity_by_legacy_projection(
            user_id=uid, legacy_startup_id=startup_id
        )
        if opportunity is None:
            return {"contexts": {}, "has_canonical_coverage": False}
        ledger = await self.evidence_repository.get_ledger(
            user_id=uid, opportunity_id=str(opportunity.opportunity_id)
        )
        items = {str(row.get("evidence_item_id")): row for row in ledger.get("evidence_items", [])}
        artifacts = {str(row.get("artifact_id")): row for row in ledger.get("artifacts", [])}
        links = []
        for link in ledger.get("claim_evidence_links", []):
            item = items.get(str(link.get("evidence_item_id")))
            artifact = artifacts.get(str(item.get("artifact_id"))) if item else None
            if item is None and link.get("display_excerpt") is not None:
                item = link
            if artifact is None and link.get("access_class") is not None:
                artifact = link
            if not item or not artifact:
                continue
            links.append({
                **dict(link),
                "user_id": uid,
                "display_excerpt": item.get("display_excerpt"),
                "source_locator": item.get("source_locator") or artifact.get("source_uri"),
                "verification_state": item.get("verification_state"),
                "source_quality": item.get("source_quality", 0),
                "effective_at": item.get("effective_at") or artifact.get("effective_at"),
                "expires_at": item.get("expires_at"),
                "access_class": artifact.get("access_class", "public"),
                "prompt_injection_detected": artifact.get("prompt_injection_detected", False),
            })
        contexts = {
            criterion: self.assembler.assemble(
                user_id=uid,
                criterion=criterion,
                claims=ledger.get("claims", []),
                evidence=links,
            )
            for criterion in ("regulatory", "founder", "funding", "traction", "market", "competition", "commercial", "product", "technical")
        }
        return {
            "contexts": contexts,
            "has_canonical_coverage": any(item["has_canonical_coverage"] for item in contexts.values()),
        }
