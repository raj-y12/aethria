"""Explicit boundary between canonical runtime facts and legacy JSON shapes.

This module only creates an in-memory runtime adapter. It never writes claims,
identity, evaluations, or legacy storage, and it never treats compatibility
fields as canonical authority.
"""

from __future__ import annotations

from typing import Any, Mapping


def _covered_claim(snapshot: Mapping[str, Any], criterion: str, claim_type: str) -> dict[str, Any] | None:
    contexts = snapshot.get("contexts") if isinstance(snapshot, Mapping) else None
    packet = contexts.get(criterion) if isinstance(contexts, Mapping) else None
    if not isinstance(packet, Mapping) or not packet.get("has_canonical_coverage"):
        return None
    for claim in packet.get("claims") or packet.get("current_supported_claims") or []:
        if isinstance(claim, Mapping) and str(claim.get("claim_type") or "") == claim_type:
            value = claim.get("normalized_value")
            return dict(value) if isinstance(value, Mapping) else {}
    return None


def project_scout_for_runtime(
    scout: Mapping[str, Any], canonical_context_snapshot: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Project covered canonical facts into a legacy-compatible runtime dict."""
    projected = dict(scout)
    fields: list[str] = []
    snapshot = canonical_context_snapshot if isinstance(canonical_context_snapshot, Mapping) else {}

    funding = _covered_claim(snapshot, "funding", "funding_stage")
    if funding and str(funding.get("stage") or "").strip():
        projected["funding_stage"] = str(funding["stage"]).strip()
        fields.append("funding_stage")

    market = _covered_claim(snapshot, "market", "market_size")
    if market and str(market.get("estimate") or "").strip():
        projected["est_tam"] = str(market["estimate"]).strip()
        fields.append("est_tam")

    traction = _covered_claim(snapshot, "traction", "traction_revenue")
    if traction and str(traction.get("revenue") or "").strip():
        current = projected.get("traction_facts")
        facts = dict(current) if isinstance(current, Mapping) else {}
        facts["revenue"] = str(traction["revenue"]).strip()
        projected["traction_facts"] = facts
        fields.append("traction_facts")

    projected["canonical_runtime_fields"] = fields
    return projected
