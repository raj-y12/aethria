"""Bind published tenant scoring policy to the immutable evidence evaluator."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable

from evaluation_v2.models import CriterionRule, EvaluationPolicy
from evaluation_v2.partner_rules import (
    PartnerRules,
    boundary_comparisons,
    decision_safety_policy,
    parse_partner_rules,
    partner_rules_document,
)


def _document_hash(document: Any) -> str:
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _strings(values: Iterable[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _partner_rules_error(detail: str) -> ValueError:
    return ValueError(f"partner_rules is incomplete or invalid: {detail}")


def validate_partner_rules_document(
    partner_rules: PartnerRules | Dict[str, Any],
) -> PartnerRules:
    """Validate every active field and reject unknown policy keys."""
    try:
        return parse_partner_rules(partner_rules)
    except ValueError as exc:
        raise _partner_rules_error(str(exc)) from exc


def evaluation_policy_from_compiled(
    compiled_policy: Dict[str, Any],
    *,
    partner_rules: PartnerRules | Dict[str, Any],
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

    typed_rules = validate_partner_rules_document(partner_rules)
    thresholds = typed_rules.score_thresholds
    decision_safety = decision_safety_policy(typed_rules)
    advance_threshold = float(thresholds.min_avg_strong_yes)
    pass_threshold = float(thresholds.min_avg_pass)
    advance_comparison, pass_comparison = boundary_comparisons(typed_rules)

    return EvaluationPolicy(
        policy_version_id=version_id,
        policy_hash=policy_hash,
        rubric_version=f"tenant-rubric:{version_id}",
        partner_rules_version=typed_rules.version,
        partner_rules_hash=_document_hash(partner_rules_document(typed_rules)),
        criteria=criteria,
        advance_threshold=advance_threshold,
        pass_threshold=pass_threshold,
        advance_comparison=advance_comparison,
        pass_comparison=pass_comparison,
        minimum_scored_weight=float(thresholds.minimum_scored_weight),
        decision_safety=decision_safety,
        hard_exclusion_claim_types=decision_safety.hard_exclusion_claim_types,
    )
