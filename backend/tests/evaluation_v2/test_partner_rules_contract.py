from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation_v2.partner_rules import PartnerRules
from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites
from partner.decision import PartnerDecisionEngine


_RULES_PATH = (
    Path(__file__).resolve().parents[3]
    / "resources"
    / "config"
    / "partner_rules"
    / "v3.json"
)


def _rules() -> dict[str, Any]:
    return json.loads(_RULES_PATH.read_text())


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


def _decision_leaf_paths(
    document: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    for key, value in document.items():
        if key in {"description", "_comment"}:
            continue
        path = (*prefix, key)
        if isinstance(value, dict):
            paths.extend(_decision_leaf_paths(value, path))
        else:
            paths.append(path)
    return paths


_DECISION_LEAF_PATHS = _decision_leaf_paths(_rules())


def _parent_at(document: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    parent = document
    for segment in path[:-1]:
        parent = parent[segment]
    return parent


def _object_paths(
    document: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    paths = [prefix]
    for key, value in document.items():
        if isinstance(value, dict):
            paths.extend(_object_paths(value, (*prefix, key)))
    return paths


_OBJECT_PATHS = _object_paths(_rules())
_NUMERIC_LEAF_PATHS = [
    path
    for path in _DECISION_LEAF_PATHS
    if isinstance(_parent_at(_rules(), path)[path[-1]], (int, float))
    and not isinstance(_parent_at(_rules(), path)[path[-1]], bool)
]
_LIST_LEAF_PATHS = [
    path
    for path in _DECISION_LEAF_PATHS
    if isinstance(_parent_at(_rules(), path)[path[-1]], list)
]


def _invalid_replacement(value: Any) -> Any:
    if isinstance(value, bool):
        return "true"
    if isinstance(value, (int, float)):
        return float("inf")
    if isinstance(value, str):
        return ""
    if isinstance(value, list):
        return []
    raise AssertionError(f"No corruption fixture for {type(value)!r}")


@pytest.mark.parametrize(
    "path", _DECISION_LEAF_PATHS, ids=lambda path: ".".join(path)
)
def test_every_decision_bearing_partner_rule_leaf_is_required(path):
    rules = _rules()
    del _parent_at(rules, path)[path[-1]]

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    "path", _DECISION_LEAF_PATHS, ids=lambda path: ".".join(path)
)
def test_every_decision_bearing_partner_rule_leaf_rejects_invalid_values(path):
    rules = _rules()
    parent = _parent_at(rules, path)
    parent[path[-1]] = _invalid_replacement(parent[path[-1]])

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    "path", _NUMERIC_LEAF_PATHS, ids=lambda path: ".".join(path)
)
def test_numeric_partner_rules_reject_string_coercion(path):
    rules = _rules()
    parent = _parent_at(rules, path)
    parent[path[-1]] = str(parent[path[-1]])

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    "path", _LIST_LEAF_PATHS, ids=lambda path: ".".join(path)
)
def test_partner_rule_string_lists_reject_blank_items(path):
    rules = _rules()
    _parent_at(rules, path)[path[-1]] = [""]

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize(
    "path", _OBJECT_PATHS, ids=lambda path: ".".join(path) or "root"
)
def test_partner_rules_reject_unknown_fields_at_every_nesting_family(path):
    rules = _rules()
    target = rules
    for segment in path:
        target = target[segment]
    target["typo_that_must_not_be_ignored"] = True

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


@pytest.mark.parametrize("verdict", ["WEAK", "MEDIUM", "STRONG"])
def test_verdict_rule_bodies_cannot_be_empty(verdict):
    rules = _rules()
    rules["verdict_rules"][verdict] = {}

    with pytest.raises(ValueError, match="partner_rules"):
        evaluation_policy_from_compiled(_compiled_policy(), partner_rules=rules)


def test_prerequisites_inject_one_typed_rules_object_consumed_by_partner():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=_rules()
    )
    prerequisites = EvaluationPrerequisites(
        user_id="user-a",
        thesis_context={"version_id": "thesis-live"},
        thesis_version_id="thesis-live",
        compiled_scoring_policy=_compiled_policy(),
        partner_rules=_rules(),
        fund_config={},
        policy=policy,
    )
    engine = PartnerDecisionEngine(
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
        use_llm_fallback=False,
    )

    assert isinstance(prerequisites.partner_rules, PartnerRules)
    assert engine._get_rules() is prerequisites.partner_rules


def test_partner_consumes_validated_rule_values_without_behavioral_defaults():
    rules = _rules()
    rules["quality_labels"]["MEDIUM"] = "Custom policy label"
    rules["llm_fallback_triggers"]["medium_borderline_edge_window"] = 0.2
    rules["contradictory_scores"] = {
        "min_gap": 6,
        "high_threshold": 9,
        "low_threshold": 2,
    }
    policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=rules
    )
    prerequisites = EvaluationPrerequisites(
        user_id="user-a",
        thesis_context={"version_id": "thesis-live"},
        thesis_version_id="thesis-live",
        compiled_scoring_policy=_compiled_policy(),
        partner_rules=rules,
        fund_config={},
        policy=policy,
    )
    engine = PartnerDecisionEngine(
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
        use_llm_fallback=False,
    )

    assert engine._verdict_label("MEDIUM") == "Custom policy label"
    assert not engine._is_medium_borderline_edge_case(
        avg_score=6.7,
        min_avg_borderline_low=6,
        max_avg_borderline_high=7,
        llm_triggers=prerequisites.partner_rules.llm_fallback_triggers,
    )
    assert not engine._has_contradictory_scores(
        8, 3, 7, 7, prerequisites.partner_rules
    )
