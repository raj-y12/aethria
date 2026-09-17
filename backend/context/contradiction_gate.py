"""Deterministic evidence-vs-judgment guard for downstream review outputs."""
from __future__ import annotations

import re
from typing import Any

from tenant_context import require_user_id


DIRECT_NEGATIVE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "regulatory": (
        re.compile(r"\b(?:not|non[- ]?)operational\b", re.I),
        re.compile(r"\bexecution\s+(?:is\s+)?impossible\b", re.I),
        re.compile(r"\bunable\s+to\s+operate\b", re.I),
    ),
    "founder": (
        re.compile(r"\bno\s+(?:relevant\s+)?(?:founder|operating|executive)\s+experience\b", re.I),
        re.compile(r"\bfounder(?:s)?\s+(?:have|has)\s+no\s+relevant\s+experience\b", re.I),
    ),
    "traction": (
        re.compile(r"\bno\s+(?:traction|revenue|customers?)\b", re.I),
        re.compile(r"\b(?:zero|no)\s+commercial\s+(?:traction|activity)\b", re.I),
    ),
    "funding": (
        re.compile(r"\b(?:unfunded|no\s+funding(?:\s+history)?|has\s+not\s+raised)\b", re.I),
    ),
    "product": (
        re.compile(r"\btechnically\s+infeasible\b", re.I),
        re.compile(r"\bproduct\s+(?:is\s+)?not\s+(?:deployed|operational|live)\b", re.I),
    ),
    "competition": (
        re.compile(r"\bno\s+(?:credible\s+|direct\s+|meaningful\s+)?competition\b", re.I),
        re.compile(r"\bno\s+(?:credible\s+|direct\s+)?competitors?\b", re.I),
    ),
    "commercial": (
        re.compile(r"\bno\s+recurring\s+revenue\b", re.I),
        re.compile(r"\bno\s+subscription\s+revenue\b", re.I),
    ),
}

_MATERIAL_FIELDS = (
    "overall_summary", "key_risks", "team_analysis", "competition_analysis", "business_model_analysis", "investment_thesis",
    "market_reasoning", "market_weaknesses", "product_reasoning", "product_weaknesses",
    "technical_reasoning", "technical_weaknesses", "execution_reasoning", "execution_weaknesses",
    "risks", "decision_rationale", "market_insight", "product_edge", "traction_signals",
    "thesis", "why_this_matters", "thesis_fit_points", "thesis_deviation_points",
)
_SUPPORTED_CLAIM_TYPES = {
    "regulatory": {"operational_feasibility", "regulatory_expansion_risk", "regulatory_blocker"},
    "founder": set(),
    "funding": {"funding_stage"},
    "traction": {"traction_revenue"},
    "market": {"market_size"},
    "product": {"product_capability"},
    "competition": {"competitor_existence"},
    "commercial": {"revenue_model", "revenue_amount", "gross_margin", "contribution_margin", "unit_economics", "retention_churn"},
}


def _criterion_for_claim(claim_type: str) -> str | None:
    if claim_type.startswith("founder_"):
        return "founder"
    for criterion, types in _SUPPORTED_CLAIM_TYPES.items():
        if claim_type in types:
            return criterion
    return None


