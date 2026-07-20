"""Bind published tenant scoring policy to the immutable evidence evaluator."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable

from evaluation_v2.models import CriterionRule, DecisionSafetyPolicy, EvaluationPolicy


def _document_hash(document: Any) -> str:
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _strings(values: Iterable[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def evaluation_policy_from_compiled(
    compiled_policy: Dict[str, Any], *, partner_rules: Dict[str, Any]
) -> EvaluationPolicy:
    """Create a deterministic evidence policy from the exact published version."""
    version_id = str(compiled_policy.get("policy_version_id") or "").strip()
    policy_hash = str(compiled_policy.get("policy_hash") or "").strip()
    dimensions = compiled_policy.get("dimensions")
    if not version_id or not policy_hash or not isinstance(dimensions, dict):
        raise ValueError("Published policy is missing version, hash, or dimensions")

    weighted_dimensions = []
    for dimension, raw in dimensions.items():
        if not isinstance(raw, dict):
            continue
        try:
            weight = float(raw.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        if weight <= 0:
            continue
        weighted_dimensions.append((str(dimension), raw, weight))
    total_weight = sum(weight for _, _, weight in weighted_dimensions)
    if total_weight <= 0:
        raise ValueError("Published policy has no weighted evaluation dimensions")

    criteria = []
    for dimension, raw, weight in weighted_dimensions:
        raw_criteria = raw.get("criteria") if isinstance(raw.get("criteria"), list) else []
        claim_types: list[Any] = [dimension]
        for criterion in raw_criteria:
            if not isinstance(criterion, dict):
                continue
            claim_types.append(criterion.get("id"))
            claim_types.extend(criterion.get("source_components") or [])
        criteria.append(
            CriterionRule(
                criterion=dimension,
                claim_types=_strings(claim_types),
                weight=weight / total_weight,
            )
        )

    thresholds = (
        partner_rules.get("score_thresholds")
        if isinstance(partner_rules.get("score_thresholds"), dict)
        else {}
    )
    advance_threshold = float(thresholds.get("min_avg_strong_yes", 7.5))
    pass_threshold = float(thresholds.get("min_avg_pass", 4.0))
    rules_version = str(partner_rules.get("version") or "unknown").strip() or "unknown"
    try:
        decision_safety = DecisionSafetyPolicy.model_validate(
            partner_rules.get("decision_safety")
        )
    except ValueError as exc:
        raise ValueError(
            "partner_rules.decision_safety is required and must be valid"
        ) from exc

    return EvaluationPolicy(
        policy_version_id=version_id,
        policy_hash=policy_hash,
        rubric_version=f"tenant-rubric:{version_id}",
        partner_rules_version=rules_version,
        partner_rules_hash=_document_hash(partner_rules),
        criteria=criteria,
        advance_threshold=advance_threshold,
        pass_threshold=pass_threshold,
        decision_safety=decision_safety,
        hard_exclusion_claim_types=decision_safety.hard_exclusion_claim_types,
    )
