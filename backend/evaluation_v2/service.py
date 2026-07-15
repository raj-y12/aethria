"""Pure deterministic evaluation over immutable claim snapshot values."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence, Tuple

from evaluation_v2.models import (
    CriterionResult,
    EvaluationPolicy,
    EvaluationResult,
    RecommendationResult,
    RecommendationState,
)


def snapshot_claims(
    claims: Sequence[Dict[str, Any]], links: Sequence[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], str]:
    by_claim: Dict[str, List[Dict[str, Any]]] = {}
    for link in links:
        by_claim.setdefault(str(link.get("claim_id")), []).append(link)
    snapshot = []
    for claim in claims:
        claim_id = str(claim.get("claim_id"))
        claim_links = by_claim.get(claim_id, [])
        snapshot.append(
            {
                "claim_id": claim_id,
                "claim_type": str(claim.get("claim_type") or ""),
                "normalized_value": claim.get("normalized_value") or {},
                "unit": claim.get("unit"),
                "period": claim.get("period"),
                "display_text": str(claim.get("display_text") or ""),
                "status_at_snapshot": str(claim.get("status") or ""),
                "assertion_class_at_snapshot": str(claim.get("assertion_class") or ""),
                "confidence_at_snapshot": float(claim.get("confidence") or 0),
                "supporting_evidence_ids": sorted(
                    str(link.get("evidence_item_id"))
                    for link in claim_links
                    if link.get("relationship") in {"supports", "partially_establishes"}
                ),
                "contradicting_evidence_ids": sorted(
                    str(link.get("evidence_item_id"))
                    for link in claim_links
                    if link.get("relationship") == "contradicts"
                ),
                "evidence_relationships": sorted(
                    [
                        {
                            "evidence_item_id": str(link.get("evidence_item_id")),
                            "relationship": str(link.get("relationship")),
                            "support_strength": float(link.get("support_strength") or 0),
                        }
                        for link in claim_links
                    ],
                    key=lambda item: (item["evidence_item_id"], item["relationship"]),
                ),
            }
        )
    snapshot.sort(key=lambda item: item["claim_id"])
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return snapshot, hashlib.sha256(canonical.encode()).hexdigest()


def _score(claim: Dict[str, Any]) -> float | None:
    value = (claim.get("normalized_value") or {}).get("criterion_score")
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return None


def evaluate_snapshot(
    snapshot: Sequence[Dict[str, Any]], policy: EvaluationPolicy
) -> EvaluationResult:
    canonical = json.dumps(list(snapshot), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    criteria: List[CriterionResult] = []
    scored_weight = 0.0
    weighted_total = 0.0
    total_weight = sum(rule.weight for rule in policy.criteria)
    missing = []
    conflicts = []
    for rule in policy.criteria:
        eligible = [
            claim
            for claim in snapshot
            if claim["claim_type"] in rule.claim_types
            and claim["status_at_snapshot"] in {"current", "contradicted"}
        ]
        scored = [(claim, _score(claim)) for claim in eligible]
        scored = [(claim, score) for claim, score in scored if score is not None]
        contradicted = [
            claim["claim_id"]
            for claim in eligible
            if claim["status_at_snapshot"] == "contradicted"
            or claim["contradicting_evidence_ids"]
        ]
        if not scored:
            missing.append(rule.criterion)
            criteria.append(
                CriterionResult(
                    criterion=rule.criterion,
                    score=None,
                    evidence_sufficiency="insufficient",
                    reasoning="No eligible scored claim was present in the immutable snapshot.",
                    missing_evidence=[rule.criterion],
                    contradicting_claim_ids=contradicted,
                )
            )
            continue
        weight_sum = sum(max(0.01, claim["confidence_at_snapshot"]) for claim, _ in scored)
        score = sum(
            value * max(0.01, claim["confidence_at_snapshot"])
            for claim, value in scored
        ) / weight_sum
        confidence = min(
            1.0,
            sum(claim["confidence_at_snapshot"] for claim, _ in scored) / len(scored),
        )
        if contradicted:
            confidence *= 0.6
            conflicts.append(rule.criterion)
        scored_weight += rule.weight
        weighted_total += score * rule.weight
        criteria.append(
            CriterionResult(
                criterion=rule.criterion,
                score=round(score, 4),
                confidence=round(confidence, 4),
                evidence_sufficiency="partial" if contradicted else "sufficient",
                reasoning="Deterministic confidence-weighted claim score.",
                supporting_claim_ids=[claim["claim_id"] for claim, _ in scored],
                contradicting_claim_ids=contradicted,
                quality_flags=["contradiction_present"] if contradicted else [],
            )
        )

    exclusion_claims = [
        claim
        for claim in snapshot
        if claim["claim_type"] in policy.hard_exclusion_claim_types
        and claim["status_at_snapshot"] == "current"
        and bool((claim.get("normalized_value") or {}).get("value"))
    ]
    coverage = scored_weight / total_weight if total_weight else 0
    average = weighted_total / scored_weight if scored_weight else 0
    if exclusion_claims:
        state = RecommendationState.PASS
    elif coverage < policy.minimum_scored_weight:
        state = RecommendationState.INSUFFICIENT_EVIDENCE
    elif average >= policy.advance_threshold:
        state = RecommendationState.ADVANCE
    elif average <= policy.pass_threshold:
        state = RecommendationState.PASS
    else:
        state = RecommendationState.MONITOR
    confidence_values = [item.confidence for item in criteria if item.score is not None]
    confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0
    confidence *= coverage
    recommendation = RecommendationResult(
        state=state,
        attention_priority=max(0, min(100, round(average * 10 * coverage))),
        confidence=round(confidence, 4),
        decision_drivers=[
            item.criterion for item in sorted(
                [item for item in criteria if item.score is not None],
                key=lambda item: item.score or 0,
                reverse=True,
            )[:3]
        ],
        principal_risks=conflicts,
        mandate_conflicts=sorted({claim["claim_type"] for claim in exclusion_claims}),
        missing_information=missing,
        change_conditions=[f"Resolve missing evidence: {name}" for name in missing],
        human_review_required=bool(exclusion_claims or conflicts or missing or state is RecommendationState.INSUFFICIENT_EVIDENCE),
    )
    return EvaluationResult(snapshot_hash=digest, criteria=criteria, recommendation=recommendation)


def explain_recommendation_change(
    previous: Dict[str, Any] | None, current: RecommendationResult
) -> str | None:
    if not previous:
        return None
    before = str(previous.get("recommended_state") or previous.get("state") or "")
    if before == current.state.value:
        return "Recommendation state is unchanged; evidence confidence or drivers were refreshed."
    return (
        f"Recommendation changed from {before or 'unknown'} to {current.state.value} "
        "because the immutable evidence snapshot or policy inputs changed."
    )
