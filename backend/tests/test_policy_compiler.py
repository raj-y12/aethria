from copy import deepcopy

import pytest

from services.scoring.policy_compiler import (
    PRODUCTION_DIMENSIONS,
    compile_policy_from_fund_config,
    validate_compiled_policy_bundle,
)


def test_empty_rubric_compiles_default_policy():
    policy = compile_policy_from_fund_config({"rubric": [], "scoringWeights": []})

    assert policy["policy_hash"]
    assert policy["policy_version_id"].startswith("draft_")
    assert set(policy["dimensions"].keys()) == set(PRODUCTION_DIMENSIONS)
    for dimension in PRODUCTION_DIMENSIONS:
        assert policy["dimensions"][dimension]["criteria"]
        criterion = policy["dimensions"][dimension]["criteria"][0]
        assert criterion["dimension"] == dimension
        assert criterion["source_components"]
        assert criterion["score_anchors"]["score3"]


def test_compiled_policy_contains_complete_hash_bound_scoring_runtime():
    policy = compile_policy_from_fund_config({})

    runtime = policy["scoring_runtime"]
    assert runtime["semantic_version"] == "1.0.0"
    assert runtime["calibration"]["mode"] in {"enforced", "shadow"}
    assert runtime["calibration"]["discount"] == {
        "floor_conf": 0.2,
        "full_conf": 0.8,
    }
    assert runtime["calibration"]["evidence_gate"] == {
        "min_completeness": 0.4,
        "min_avg_conf": 0.35,
        "cap": 6.0,
    }
    assert set(runtime["component_weights"]) == set(PRODUCTION_DIMENSIONS)
    assert runtime["overall"]["dimensions"] == [
        "market",
        "product",
        "technical",
        "execution",
    ]
    assert runtime["normalization"]["tam_thresholds"]
    assert runtime["normalization"]["growth_thresholds"]
    assert runtime["normalization"]["sector_tam_benchmarks"]
    assert policy["scoring_runtime_hash"]


def test_default_runtime_and_policy_hash_do_not_follow_environment_toggle(monkeypatch):
    monkeypatch.setenv("SCORING_EVIDENCE_CALIBRATION_ENABLED", "false")
    first = compile_policy_from_fund_config({})
    monkeypatch.setenv("SCORING_EVIDENCE_CALIBRATION_ENABLED", "true")
    second = compile_policy_from_fund_config({})

    assert first["scoring_runtime"] == second["scoring_runtime"]
    assert first["scoring_runtime_hash"] == second["scoring_runtime_hash"]
    assert first["policy_hash"] == second["policy_hash"]


def test_any_scoring_runtime_change_changes_runtime_and_policy_hash():
    baseline = compile_policy_from_fund_config({})
    changed_runtime = deepcopy(baseline["scoring_runtime"])
    changed_runtime["calibration"]["evidence_gate"]["cap"] = 5.5

    changed = compile_policy_from_fund_config(
        {"scoringRuntime": changed_runtime}, require_publish_ready=True
    )

    assert changed["scoring_runtime_hash"] != baseline["scoring_runtime_hash"]
    assert changed["policy_hash"] != baseline["policy_hash"]


def test_persisted_policy_rejects_missing_or_unknown_runtime_contract():
    missing = compile_policy_from_fund_config({})
    missing.pop("scoring_runtime")
    with pytest.raises(ValueError, match="complete decision-input bundle"):
        validate_compiled_policy_bundle(missing)

    unknown = compile_policy_from_fund_config({})
    unknown["scoring_runtime"]["calibration"]["mystery_mode"] = True
    with pytest.raises(ValueError, match="complete decision-input bundle"):
        validate_compiled_policy_bundle(unknown)