def _packet_state(packet: dict[str, Any], *, user_id: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    supported = [dict(row) for row in packet.get("current_supported_claims", []) if isinstance(row, dict)]
    contradicted = [dict(row) for row in packet.get("materially_contradicted_claims", []) if isinstance(row, dict)]
    evidence = []
    for row in packet.get("evidence", []):
        if not isinstance(row, dict):
            continue
        row_user = str(row.get("user_id") or "").strip()
        if row_user and row_user != user_id:
            raise ValueError("ContradictionGate tenant mismatch")
        if str(row.get("access_class") or "public") not in {"public", "tenant_confidential"}:
            continue
        if bool(row.get("prompt_injection_detected")):
            continue
        evidence.append(row)
    if not supported or not evidence:
        return "unsupported", [], evidence
    verified = [row for row in evidence if str(row.get("verification_state") or "").casefold() in {"verified", "corroborated"}]
    if not verified:
        return "uncertain", supported, evidence
    if contradicted or any(str(row.get("relationship") or "") == "contradicts" for row in evidence):
        return "conflict", supported, evidence
    if any(str(row.get("relationship") or "") == "partially_establishes" for row in evidence):
        return "partially_contradicted", supported, evidence
    return "supported", supported, evidence


def _replacement(state: str, criterion: str) -> str:
    if state == "conflict":
        return f"Evidence conflict / unresolved for {criterion}: canonical evidence contains materially conflicting signals; no categorical conclusion is safe."
    if state == "uncertain":
        return f"Uncertain {criterion} judgment: canonical evidence is not sufficiently verified for a categorical conclusion; further verification is required."
    if state == "partially_contradicted":
        return f"Partially contradicted {criterion} judgment: canonical evidence weakens the categorical conclusion, but coverage is incomplete; preserve the uncertainty."
    return f"Evidence-consistent {criterion} interpretation: canonical evidence supports the opposite of this categorical judgment; retain the evidence and reassess the conclusion."


def apply_contradiction_gate(
    *, user_id: str, review: dict[str, Any], canonical_context: dict[str, Any] | None
) -> dict[str, Any]:
    """Return original review, guarded review, and inspectable correction records."""
    uid = require_user_id(user_id, context="ContradictionGate")
    original = dict(review)
    guarded = dict(review)
    contexts = canonical_context.get("contexts", {}) if isinstance(canonical_context, dict) else {}
    corrections: list[dict[str, Any]] = []
    inspected = 0
    criterion_states = {}
    for criterion in ("regulatory", "founder", "funding", "traction", "market", "product", "competition", "commercial", "business_model"):
        packet = contexts.get(criterion) if isinstance(contexts, dict) else None
        criterion_states[criterion] = (
            _packet_state(packet, user_id=uid)[0]
            if isinstance(packet, dict)
            else "not_applicable"
        )

    for field in _MATERIAL_FIELDS:
        value = review.get(field)
        values = value if isinstance(value, list) else [value]
        if not values:
            continue
        for index, item in enumerate(values):
            if not isinstance(item, str) or not item.strip():
                continue
            inspected += 1
            matched = None
            for candidate, patterns in DIRECT_NEGATIVE_PATTERNS.items():
                packet = contexts.get(candidate) if isinstance(contexts, dict) else None
                if not isinstance(packet, dict):
                    continue
                match = next((pattern.search(item) for pattern in patterns if pattern.search(item)), None)
                if match is not None:
                    matched = (candidate, packet)
                    break
            if matched is None:
                continue
            criterion, packet = matched
            state, claims, evidence = _packet_state(packet, user_id=uid)
            if state not in {"supported", "conflict", "uncertain", "partially_contradicted"}:
                continue
            correction_state = "directly_contradicted" if state == "supported" else state
            replacement = _replacement(state, criterion)
            if isinstance(value, list):
                updated = list(guarded.get(field) or [])
                updated[index] = replacement
                guarded[field] = updated
            else:
                guarded[field] = replacement
            corrections.append({
                "field": field,
                "index": index,
                "criterion": criterion,
                "state": correction_state,
                "original": item,
                "guarded": replacement,
                "claim_types": sorted(str(row.get("claim_type") or "") for row in claims),
                "evidence": [
                    {
                        "relationship": row.get("relationship"),
                        "source_locator": row.get("source_locator"),
                        "verification_state": row.get("verification_state"),
                        "access_class": row.get("access_class") or "public",
                        "display_excerpt": row.get("display_excerpt"),
                    }
                    for row in evidence
                ],
            })

    states = sorted({str(row["state"]) for row in corrections})
    return {
        "original_review": original,
        "guarded_review": guarded,
        "corrections": corrections,
        "material_fields_inspected": inspected,
        "correction_count": len(corrections),
        "state": "clear" if not corrections else ("conflict" if "conflict" in states else states[0]),
        "criterion_states": criterion_states,
        "llm_calls": 0,
    }
