"""Snapshot, evidence-eligibility and safety helpers for current analysis."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence, Tuple

from evaluation_v2.models import (
    EvaluationPolicy,
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
                            # Add actual source material when available. Historical
                            # snapshots without these fields retain their exact
                            # serialized shape and digest for replay.
                            **{key: str(link[key]) if link[key] is not None else None
                               for key in ("artifact_id", "source_uri", "display_excerpt")
                               if key in link},
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
