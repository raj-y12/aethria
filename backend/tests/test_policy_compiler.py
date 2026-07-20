import pytest

from services.scoring.policy_compiler import (
    PRODUCTION_DIMENSIONS,
    compile_policy_from_fund_config,
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
