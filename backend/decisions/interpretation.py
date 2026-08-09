"""Constrained, auditable interpretation of a human ruling rationale."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from utils.partner_codes import ruling_aligns_with_recommendation


_REFERENCE_PATTERN = re.compile(r"\b(?:claim|evidence)-[A-Za-z0-9_-]+\b")
_SENTENCE_PATTERN = re.compile(r"[^.!?;\n]+")
_POSITIVE_TERMS = ("strong", "support", "supports", "traction", "advantage", "compelling", "good")
_NEGATIVE_TERMS = (
    "risk", "weak", "concern", "limited", "unclear", "does not support", "lack",
    "not right", "not ready", "outside", "not a fit",
)
_DECISIVE_TERMS = ("decisive", "key", "primary", "main reason", "ultimately", "because")
_ACCEPTED_RISK_TERMS = ("accept", "accepted", "tolerate", "tolerated", "not decisive", "depriorit")


def _sentences(rationale: str) -> list[str]:
    return [item.strip() for item in _SENTENCE_PATTERN.findall(rationale) if item.strip()]


def _factor_items(sentences: Iterable[str], terms: tuple[str, ...]) -> list[Dict[str, Any]]:
    return [
        {"text": sentence, "source": "human_rationale", "attribution": "observed"}
        for sentence in sentences
        if any(term in sentence.lower() for term in terms)
    ]


def _claim_snapshot(context: Dict[str, Any]) -> list[Dict[str, Any]]:
    value = context.get("claim_snapshot") or []
    return value if isinstance(value, list) else []


def _evidence_influence(rationale: str, context: Dict[str, Any]) -> Dict[str, Any]:
    claims = _claim_snapshot(context)
    claim_by_id = {str(item.get("claim_id")): item for item in claims if item.get("claim_id")}
    evidence_ids = {
        str(reference_id)
        for claim in claims
        for key in ("supporting_evidence_ids", "contradicting_evidence_ids")
        for reference_id in (claim.get(key) or [])
    }
    references = []
    for reference_id in _REFERENCE_PATTERN.findall(rationale):
        if reference_id in claim_by_id:
            references.append(
                {
                    "reference_type": "claim",
                    "reference_id": reference_id,
                    "attribution": "explicit",
                    "basis": "claim identifier appeared in the human rationale",
                }
            )
        elif reference_id in evidence_ids:
            references.append(
                {
                    "reference_type": "evidence",
                    "reference_id": reference_id,
                    "attribution": "explicit",
                    "basis": "evidence identifier appeared in the human rationale",
                }
            )

    lowered = rationale.lower()
    if not references:
        for claim_id, claim in claim_by_id.items():
            display_text = str(claim.get("display_text") or "").strip().lower()
            if len(display_text) >= 12 and display_text in lowered:
                references.append(
                    {
                        "reference_type": "claim",
                        "reference_id": claim_id,
                        "attribution": "inferred",
                        "basis": "rationale phrase matched the decision-time claim text",
                    }
                )

    if references:
        status = "explicit" if all(item["attribution"] == "explicit" for item in references) else "inferred"
        return {"status": status, "references": references, "limitations": []}
    return {
        "status": "unknown",
        "references": [],
        "limitations": [
            "The rationale did not explicitly or reliably identify decision-time evidence."
        ],
    }


def build_ruling_interpretation_draft(
    *,
    rationale: str,
    decision: str,
    investor_confidence: float,
    risk_acknowledgement: Optional[str],
    mandate_exception: Optional[str],
    override_type: Optional[str],
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Derive only grounded dimensions; return None when interpretation is insufficient."""
    text = str(rationale or "").strip()
    if len(text) < 6:
        return None
    sentences = _sentences(text)
    positive = _factor_items(sentences, _POSITIVE_TERMS)
    negative = _factor_items(sentences, _NEGATIVE_TERMS)
    accepted_risks = _factor_items(sentences, _ACCEPTED_RISK_TERMS)
    if risk_acknowledgement:
        accepted_risks.append(
            {"text": str(risk_acknowledgement), "source": "human_risk_acknowledgement", "attribution": "observed"}
        )
    decisive = _factor_items(sentences, _DECISIVE_TERMS)
    evidence = _evidence_influence(text, context)
    strategic = None
    if mandate_exception or str(override_type or "") == "strategic_exception":
        strategic = {
            "text": str(mandate_exception or "Strategic exception indicated by the ruling override type."),
            "source": "human_mandate_exception" if mandate_exception else "human_override_type",
            "attribution": "observed",
        }
    recommendation = context.get("recommended_state")
    agreement = "unknown"
    if recommendation:
        agreement = "agree" if ruling_aligns_with_recommendation(recommendation, decision) else "disagree"
    if not any((positive, negative, accepted_risks, decisive, strategic, evidence["references"])):
        return None
    return {
        "status": "complete",
        "source": "aethria_inferred",
        "extraction_confidence": 0.75,
        "positive_factors": positive,
        "negative_factors": negative,
        "accepted_risks": accepted_risks,
        "decisive_factors": decisive,
        "overridden_criteria": [],
        "strategic_exception": strategic,
        "agreement_with_aethria": agreement,
        "human_confidence": float(investor_confidence),
        "evidence_influence": evidence,
        "provenance": {
            "extractor": "aethria-ruling-interpretation-rules-v1",
            "model": None,
            "prompt_version": None,
            "causality": "not_established",
        },
    }
