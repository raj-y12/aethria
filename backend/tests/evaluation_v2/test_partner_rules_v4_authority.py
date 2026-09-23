"""Historical Partner policy parsing and immutable identity contracts."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evaluation_v2.partner_rules import (
    PartnerRules,
    parse_partner_rules,
    partner_rules_document,
)
from evaluation_v2.policy import evaluation_policy_from_compiled


_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "resources" / "config"
_V3_PATH = _CONFIG_ROOT / "partner_rules" / "v3.json"
_V4_PATH = _CONFIG_ROOT / "partner_rules" / "v4.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _compiled_policy() -> dict[str, Any]:
    return {
        "policy_version_id": "policy-live",
        "policy_hash": "policy-hash-live",
        "dimensions": {
            "market": {"weight": 50, "criteria": [{"id": "market-quality"}]},
            "execution": {
                "weight": 50,
                "criteria": [{"id": "execution-quality"}],
            },
        },
    }


def test_v4_removes_redundant_and_fixed_invariant_declarations() -> None:
    rules = _load(_V4_PATH)

    assert "min_avg_for_yes" not in rules["verdict_rules"]["STRONG"]
    assert "min_avg_for_maybe" not in rules["verdict_rules"]["MEDIUM"]
    assert "min_avg_for_borderline" not in rules["verdict_rules"]["MEDIUM"]
    assert "boundary_semantics" not in rules["score_thresholds"]
    assert "zero_confidence_ineligible" not in rules["decision_safety"]["claim_confidence"]
    assert not {
        "expired_action",
        "undated_action",
        "future_dated_action",
        "stale_action",
    } & rules["decision_safety"]["freshness"].keys()

    typed = parse_partner_rules(rules)
    assert isinstance(typed, PartnerRules)
    assert typed.version == "4.0"


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        (("verdict_rules", "STRONG"), "min_avg_for_yes", 8.0),
        (("verdict_rules", "MEDIUM"), "min_avg_for_maybe", 7.0),
        (("score_thresholds",), "boundary_semantics", {"advance": "greater_than_or_equal", "pass": "less_than"}),
        (("decision_safety", "claim_confidence"), "zero_confidence_ineligible", True),
        (("decision_safety", "freshness"), "stale_action", "cap"),
    ],
)
def test_v4_strictly_rejects_removed_declarations(
    section: tuple[str, ...], field: str, value: Any
) -> None:
    rules = _load(_V4_PATH)
    target = rules
    for segment in section:
        target = target[segment]
    target[field] = value

    with pytest.raises((ValueError, ValidationError)):
        parse_partner_rules(rules)


def test_historical_v3_remains_parseable_without_rewriting_its_document() -> None:
    document = _load(_V3_PATH)

    typed = parse_partner_rules(document)

    assert typed.version == "3.0"
    assert partner_rules_document(typed) == document


def test_v4_materializes_non_configurable_evaluator_invariants() -> None:
    policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=_load(_V4_PATH)
    )

    assert policy.advance_comparison == "greater_than_or_equal"
    assert policy.pass_comparison == "less_than"
    assert policy.decision_safety.claim_confidence.zero_confidence_ineligible is True
    freshness = policy.decision_safety.freshness
    assert freshness.expired_action == "ineligible"
    assert freshness.undated_action == "ineligible"
    assert freshness.future_dated_action == "ineligible"
    assert freshness.stale_action == "cap"


def _decision_leaf_paths(
    document: dict[str, Any], prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for key, value in document.items():
        if key in {"version", "description", "_comment"}:
            continue
        path = (*prefix, key)
        if isinstance(value, dict):
            paths.update(_decision_leaf_paths(value, path))
        else:
            paths.add(path)
    return paths


_NUMERIC_MUTATIONS: dict[tuple[str, ...], int | float] = {
    ("mandate_fit", "strong_fit_min"): 0.75,
    ("mandate_fit", "partial_fit_min"): 0.55,
    ("mandate_fit", "weak_fit_min"): 0.35,
    ("mandate_fit", "gate_invest_below"): 0.25,
    ("mandate_fit", "low_confidence_max"): 0.45,
    ("score_thresholds", "min_avg_pass"): 5.9,
    ("score_thresholds", "min_avg_strong_yes"): 8.2,
    ("score_thresholds", "min_avg_medium_maybe"): 7.1,
    ("score_thresholds", "min_avg_borderline_low"): 6.1,
    ("score_thresholds", "max_avg_borderline_high"): 7.1,
    ("score_thresholds", "grey_zone_min"): 6.6,
    ("score_thresholds", "grey_zone_max"): 7.6,
    ("score_thresholds", "grey_zone_confidence_max"): 0.8,
    ("score_thresholds", "minimum_scored_weight"): 0.6,
    ("contradictory_scores", "min_gap"): 3.5,
    ("contradictory_scores", "high_threshold"): 8.5,
    ("contradictory_scores", "low_threshold"): 3.5,
    ("llm_fallback_triggers", "medium_borderline_edge_window"): 0.7,
    ("llm_fallback_triggers", "low_score_near_threshold_window"): 0.2,
    ("decision_safety", "evidence_eligibility", "min_support_strength"): 0.55,
    ("decision_safety", "evidence_eligibility", "min_source_quality"): 0.45,
    ("decision_safety", "claim_confidence", "minimum_eligible"): 0.55,
    ("decision_safety", "claim_confidence", "full_confidence_at"): 0.85,
    (
        "decision_safety",
        "claim_confidence",
        "score_cap_below_full_confidence",
    ): 7.89,
    (
        "decision_safety",
        "claim_confidence",
        "recommendation_confidence_cap_below_full_confidence",
    ): 0.55,
    ("decision_safety", "freshness", "max_age_days"): 181,
    ("decision_safety", "freshness", "stale_score_cap"): 7.89,
    ("decision_safety", "freshness", "stale_confidence_cap"): 0.55,
    ("decision_safety", "source_quality", "full_confidence_at"): 0.85,
    (
        "decision_safety",
        "source_quality",
        "score_cap_below_full_quality",
    ): 7.89,
    (
        "decision_safety",
        "source_quality",
        "recommendation_confidence_cap_below_full_quality",
    ): 0.6,
}

_ENUM_MUTATIONS: dict[tuple[str, ...], str] = {
    ("mandate_fit", "held_recommendation"): "PASS",
    ("verdict_rules", "WEAK", "decision"): "MAYBE",
    ("verdict_rules", "STRONG", "decision_yes"): "MAYBE",
    ("verdict_rules", "STRONG", "decision_below_strong_yes_bar"): "NO",
    ("verdict_rules", "MEDIUM", "decision_maybe"): "NO",
    ("verdict_rules", "MEDIUM", "decision_borderline_no_llm"): "NO",
}


def _value_at(document: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = document
    for segment in path:
        value = value[segment]
    return value


def _valid_mutation(document: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    mutated = deepcopy(document)
    target = mutated
    for segment in path[:-1]:
        target = target[segment]
    current = target[path[-1]]
    if path in _NUMERIC_MUTATIONS:
        replacement: Any = _NUMERIC_MUTATIONS[path]
    elif path in _ENUM_MUTATIONS:
        replacement = _ENUM_MUTATIONS[path]
    elif isinstance(current, bool):
        replacement = not current
    elif isinstance(current, int):
        replacement = current - 1 if current > 1 else current + 1
    elif isinstance(current, list):
        replacement = [*current, "v4-authority-mutation"]
    elif isinstance(current, str):
        replacement = f"{current} (v4 authority mutation)"
    else:
        raise AssertionError(f"No valid mutation for {'.'.join(path)}")
    target[path[-1]] = replacement
    return mutated


_ACTIVE_V4_LEAVES = sorted(_decision_leaf_paths(_load(_V4_PATH)))


@pytest.mark.parametrize(
    "path",
    _ACTIVE_V4_LEAVES,
    ids=lambda path: ".".join(path),
)
def test_mutating_every_active_v4_decision_leaf_changes_manifest_identity(
    path: tuple[str, ...],
) -> None:
    original = _load(_V4_PATH)
    mutated = _valid_mutation(original, path)

    original_policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=original
    )
    mutated_policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=mutated
    )

    assert _value_at(mutated, path) != _value_at(original, path)
    assert mutated_policy.partner_rules_hash != original_policy.partner_rules_hash
    assert mutated_policy.partner_rules_version == original_policy.partner_rules_version
