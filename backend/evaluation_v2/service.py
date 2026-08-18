"""Pure deterministic evaluation over immutable claim snapshot values."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
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


def _canonical_digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def materiality_digest(snapshot: Sequence[Dict[str, Any]]) -> str:
    """Hash enriched immutable content while excluding only the evaluation clock."""
    material_projection = [
        {
            key: value
            for key, value in claim.items()
            if key != "evaluation_at_snapshot"
        }
        for claim in snapshot
    ]
    material_projection.sort(key=lambda item: str(item.get("claim_id") or ""))
    return _canonical_digest(material_projection)


def snapshot_claims(
    claims: Sequence[Dict[str, Any]],
    links: Sequence[Dict[str, Any]],
    *,
    evaluation_at: datetime | None = None,
) -> Tuple[List[Dict[str, Any]], str]:
    evaluation_clock = _utc(evaluation_at or datetime.now(timezone.utc))
    evaluation_clock_iso = evaluation_clock.isoformat()
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
                "normalized_value": (
                    {}
                    if claim.get("normalized_value") is None
                    else claim.get("normalized_value")
                ),
                "unit": claim.get("unit"),
                "period": claim.get("period"),
                "display_text": str(claim.get("display_text") or ""),
                "status_at_snapshot": str(claim.get("status") or ""),
                "assertion_class_at_snapshot": str(claim.get("assertion_class") or ""),
                "operator_attribution_at_snapshot": claim.get("operator_attribution"),
                "confidence_at_snapshot": float(claim.get("confidence") or 0),
                "evaluation_at_snapshot": evaluation_clock_iso,
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
                            "evidence_effective_at": _iso_or_none(
                                link.get("evidence_effective_at")
                            ),
                            "evidence_expires_at": _iso_or_none(
                                link.get("evidence_expires_at")
                            ),
                            "artifact_effective_at": _iso_or_none(
                                link.get("artifact_effective_at")
                            ),
                            "retrieved_at": _iso_or_none(link.get("retrieved_at")),
                        }
                        for link in claim_links
                    ],
                    key=lambda item: (item["evidence_item_id"], item["relationship"]),
                ),
            }
        )
    snapshot.sort(key=lambda item: item["claim_id"])
    return snapshot, _canonical_digest(snapshot)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("evaluation timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _utc(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return _utc(parsed)
    except (TypeError, ValueError):
        return None


def _iso_or_none(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def _snapshot_clock(
    snapshot: Sequence[Dict[str, Any]], evaluation_at: datetime | None
) -> datetime:
    embedded = {
        str(claim.get("evaluation_at_snapshot") or "").strip()
        for claim in snapshot
        if claim.get("evaluation_at_snapshot")
    }
    if len(embedded) > 1:
        raise ValueError("immutable snapshot contains multiple evaluation timestamps")
    embedded_clock = _parse_timestamp(next(iter(embedded))) if embedded else None
    requested_clock = _utc(evaluation_at) if evaluation_at is not None else None
    if embedded_clock and requested_clock and embedded_clock != requested_clock:
        raise ValueError("evaluation timestamp does not match immutable snapshot")
    return embedded_clock or requested_clock or _utc(datetime.now(timezone.utc))


def evaluate_claim_score_eligibility(
    claim: Dict[str, Any],
    *,
    policy: EvaluationPolicy,
    evaluation_at: datetime,
) -> ScoreEligibility:
    blocking_reasons: List[str] = []
    quality_flags: List[str] = []
    evidence_policy = policy.decision_safety.evidence_eligibility
    confidence_policy = policy.decision_safety.claim_confidence
    freshness_policy = policy.decision_safety.freshness
    quality_policy = policy.decision_safety.source_quality
    claim_confidence = float(claim.get("confidence_at_snapshot") or 0)
    score_cap = 10.0
    confidence_cap = 1.0
    if claim_confidence == 0 and confidence_policy.zero_confidence_ineligible:
        blocking_reasons.append("claim_confidence_zero")
    elif claim_confidence < confidence_policy.minimum_eligible:
        blocking_reasons.append("claim_confidence_below_minimum")
    elif claim_confidence < confidence_policy.full_confidence_at:
        quality_flags.append("claim_confidence_below_full")
        score_cap = min(score_cap, confidence_policy.score_cap_below_full_confidence)
        confidence_cap = min(
            confidence_cap,
            confidence_policy.recommendation_confidence_cap_below_full_confidence,
        )

    assertion_class = claim.get("assertion_class_at_snapshot")
    if assertion_class not in evidence_policy.allowed_assertion_classes:
        blocking_reasons.append("assertion_class_not_allowed")

    candidate_links = list(claim.get("evidence_relationships", []))
    if (
        assertion_class == "operator_asserted"
        and "operator_asserted" in evidence_policy.allowed_assertion_classes
        and str(claim.get("operator_attribution_at_snapshot") or "").strip()
    ):
        candidate_links.append(
            {
                "relationship": evidence_policy.allowed_relationships[0],
                "support_strength": 1.0,
                "source_quality": 1.0,
                "trust_class": "operator",
                "prompt_injection_detected": False,
                "verification_state": "verified",
                "operator_grounded": True,
            }
        )

    allowed_links = []
    rejected_link_reasons: List[str] = []
    link_caps: list[tuple[float, float, list[str]]] = []
    for link in candidate_links:
        if link.get("relationship") not in evidence_policy.allowed_relationships:
            continue
        if float(link.get("support_strength") or 0) < evidence_policy.min_support_strength:
            continue
        source_quality = float(link.get("source_quality") or 0)
        if source_quality < evidence_policy.min_source_quality:
            continue
        if link.get("trust_class") in evidence_policy.blocked_trust_classes:
            continue
        if bool(link.get("prompt_injection_detected")):
            continue
        if (
            evidence_policy.require_verified_evidence
            and link.get("verification_state") != "verified"
        ):
            continue

        current_score_cap = 10.0
        current_confidence_cap = 1.0
        current_flags: list[str] = []
        if not link.get("operator_grounded"):
            expires_at = _parse_timestamp(link.get("evidence_expires_at"))
            effective_at = (
                _parse_timestamp(link.get("evidence_effective_at"))
                or _parse_timestamp(link.get("artifact_effective_at"))
                or _parse_timestamp(link.get("retrieved_at"))
            )
            if expires_at is not None and expires_at <= evaluation_at:
                rejected_link_reasons.append("evidence_expired")
                continue
            if effective_at is None:
                rejected_link_reasons.append("evidence_undated")
                continue
            if effective_at > evaluation_at:
                rejected_link_reasons.append("evidence_future_dated")
                continue
            if evaluation_at - effective_at > timedelta(days=freshness_policy.max_age_days):
                current_flags.append("evidence_stale")
                current_score_cap = min(
                    current_score_cap, freshness_policy.stale_score_cap
                )
                current_confidence_cap = min(
                    current_confidence_cap, freshness_policy.stale_confidence_cap
                )
        if source_quality < quality_policy.full_confidence_at:
            current_flags.append("source_quality_below_full")
            current_score_cap = min(
                current_score_cap, quality_policy.score_cap_below_full_quality
            )
            current_confidence_cap = min(
                current_confidence_cap,
                quality_policy.recommendation_confidence_cap_below_full_quality,
            )
        allowed_links.append(link)
        link_caps.append((current_score_cap, current_confidence_cap, current_flags))

    if not allowed_links:
        blocking_reasons.extend(rejected_link_reasons)
        blocking_reasons.append("no_eligible_supporting_evidence")
    else:
        # Any independently eligible full-quality link can establish the claim.
        best_score_cap, best_confidence_cap, best_flags = max(
            link_caps, key=lambda item: (item[0], item[1])
        )
        score_cap = min(score_cap, best_score_cap)
        confidence_cap = min(confidence_cap, best_confidence_cap)
        quality_flags.extend(best_flags)
    return ScoreEligibility(
        eligible=not blocking_reasons,
        reason_codes=sorted(set(blocking_reasons + quality_flags)),
        score_cap=score_cap,
        confidence_cap=confidence_cap,
    )


def _score(claim: Dict[str, Any]) -> float | None:
    value = (claim.get("normalized_value") or {}).get("criterion_score")
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return None


def _claim_score_note(claim: Dict[str, Any], value: float) -> str:
    """One claim's contribution: evidence, confidence, and -- when extraction
    supplied it -- which rubric band it met and why the score isn't higher/lower.

    A claim's normalized_value carries score_band/score_justification only when
    extracted by evidence/extraction.py's current prompt; older claims degrade to
    the evidence text alone rather than a missing-field error.
    """
    text = str(claim.get("display_text") or claim.get("claim_type") or "").strip()
    confidence = claim["confidence_at_snapshot"]
    normalized = claim.get("normalized_value") or {}
    justification = str(normalized.get("score_justification") or "").strip()
    band = str(normalized.get("score_band") or "").strip()
    note = f'"{text}" (scored {value:.1f}, {confidence:.0%} confidence'
    if band:
        note += f", {band} band"
    note += ")"
    if justification:
        note += f" — {justification}"
    return note


def _criterion_reasoning(scored: list[tuple[Dict[str, Any], float, ScoreEligibility]]) -> str:
    """Deterministic, claim-specific audit trail for a criterion's score.

    Replaces a static placeholder that gave no way to trace an 8 vs a 2 back to
    the evidence behind it -- every scored criterion cited the identical string
    regardless of company or claim.
    """
    if len(scored) == 1:
        claim, value, _ = scored[0]
        return f"Scored from one claim: {_claim_score_note(claim, value)}"
    notes = [_claim_score_note(claim, value) for claim, value, _ in scored]
    return f"Confidence-weighted average of {len(scored)} claims: " + "; ".join(notes)


def decisive_policy_outcome(
    snapshot: Sequence[Dict[str, Any]],
    policy: EvaluationPolicy,
    *,
    evaluation_at: datetime,
) -> tuple[
    RecommendationState | None,
    list[str],
    list[str],
    list[str],
    list[str],
]:
    risks: list[str] = []
    conflicts: list[str] = []
    uncertainties: list[str] = []
    contradictions: list[str] = []
    for claim in snapshot:
        if claim.get("status_at_snapshot") not in {"current", "contradicted"}:
            continue
        eligibility = evaluate_claim_score_eligibility(
            claim, policy=policy, evaluation_at=evaluation_at
        )
        raw_value = (claim.get("normalized_value") or {}).get("value")
        claim_type = claim.get("claim_type")
        if claim_type not in (
            set(policy.decision_safety.hard_exclusion_claim_types)
            | set(policy.decision_safety.critical_risk_claim_types)
        ):
            continue
        if (
            claim.get("status_at_snapshot") == "contradicted"
            or claim.get("contradicting_evidence_ids")
        ):
            contradictions.append(str(claim.get("display_text") or claim_type))
            continue
        if type(raw_value) is not bool:
            uncertainties.append(str(claim.get("display_text") or claim_type))
            continue
        if raw_value is False:
            continue
        if not eligibility.eligible:
            uncertainties.append(str(claim.get("display_text") or claim_type))
            continue
        if claim_type in policy.decision_safety.hard_exclusion_claim_types:
            conflicts.append(str(claim_type))
        if claim_type in policy.decision_safety.critical_risk_claim_types:
            risks.append(str(claim.get("display_text") or claim_type))
    if conflicts or risks:
        return RecommendationState.PASS, risks, conflicts, uncertainties, contradictions
    return None, risks, conflicts, uncertainties, contradictions


def evaluate_snapshot(
    snapshot: Sequence[Dict[str, Any]],
    policy: EvaluationPolicy,
    *,
    evaluation_at: datetime | None = None,
) -> EvaluationResult:
    evaluation_clock = _snapshot_clock(snapshot, evaluation_at)
    canonical = json.dumps(list(snapshot), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    criteria: List[CriterionResult] = []
    scored_weight = 0.0
    weighted_total = 0.0
    total_weight = sum(rule.weight for rule in policy.criteria)
    missing = []
    required_missing = []
    conflicts = []
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
                evaluate_claim_score_eligibility(
                    claim, policy=policy, evaluation_at=evaluation_clock
                ),
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
        scored = [
            (claim, _score(claim), eligibility)
            for claim, eligibility in eligibility_results
            if eligibility.eligible
        ]
        scored = [
            (claim, min(score, eligibility.score_cap), eligibility)
            for claim, score, eligibility in scored
            if score is not None
        ]
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
        # M5: confidence_at_snapshot is the model's own self-reported number --
        # weighting the criterion average by it alone let one overconfident
        # claim dominate even when its evidence was weak/stale (eligibility.
        # confidence_cap, a deterministic signal independent of the model,
        # already caps the *composed* confidence below but wasn't applied to
        # *weighting*). Same fix shape as C4: cross-check the self-reported
        # number against the independent cap before trusting it.
        weight_sum = sum(
            min(claim["confidence_at_snapshot"], eligibility.confidence_cap)
            for claim, _, eligibility in scored
        )
        if weight_sum == 0:
            # confidence_cap is a policy-configured value (0 <= cap < 1) --
            # unlike confidence_at_snapshot, nothing prevents a future
            # partner_rules version from setting one to exactly 0, which
            # would zero every scored claim's weight here. Fail closed the
            # same way "no eligible scored claim" above does, rather than
            # letting the division below raise and crash the evaluation.
            missing.append(rule.criterion)
            if rule.required:
                required_missing.append(rule.criterion)
            criteria.append(
                CriterionResult(
                    criterion=rule.criterion,
                    score=None,
                    evidence_sufficiency="insufficient",
                    reasoning="Every eligible claim's confidence was capped to zero by policy.",
                    missing_evidence=[rule.criterion],
                    contradicting_claim_ids=contradicted,
                    quality_flags=sorted(set(eligibility_flags) | {"confidence_cap_zero"}),
                )
            )
            continue
        score = sum(
            value * min(claim["confidence_at_snapshot"], eligibility.confidence_cap)
            for claim, value, eligibility in scored
        ) / weight_sum
        confidence = min(
            1.0,
            sum(claim["confidence_at_snapshot"] for claim, _, _ in scored)
            / len(scored),
            min(eligibility.confidence_cap for _, _, eligibility in scored),
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
                reasoning=_criterion_reasoning(scored),
                supporting_claim_ids=[claim["claim_id"] for claim, _, _ in scored],
                contradicting_claim_ids=contradicted,
                quality_flags=sorted(
                    set(eligibility_flags)
                    | ({"contradiction_present"} if contradicted else set())
                ),
            )
        )

    (
        decisive_state,
        decisive_risks,
        mandate_conflicts,
        decisive_uncertainties,
        decisive_contradictions,
    ) = decisive_policy_outcome(snapshot, policy, evaluation_at=evaluation_clock)
    missing = list(dict.fromkeys(missing + decisive_uncertainties))
    coverage = scored_weight / total_weight if total_weight else 0
    average = weighted_total / scored_weight if scored_weight else 0
    if (
        required_missing
        or conflicts
        or decisive_uncertainties
        or decisive_contradictions
        or coverage < policy.minimum_scored_weight
    ):
        state = RecommendationState.INSUFFICIENT_EVIDENCE
    elif decisive_state is not None:
        state = decisive_state
    elif average >= policy.advance_threshold:
        state = RecommendationState.ADVANCE
    elif average < policy.pass_threshold:
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
        change_conditions=(
            [f"Resolve missing evidence: {name}" for name in missing]
            + [
                f"Resolve contradictory evidence: {name}"
                for name in dict.fromkeys(conflicts + decisive_contradictions)
            ]
        ),
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
