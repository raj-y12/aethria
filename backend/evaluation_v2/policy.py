"""Bind published tenant scoring policy to the immutable evidence evaluator."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Iterable

from evaluation_v2.models import CriterionRule, DecisionSafetyPolicy, EvaluationPolicy


_CANONICAL_THRESHOLD_KEYS = (
    "min_avg_pass",
    "min_avg_strong_yes",
    "min_avg_medium_maybe",
    "min_avg_borderline_low",
    "max_avg_borderline_high",
    "grey_zone_min",
    "grey_zone_max",
    "minimum_scored_weight",
)
_DETECTION_LIST_KEYS = (
    "critical_risk_keywords",
    "red_flag_keywords",
    "missing_qualitative_keywords",
    "assumption_risk_keywords",
)
_ACTION_KEYS = (
    "critical_risks",
    "low_scores",
    "default_no",
    "request_cap_table",
    "request_cap_table_and_review",
    "monitor",
    "human_review_monitor",
    "human_review_contradictions",
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


def _require_nonempty_strings(document: Dict[str, Any], key: str) -> list[str]:
    value = document.get(key)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise _partner_rules_error(f"{key} must be a non-empty string list")
    return [item.strip() for item in value]


def validate_partner_rules_document(
    partner_rules: Dict[str, Any],
) -> tuple[Dict[str, Any], DecisionSafetyPolicy]:
    """Validate the complete versioned authority contract without fallbacks."""
    if not isinstance(partner_rules, dict):
        raise _partner_rules_error("document must be an object")
    version = partner_rules.get("version")
    if not isinstance(version, str) or not version.strip():
        raise _partner_rules_error("version must be a non-empty string")

    thresholds = partner_rules.get("score_thresholds")
    if not isinstance(thresholds, dict):
        raise _partner_rules_error("score_thresholds must be an object")
    numeric_thresholds: dict[str, float] = {}
    for key in _CANONICAL_THRESHOLD_KEYS:
        if key not in thresholds or isinstance(thresholds[key], bool):
            raise _partner_rules_error(f"score_thresholds.{key} is required")
        try:
            numeric_thresholds[key] = float(thresholds[key])
        except (TypeError, ValueError) as exc:
            raise _partner_rules_error(
                f"score_thresholds.{key} must be numeric"
            ) from exc
        if not math.isfinite(numeric_thresholds[key]):
            raise _partner_rules_error(
                f"score_thresholds.{key} must be finite"
            )
        if key == "minimum_scored_weight":
            if not 0 < numeric_thresholds[key] <= 1:
                raise _partner_rules_error(
                    "score_thresholds.minimum_scored_weight must be in (0, 1]"
                )
        elif not 0 <= numeric_thresholds[key] <= 10:
            raise _partner_rules_error(
                f"score_thresholds.{key} must be between 0 and 10"
            )
    pass_threshold = numeric_thresholds["min_avg_pass"]
    advance_threshold = numeric_thresholds["min_avg_strong_yes"]
    medium_threshold = numeric_thresholds["min_avg_medium_maybe"]
    borderline_low = numeric_thresholds["min_avg_borderline_low"]
    borderline_high = numeric_thresholds["max_avg_borderline_high"]
    grey_min = numeric_thresholds["grey_zone_min"]
    grey_max = numeric_thresholds["grey_zone_max"]
    if not pass_threshold < advance_threshold:
        raise _partner_rules_error(
            "min_avg_pass must be below min_avg_strong_yes"
        )
    if not pass_threshold <= medium_threshold <= advance_threshold:
        raise _partner_rules_error(
            "min_avg_medium_maybe must be between pass and advance thresholds"
        )
    if not pass_threshold <= borderline_low < borderline_high <= advance_threshold:
        raise _partner_rules_error(
            "borderline thresholds must be ordered within pass and advance"
        )
    if not pass_threshold <= grey_min <= grey_max <= advance_threshold:
        raise _partner_rules_error(
            "grey-zone thresholds must be ordered within pass and advance"
        )
    boundaries = thresholds.get("boundary_semantics")
    if not isinstance(boundaries, dict):
        raise _partner_rules_error(
            "score_thresholds.boundary_semantics must be an object"
        )
    if boundaries.get("advance") != "greater_than_or_equal":
        raise _partner_rules_error(
            "score_thresholds.boundary_semantics.advance must be greater_than_or_equal"
        )
    if boundaries.get("pass") != "less_than":
        raise _partner_rules_error(
            "score_thresholds.boundary_semantics.pass must be less_than"
        )

    for key in _DETECTION_LIST_KEYS:
        _require_nonempty_strings(partner_rules, key)
    actions = partner_rules.get("next_actions")
    if not isinstance(actions, dict):
        raise _partner_rules_error("next_actions must be an object")
    for key in _ACTION_KEYS:
        action = actions.get(key)
        if not isinstance(action, str) or not action.strip():
            raise _partner_rules_error(f"next_actions.{key} is required")

    for key in (
        "quality_labels",
        "verdict_rules",
        "contradictory_scores",
        "llm_fallback_triggers",
    ):
        if not isinstance(partner_rules.get(key), dict) or not partner_rules[key]:
            raise _partner_rules_error(f"{key} must be a non-empty object")

    try:
        decision_safety = DecisionSafetyPolicy.model_validate(
            partner_rules.get("decision_safety")
        )
    except ValueError as exc:
        raise _partner_rules_error(
            "decision_safety is required and must include eligibility, confidence, "
            "freshness, source quality, and decisive claim types"
        ) from exc
    advance_threshold = numeric_thresholds["min_avg_strong_yes"]
    score_caps = (
        decision_safety.claim_confidence.score_cap_below_full_confidence,
        decision_safety.freshness.stale_score_cap,
        decision_safety.source_quality.score_cap_below_full_quality,
    )
    if any(cap >= advance_threshold for cap in score_caps):
        raise _partner_rules_error(
            "every weak-evidence score cap must be below min_avg_strong_yes"
        )
    if (
        decision_safety.source_quality.full_confidence_at
        < decision_safety.evidence_eligibility.min_source_quality
    ):
        raise _partner_rules_error(
            "source_quality.full_confidence_at must be at least min_source_quality"
        )
    return thresholds, decision_safety


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

    thresholds, decision_safety = validate_partner_rules_document(partner_rules)
    advance_threshold = float(thresholds["min_avg_strong_yes"])
    pass_threshold = float(thresholds["min_avg_pass"])
    rules_version = str(partner_rules["version"]).strip()
    boundary_semantics = thresholds["boundary_semantics"]

    return EvaluationPolicy(
        policy_version_id=version_id,
        policy_hash=policy_hash,
        rubric_version=f"tenant-rubric:{version_id}",
        partner_rules_version=rules_version,
        partner_rules_hash=_document_hash(partner_rules),
        criteria=criteria,
        advance_threshold=advance_threshold,
        pass_threshold=pass_threshold,
        advance_comparison=boundary_semantics["advance"],
        pass_comparison=boundary_semantics["pass"],
        minimum_scored_weight=float(thresholds["minimum_scored_weight"]),
        decision_safety=decision_safety,
        hard_exclusion_claim_types=decision_safety.hard_exclusion_claim_types,
    )