def _decision_config():
    return {
        "thresholds": {
            "autoPass": 39,
            "monitor": 59,
            "escalation": 75,
            "partnerReview": 60,
        },
        "scoreBands": [
            {"id": "pass", "min": 0, "max": 59, "label": "Pass"},
            {"id": "monitor", "min": 60, "max": 79, "label": "Monitor"},
            {"id": "invest", "min": 80, "max": 100, "label": "Invest"},
        ],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda config: config["thresholds"].update({"partnerReview": 61}),
        lambda config: config["scoreBands"][1].update({"max": 78}),
        lambda config: config["scoreBands"][2].update({"label": "Proceed"}),
    ],
    ids=["threshold", "score-band-boundary", "score-band-outcome"],
)
def test_every_consumed_tenant_decision_input_changes_published_hash(mutation):
    baseline = _decision_config()
    changed = _decision_config()
    mutation(changed)

    original = compile_policy_from_fund_config(baseline)
    modified = compile_policy_from_fund_config(changed)

    assert original["policy_hash"] != modified["policy_hash"]
    assert original["decision_inputs"] != modified["decision_inputs"]


def test_decision_bundle_hash_is_order_and_numeric_format_deterministic():
    baseline = _decision_config()
    equivalent = {
        "thresholds": {
            "partnerReview": "60.0",
            "escalation": 75.0,
            "monitor": "59",
            "autoPass": 39.0,
        },
        "scoreBands": list(reversed(baseline["scoreBands"])),
        "memo": {"style": "detailed"},
    }

    original = compile_policy_from_fund_config(baseline)
    reordered = compile_policy_from_fund_config(equivalent)

    assert reordered.get("decision_inputs") is not None
    assert original.get("decision_inputs") is not None
    assert reordered["decision_inputs"] == original["decision_inputs"]
    assert reordered["policy_hash"] == original["policy_hash"]


def test_configured_rubric_compiles_to_dimension_criteria():
    policy = compile_policy_from_fund_config(
        {
            "scoringWeights": [{"key": "market", "weight": 30}],
            "rubric": [
                {
                    "id": "market_conviction",
                    "dimension": "market",
                    "name": "Market conviction",
                    "description": "Market size, urgency, budget, and expansion.",
                    "weight": 100,
                    "positiveSignals": "Clear evidence-backed market pull.",
                    "negativeSignals": "Weak or shallow market evidence.",
                    "missingDataBehavior": "Treat as diligence debt.",
                    "examples": {
                        "score3": "Structurally weak.",
                        "score5": "Plausible but not proven.",
                        "score7": "Strong with diligence open.",
                        "score9": "Exceptional and well evidenced.",
                    },
                }
            ],
        }
    )

    criterion = policy["dimensions"]["market"]["criteria"][0]
    assert criterion["id"] == "market_conviction"
    assert criterion["weight"] == 100.0
    assert criterion["source_components"] == [
        "tam",
        "growth_rate",
        "urgency",
        "timing",
        "competition",
    ]
    assert policy["dimensions"]["market"]["weight"] == 30.0


@pytest.mark.parametrize(
    "rubric,error_fragment",
    [
        (
            [
                {
                    "id": "traction_depth",
                    "dimension": "traction",
                    "name": "Traction depth",
                    "weight": 100,
                    "examples": {
                        "score3": "Weak",
                        "score5": "Neutral",
                        "score7": "Good",
                        "score9": "Great",
                    },
                }
            ],
            "dimension",
        ),
        (
            [
                {
                    "id": "market_conviction",
                    "dimension": "market",
                    "name": "Market conviction",
                    "weight": 0,
                    "examples": {
                        "score3": "Weak",
                        "score5": "Neutral",
                        "score7": "Good",
                        "score9": "Great",
                    },
                }
            ],
            "weight",
        ),
        (
            [
                {
                    "id": "market_conviction",
                    "dimension": "market",
                    "name": "Market conviction",
                    "weight": 100,
                    "examples": {"score3": "Weak", "score5": "Neutral"},
                }
            ],
            "anchor",
        ),
    ],
)
def test_invalid_publish_policy_raises_field_errors(rubric, error_fragment):
    with pytest.raises(ValueError) as exc:
        compile_policy_from_fund_config({"rubric": rubric}, require_publish_ready=True)

    assert error_fragment in str(exc.value).lower()
