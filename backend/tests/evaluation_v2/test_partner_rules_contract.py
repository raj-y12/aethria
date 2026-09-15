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


@pytest.mark.asyncio
async def test_former_employer_acquisition_is_not_startup_ownership():
    from tests.investment_analysis.test_authority import run_case

    def former_employer(claims, links):
        claims[0]["display_text"] = "Synthetic's COO previously worked at Novate Medical (acquired by BTG plc)."

    result, _ = await run_case(action="ADVANCE", mutate=former_employer)
    assert result.partner.operational_action == "ADVANCE"
    assert not any("ownership" in item.lower() for item in result.partner.constraints)


def test_v5_versions_new_authority_without_changing_evidence_safety_limits():
    directory = _RULES_PATH.parent
    old = json.loads((directory / "v4.json").read_text())
    new = json.loads((directory / "v5.json").read_text())
    assert new["version"] == "5.0"
    assert "Partner chooses" in new["description"]
    for key in old.keys() - {"version", "description"}:
        assert new[key] == old[key], key


@pytest.mark.asyncio
async def test_live_partner_judgment_is_not_selected_by_legacy_score_thresholds():
    from tests.investment_analysis.test_authority import run_case

    passed, _ = await run_case(proposal=8, action="PASS")
    advanced, _ = await run_case(proposal=8, action="ADVANCE")
    assert [item.score for item in passed.evaluation.criteria] == [item.score for item in advanced.evaluation.criteria]
    assert passed.partner.operational_action == "PASS"
    assert advanced.partner.operational_action == "ADVANCE"
    assert passed.partner.judgment.action == "PASS"

    unsupported, _ = await run_case("B_strong_looking_unverified", proposal=8, action="ADVANCE")
    assert unsupported.partner.judgment.action == "ADVANCE"
    assert unsupported.partner.operational_action == "MORE_DILIGENCE"
    assert unsupported.partner.constraints


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


def test_compiled_policy_marks_each_configured_dimension_required_for_evaluation():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules=_rules()
    )

    assert {criterion.criterion for criterion in policy.criteria} == {
        "market",
        "execution",
    }
    assert all(criterion.required for criterion in policy.criteria)


@pytest.mark.asyncio
@pytest.mark.parametrize("verified,expected", [(True, "PASS"), (False, "MORE_DILIGENCE")])
async def test_live_partner_judgment_retained_when_explicit_fund_exclusion_constrains_action(verified, expected):
    from investment_analysis.models import ReviewerDraft, PartnerDraft
    from investment_analysis.service import analyze
    from pipeline_contracts.models import Lineage, Identity
    from tests.investment_analysis.test_mandate import sector_snapshot
    from tests.evaluation_v2.test_phase0_provenance_e2e import _policy
    from tests.evaluation_v2.test_phase0_golden_pipeline import CLOCK

    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment="Sector established; investment dimensions need diligence.")
        return PartnerDraft(action="ADVANCE", rationale=["Test senior judgment before the mandate check."],
                            confidence=0.8, investment_case="Test opportunity")

    result = await analyze(
        user_id="fund-a", lineage=Lineage(user_id="fund-a"), identity=Identity(name="Synthetic"),
        snapshot=sector_snapshot(verified=verified), policy=_policy(), evaluation_at=CLOCK,
        context={"fund_configuration": {"mandate": {"excludedSectorList": ["gambling"]}}},
        generate=generate,
    )
    assert result.partner.judgment.action.value == "ADVANCE"
    assert result.partner.operational_action.value == expected
    assert result.partner.constraints
    assert bool(result.evaluation.recommendation.mandate_conflicts) is verified
    assert any("sector" in item for item in (
        result.evaluation.recommendation.mandate_conflicts + result.evaluation.recommendation.missing_information
    ))


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
