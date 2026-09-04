"""Partner v4 schema-to-consumer authority certification."""

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
from partner.decision import PartnerDecisionEngine


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


def _mutated_rules(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    rules = _load(_V4_PATH)
    target = rules
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = value
    return rules


def _engine(rules: dict[str, Any] | None = None, *, use_llm: bool = False) -> PartnerDecisionEngine:
    engine = PartnerDecisionEngine(use_llm_fallback=use_llm, api_key=None)
    engine._rules = parse_partner_rules(rules or _load(_V4_PATH))
    engine._fund_config = {}
    engine.evaluation_policy = None
    return engine


def _scout(**overrides: Any) -> dict[str, Any]:
    value = {
        "name": "Authority Co",
        "one_line": "Governed infrastructure",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.9,
    }
    value.update(overrides)
    return value


def _review(
    *, verdict: str = "MEDIUM", score: float = 7.2, **overrides: Any
) -> dict[str, Any]:
    value = {
        "verdict": verdict,
        "market_score": score,
        "product_score": score,
        "technical_score": score,
        "execution_score": score,
        "defensibility_score": score,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced founder with relevant operating history."],
        "business_model_analysis": ["Annual contracts with documented unit economics."],
    }
    value.update(overrides)
    return value


def test_weak_verdict_configuration_controls_entire_deterministic_payload() -> None:
    baseline = _engine().decide(_scout(), _review(verdict="WEAK", score=7.2))
    rules = _mutated_rules(("verdict_rules", "WEAK", "decision"), "MAYBE")
    rules["verdict_rules"]["WEAK"].update(
        conviction_level=4,
        next_action="Custom weak-verdict review",
        human_review_required=True,
    )
    mutated = _engine(rules).decide(_scout(), _review(verdict="WEAK", score=7.2))

    assert baseline["recommendation"] == mutated["recommendation"] == "MONITOR"
    assert baseline["human_review_required"] is mutated["human_review_required"] is True


def test_strong_yes_configuration_and_review_action_control_payload() -> None:
    baseline = _engine().decide(_scout(), _review(verdict="STRONG", score=8.4))
    rules = _mutated_rules(("verdict_rules", "STRONG", "decision_yes"), "MAYBE")
    rules["verdict_rules"]["STRONG"].update(
        conviction_level_yes=3,
        human_review_required_yes=False,
    )
    rules["next_actions"]["monitor"] = "Custom strong monitor"
    mutated = _engine(rules).decide(_scout(), _review(verdict="STRONG", score=8.4))

    assert baseline["recommendation"] == mutated["recommendation"] == "MONITOR"
    assert baseline["human_review_required"] is mutated["human_review_required"] is True


def test_strong_yes_without_review_uses_request_cap_table_policy() -> None:
    rules = _load(_V4_PATH)
    rules["verdict_rules"]["STRONG"]["human_review_required_yes"] = False
    rules["next_actions"]["request_cap_table"] = "Custom cap-table request"

    result = _engine(rules).decide(_scout(), _review(verdict="STRONG", score=8.4))

    assert result["recommendation"] == "MONITOR"
    assert result["human_review_required"] is True


def test_strong_below_bar_configuration_controls_entire_payload() -> None:
    rules = _load(_V4_PATH)
    rules["verdict_rules"]["STRONG"].update(
        decision_below_strong_yes_bar="NO",
        conviction_level_below_strong_yes_bar=3,
        next_action_below_strong_yes_bar="Custom below-bar pass",
        human_review_required_below_strong_yes_bar=True,
    )

    result = _engine(rules).decide(_scout(), _review(verdict="STRONG", score=7.4))

    assert result["recommendation"] == "MONITOR"
    assert result["human_review_required"] is True


def test_medium_maybe_decision_conviction_and_monitor_action_control_payload() -> None:
    baseline = _engine().decide(_scout(), _review(verdict="MEDIUM", score=7.2))
    rules = _mutated_rules(("verdict_rules", "MEDIUM", "decision_maybe"), "NO")
    rules["verdict_rules"]["MEDIUM"]["conviction_level_maybe"] = 3
    rules["next_actions"]["default_no"] = "Custom medium pass"
    mutated = _engine(rules).decide(_scout(), _review(verdict="MEDIUM", score=7.2))

    assert baseline["recommendation"] == mutated["recommendation"] == "MONITOR"
    assert baseline["human_review_required"] is mutated["human_review_required"] is True


def test_medium_borderline_configuration_controls_entire_payload() -> None:
    rules = _load(_V4_PATH)
    rules["verdict_rules"]["MEDIUM"].update(
        decision_borderline_no_llm="NO",
        conviction_level_borderline=2,
        next_action_borderline="Custom borderline pass",
    )

    result = _engine(rules).decide(_scout(), _review(verdict="MEDIUM", score=6.2))

    assert result["recommendation"] == "MONITOR"


def test_low_score_action_is_policy_governed() -> None:
    rules = _load(_V4_PATH)
    rules["next_actions"]["low_scores"] = "Custom low-score pass"

    result = _engine(rules).decide(_scout(), _review(verdict="MEDIUM", score=5.0))

    assert result["recommendation"] == "MONITOR"


def test_red_flag_keywords_escalate_human_review_without_changing_decision() -> None:
    review = _review(
        verdict="MEDIUM", score=7.2, key_risks=["Opaque governance dependency"]
    )
    baseline = _engine().decide(_scout(), review)
    rules = _load(_V4_PATH)
    rules["red_flag_keywords"].append("opaque governance")
    mutated = _engine(rules).decide(_scout(), review)

    assert baseline["recommendation"] == mutated["recommendation"] == "MONITOR"
    assert baseline["human_review_required"] is True
    assert mutated["human_review_required"] is True


def test_red_flag_review_escalation_survives_llm_narrative_path() -> None:
    rules = _load(_V4_PATH)
    rules["red_flag_keywords"].append("opaque governance")
    engine = _engine(rules, use_llm=True)

    def _fake_llm(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return engine._create_decision(
            recommendation="MONITOR",
            conviction=5,
            decision_rationale="Narrative only",
            next_action="Narrative action",
            human_review_required=False,
        )

    engine._decide_with_llm = _fake_llm  # type: ignore[method-assign]
    result = engine.decide(
        _scout(),
        _review(
            verdict="MEDIUM",
            score=7.2,
            key_risks=["Opaque governance dependency"],
        ),
    )

    assert result["recommendation"] == "MONITOR"
    assert result["human_review_required"] is True


def test_only_configured_assumption_keywords_create_feedback_risks() -> None:
    rules = _load(_V4_PATH)
    rules["assumption_risk_keywords"] = ["opaque dependency"]
    engine = _engine(rules)

    assert engine._compute_assumption_risks(
        _scout(), {}, ["Unknown risk in sales motion"]
    ) == []
    assert engine._compute_assumption_risks(
        _scout(), {}, ["Opaque dependency in sales motion"]
    ) == ["Opaque dependency in sales motion"]


def test_only_configured_missing_keywords_control_qualitative_strength() -> None:
    rules = _load(_V4_PATH)
    rules["missing_qualitative_keywords"] = ["opaque placeholder"]
    engine = _engine(rules)
    items = [
        "[MISSING] but this is now a substantive configured-safe line",
        "[MISSING] second substantive configured-safe diligence line",
    ]

    assert engine._has_strong_qualitative(items, engine._get_rules()) is True


def test_high_thesis_fallback_uses_configured_strong_fit_boundary() -> None:
    review = _review(thesis_alignment_score=0.72)
    baseline = _engine()
    rules = _load(_V4_PATH)
    rules["mandate_fit"]["strong_fit_min"] = 0.8
    mutated = _engine(rules)

    assert baseline._high_thesis_triggers_llm(review, 7.2, 7.0) is True
    assert mutated._high_thesis_triggers_llm(review, 7.2, 7.0) is False


@pytest.mark.parametrize(
    ("verdict", "score"),
    [
        ("MEDIUM", 5.999), ("MEDIUM", 6.0), ("MEDIUM", 6.999),
        ("MEDIUM", 7.0), ("STRONG", 7.999), ("STRONG", 8.0),
    ],
)
def test_fixed_score_boundary_precedence_is_exact(
    verdict: str, score: float
) -> None:
    result = _engine().decide(_scout(), _review(verdict=verdict, score=score))

    assert result["recommendation"] == "MONITOR"


def test_mutating_score_threshold_changes_the_selected_verdict_branch() -> None:
    baseline_rules = _load(_V4_PATH)
    baseline_rules["verdict_rules"]["STRONG"].update(
        conviction_level_yes=2,
        conviction_level_below_strong_yes_bar=7,
    )
    mutated_rules = deepcopy(baseline_rules)
    mutated_rules["score_thresholds"]["min_avg_strong_yes"] = 8.5

    baseline = _engine(baseline_rules).decide(
        _scout(), _review(verdict="STRONG", score=8.2)
    )
    mutated = _engine(mutated_rules).decide(
        _scout(), _review(verdict="STRONG", score=8.2)
    )

    assert baseline["recommendation"] == mutated["recommendation"] == "MONITOR"


def test_critical_risk_clamp_precedes_configurable_strong_decision() -> None:
    rules = _load(_V4_PATH)
    rules["verdict_rules"]["STRONG"].update(
        decision_yes="MAYBE",
        human_review_required_yes=False,
    )
    rules["next_actions"]["critical_risks"] = "Custom critical-risk stop"
    result = _engine(rules).decide(
        _scout(),
        _review(
            verdict="STRONG",
            score=9.0,
            key_risks=["Regulatory ban in the primary market"],
        ),
    )

    assert result["recommendation"] == "PASS"
    assert result["human_review_required"] is True
    assert result["next_action"] == "Custom critical-risk stop"


def test_missing_evidence_clamp_precedes_configurable_weak_decision() -> None:
    rules = _load(_V4_PATH)
    rules["verdict_rules"]["WEAK"].update(
        decision="NO",
        human_review_required=False,
        next_action="Unsafe weak pass",
    )
    rules["next_actions"]["human_review_monitor"] = "Custom evidence recovery"
    result = _engine(rules).decide(
        _scout(), _review(verdict="WEAK", score=9.0, execution_score=None)
    )

    assert result["recommendation"] == "MONITOR"
    assert result["human_review_required"] is True
    assert result["next_action"] == "Custom evidence recovery"


def test_critical_risk_clamp_precedes_missing_evidence_clamp() -> None:
    rules = _load(_V4_PATH)
    rules["next_actions"]["critical_risks"] = "Critical risk wins"
    rules["next_actions"]["human_review_monitor"] = "Evidence recovery loses"

    result = _engine(rules).decide(
        _scout(),
        _review(
            verdict="STRONG",
            score=9.0,
            execution_score=None,
            key_risks=["Regulatory ban in the primary market"],
        ),
    )

    assert result["recommendation"] == "PASS"
    assert result["human_review_required"] is True
    assert result["next_action"] == "Critical risk wins"


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


def _field_paths(prefix: tuple[str, ...], *fields: str) -> set[tuple[str, ...]]:
    return {(*prefix, field) for field in fields}


_CONSUMER_GROUPS: dict[str, set[tuple[str, ...]]] = {
    "mandate_gate": _field_paths(
        ("mandate_fit",),
        "enabled",
        "strong_fit_min",
        "partial_fit_min",
        "weak_fit_min",
        "gate_invest_below",
        "held_recommendation",
        "held_next_action",
        "low_confidence_max",
    ),
    "decision_rationale": _field_paths(
        ("quality_labels",), "STRONG", "MEDIUM", "WEAK"
    ),
    "verdict_branch": (
        _field_paths(
            ("verdict_rules", "WEAK"),
            "decision",
            "conviction_level",
            "next_action",
            "human_review_required",
        )
        | _field_paths(
            ("verdict_rules", "STRONG"),
            "decision_yes",
            "conviction_level_yes",
            "human_review_required_yes",
            "decision_below_strong_yes_bar",
            "conviction_level_below_strong_yes_bar",
            "next_action_below_strong_yes_bar",
            "human_review_required_below_strong_yes_bar",
        )
        | _field_paths(
            ("verdict_rules", "MEDIUM"),
            "decision_maybe",
            "conviction_level_maybe",
            "conviction_level_borderline",
            "decision_borderline_no_llm",
            "next_action_borderline",
        )
    ),
    "score_ladder_and_evaluator": _field_paths(
        ("score_thresholds",),
        "min_avg_pass",
        "min_avg_strong_yes",
        "min_avg_medium_maybe",
        "min_avg_borderline_low",
        "max_avg_borderline_high",
        "grey_zone_min",
        "grey_zone_max",
        "grey_zone_confidence_max",
        "minimum_scored_weight",
    ),
    "critical_risk_clamp": {("critical_risk_keywords",), ("critical_risk_pass_conviction",)},
    "contradiction_detection": _field_paths(
        ("contradictory_scores",),
        "min_gap",
        "high_threshold",
        "low_threshold",
    ),
    "red_flag_review_escalation": {("red_flag_keywords",)},
    "next_action_projection": _field_paths(
        ("next_actions",),
        "critical_risks",
        "low_scores",
        "default_no",
        "request_cap_table",
        "request_cap_table_and_review",
        "monitor",
        "human_review_monitor",
        "human_review_contradictions",
    ),
    "llm_fallback_router": _field_paths(
        ("llm_fallback_triggers",),
        "contradictory_scores",
        "medium_borderline_avg",
        "medium_borderline_edge_window",
        "low_score_near_threshold",
        "low_score_near_threshold_window",
        "missing_assumptions_affecting_decision",
        "missing_critical_qualitative",
        "reviewer_disagreement",
        "grey_zone_deep_dive",
    ),
    "qualitative_coverage": {("missing_qualitative_keywords",)},
    "assumption_risk_detection": {("assumption_risk_keywords",)},
    "evidence_eligibility": _field_paths(
        ("decision_safety", "evidence_eligibility"),
        "allowed_assertion_classes",
        "allowed_relationships",
        "require_verified_evidence",
        "min_support_strength",
        "min_source_quality",
        "blocked_trust_classes",
    ),
    "risk_and_exclusion_claim_evaluation": _field_paths(
        ("decision_safety",),
        "critical_risk_claim_types",
        "hard_exclusion_claim_types",
    ),
    "claim_confidence_caps": _field_paths(
        ("decision_safety", "claim_confidence"),
        "minimum_eligible",
        "full_confidence_at",
        "score_cap_below_full_confidence",
        "recommendation_confidence_cap_below_full_confidence",
    ),
    "freshness_caps": _field_paths(
        ("decision_safety", "freshness"),
        "max_age_days",
        "stale_score_cap",
        "stale_confidence_cap",
    ),
    "source_quality_caps": _field_paths(
        ("decision_safety", "source_quality"),
        "full_confidence_at",
        "score_cap_below_full_quality",
        "recommendation_confidence_cap_below_full_quality",
    ),
}

_CONSUMER_BY_PATH = {
    path: consumer
    for consumer, paths in _CONSUMER_GROUPS.items()
    for path in paths
}


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


def test_every_active_v4_decision_leaf_has_an_explicit_runtime_consumer() -> None:
    assert set(_CONSUMER_BY_PATH) == set(_ACTIVE_V4_LEAVES)


@pytest.mark.parametrize(
    "path",
    _ACTIVE_V4_LEAVES,
    ids=lambda path: f"{_CONSUMER_BY_PATH.get(path, 'UNREGISTERED')}:{'.'.join(path)}",
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
