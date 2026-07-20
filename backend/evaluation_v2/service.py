"""Pure deterministic evaluation over immutable claim snapshot values."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence, Tuple

from evaluation_v2.models import (
    CriterionResult,
    EvidenceEligibilityPolicy,
    EvaluationPolicy,
    EvaluationResult,
    RecommendationResult,
    RecommendationState,
    ScoreEligibility,
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
                "operator_attribution_at_snapshot": claim.get("operator_attribution"),
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
                            "verification_state": str(link.get("verification_state") or ""),
                            "source_quality": float(link.get("source_quality") or 0),
                            "trust_class": str(link.get("trust_class") or ""),
                            "untrusted_input": bool(link.get("untrusted_input")),
                            "prompt_injection_detected": bool(
                                link.get("prompt_injection_detected")
                            ),
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


def evaluate_claim_score_eligibility(
    claim: Dict[str, Any], *, policy: EvidenceEligibilityPolicy
) -> ScoreEligibility:
    reasons: List[str] = []
    assertion_class = claim.get("assertion_class_at_snapshot")
    if assertion_class not in policy.allowed_assertion_classes:
        reasons.append("assertion_class_not_allowed")

    candidate_links = list(claim.get("evidence_relationships", []))
    if (
        assertion_class == "operator_asserted"
        and "operator_asserted" in policy.allowed_assertion_classes
        and str(claim.get("operator_attribution_at_snapshot") or "").strip()
    ):
        candidate_links.append(
            {
                "relationship": policy.allowed_relationships[0],
                "support_strength": 1.0,
                "source_quality": 1.0,
                "trust_class": "operator",
                "prompt_injection_detected": False,
                "verification_state": "verified",
            }
        )

    allowed_links = [
        link
        for link in candidate_links
        if link.get("relationship") in policy.allowed_relationships
        and float(link.get("support_strength") or 0) >= policy.min_support_strength
        and float(link.get("source_quality") or 0) >= policy.min_source_quality
        and link.get("trust_class") not in policy.blocked_trust_classes
        and not bool(link.get("prompt_injection_detected"))
    ]
    if policy.require_verified_evidence:
        allowed_links = [
            link
            for link in allowed_links
            if link.get("verification_state") == "verified"
        ]
    if not allowed_links:
        reasons.append("no_eligible_supporting_evidence")
    return ScoreEligibility(eligible=not reasons, reason_codes=reasons)


def _score(claim: Dict[str, Any]) -> float | None:
    value = (claim.get("normalized_value") or {}).get("criterion_score")
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return None


def decisive_policy_outcome(
    snapshot: Sequence[Dict[str, Any]], policy: EvaluationPolicy
) -> tuple[RecommendationState | None, list[str], list[str]]:
    risks: list[str] = []
    conflicts: list[str] = []
    for claim in snapshot:
        if claim.get("status_at_snapshot") != "current":
            continue
        eligibility = evaluate_claim_score_eligibility(
            claim, policy=policy.decision_safety.evidence_eligibility
        )
        if not eligibility.eligible or not bool(
            (claim.get("normalized_value") or {}).get("value")
        ):
            continue
        claim_type = claim.get("claim_type")
        if claim_type in policy.decision_safety.hard_exclusion_claim_types:
            conflicts.append(str(claim_type))
        if claim_type in policy.decision_safety.critical_risk_claim_types:
            risks.append(str(claim.get("display_text") or claim_type))
    if conflicts or risks:
        return RecommendationState.PASS, risks, conflicts
    return None, risks, conflicts


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
    required_missing = []
    conflicts = []
    eligibility_policy = policy.decision_safety.evidence_eligibility
    for rule in policy.criteria:
        criterion_claims = [
            claim
            for claim in snapshot
            if claim["claim_type"] in rule.claim_types
            and claim["status_at_snapshot"] in {"current", "contradicted"}
        ]
        eligibility_results = [
            (
                claim,
                evaluate_claim_score_eligibility(claim, policy=eligibility_policy),
            )
            for claim in criterion_claims
        ]
        eligible = [
            claim for claim, eligibility in eligibility_results if eligibility.eligible
        ]
        eligibility_flags = sorted(
            {
                reason
                for _, eligibility in eligibility_results
                for reason in eligibility.reason_codes
            }
        )
        scored = [(claim, _score(claim)) for claim in eligible]
        scored = [(claim, score) for claim, score in scored if score is not None]
        contradicted = [
            claim["claim_id"]
            for claim in criterion_claims
            if claim["status_at_snapshot"] == "contradicted"
            or claim["contradicting_evidence_ids"]
        ]
        if not scored:
            missing.append(rule.criterion)
            if rule.required:
                required_missing.append(rule.criterion)
            criteria.append(
                CriterionResult(
                    criterion=rule.criterion,
                    score=None,
                    evidence_sufficiency="insufficient",
                    reasoning="No eligible scored claim was present in the immutable snapshot.",
                    missing_evidence=[rule.criterion],
                    contradicting_claim_ids=contradicted,
                    quality_flags=eligibility_flags,
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
                quality_flags=sorted(
                    set(eligibility_flags)
                    | ({"contradiction_present"} if contradicted else set())
                ),
            )
        )

    decisive_state, decisive_risks, mandate_conflicts = decisive_policy_outcome(
        snapshot, policy
    )
    decisive_claim_types = set(policy.decision_safety.critical_risk_claim_types) | set(
        policy.decision_safety.hard_exclusion_claim_types
    )
    decisive_uncertainties = [
        str(claim.get("display_text") or claim.get("claim_type"))
        for claim in snapshot
        if claim.get("claim_type") in decisive_claim_types
        and claim["status_at_snapshot"] == "current"
        and bool((claim.get("normalized_value") or {}).get("value"))
        and not evaluate_claim_score_eligibility(
            claim, policy=eligibility_policy
        ).eligible
    ]
    missing = list(dict.fromkeys(missing + decisive_uncertainties))
    coverage = scored_weight / total_weight if total_weight else 0
    average = weighted_total / scored_weight if scored_weight else 0
    if decisive_state is not None:
        state = decisive_state
    elif required_missing or coverage < policy.minimum_scored_weight:
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
        principal_risks=list(dict.fromkeys(conflicts + decisive_risks)),
        mandate_conflicts=sorted(set(mandate_conflicts)),
        missing_information=missing,
        change_conditions=[f"Resolve missing evidence: {name}" for name in missing],
        human_review_required=bool(
            decisive_state
            or conflicts
            or missing
            or state is RecommendationState.INSUFFICIENT_EVIDENCE
        ),
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
