from services.scoring.scoring_engine import DeterministicScoringEngine
from services.scoring.policy_compiler import compile_policy_from_fund_config


def test_scoring_output_shape_snapshot():
    engine = DeterministicScoringEngine()
    scout = {
        "why_now": "AI adoption is growing 32% YoY with strong tailwinds.",
        "est_tam": "$12B",
    }
    review = {
        "market_confidence": "high",
        "product_confidence": "medium",
        "technical_confidence": "medium",
        "execution_confidence": "low",
        "defensibility_confidence": "medium",
        "competition_analysis": ["Crowded space with strong incumbents."],
    }
    result = engine.score(scout, review)
    assert set(result.keys()) == {
        "market",
        "product",
        "technical",
        "execution",
        "defensibility",
        "overall_score",
        "overall_confidence",
        "overall_dispersion",
        "raw_signals",
        "policy_version_id",
        "policy_hash",
        "stage_cohort",
        "stage_cohort_label",
        "sector_tam_benchmark",
        "calibration",
    }
    assert 0.0 <= result["market"]["score"] <= 10.0
    assert "components" in result["market"]
    assert "tam" in result["market"]["components"]
    assert "traction" in result["execution"]["components"]
    assert "value_prop" in result["product"]["components"]
    assert "complexity" in result["technical"]["components"]
    assert "brand" in result["defensibility"]["components"]


def test_policy_criteria_are_included_with_legacy_components():
    policy = compile_policy_from_fund_config(
        {
            "activePolicyVersionId": "policy_test_1234",
            "rubric": [
                {
                    "id": "market_conviction",
                    "dimension": "market",
                    "name": "Market conviction",
                    "weight": 100,
                    "positiveSignals": "Evidence-backed market pull.",
                    "negativeSignals": "Weak market evidence.",
                    "missingDataBehavior": "Reduce conviction until evidence is supplied.",
                    "examples": {
                        "score3": "Weak",
                        "score5": "Neutral",
                        "score7": "Strong",
                        "score9": "Exceptional",
                    },
                }
            ],
        }
    )
    engine = DeterministicScoringEngine(policy=policy)

    result = engine.score({"est_tam": "$12B", "why_now": "Budget urgency is high."}, {})

    assert result["policy_version_id"] == "policy_test_1234"
    assert "components" in result["market"]
    assert "criteria" in result["market"]
    criterion = result["market"]["criteria"]["market_conviction"]
    assert criterion["weight"] == 100.0
    assert criterion["source_components"] == [
        "tam",
        "growth_rate",
        "urgency",
        "timing",
        "competition",
    ]
    assert criterion["evidence_status"] in {"complete", "partial", "missing"}
    assert isinstance(criterion["missing_data_applied"], bool)


def test_no_data_company_is_unscored_not_mid_scored():
    """A company with no evidence at all is now fully unscored (every dimension flagged
    `unscored`, overall is None) instead of being assigned neutral mid scores — see the
    P3.2 abstain work in docs/scoring-remediation-checklist.md."""
    engine = DeterministicScoringEngine()
    result = engine.score({}, {})
    for dim in ("market", "product", "technical", "execution", "defensibility"):
        assert result[dim]["unscored"] is True
    assert result["overall_score"] is None


def test_overall_dispersion_flags_lopsided_profiles():
    """The overall is a mean, so a flat profile and a lopsided one can share a headline.
    `overall_dispersion` exposes the spread of the evidenced drivers so the memo can show
    a uniform 7 differs from [9,9,3,9]. Undefined (None) with fewer than two scored drivers."""
    engine = DeterministicScoringEngine()

    # No evidence → no drivers scored → dispersion undefined.
    assert engine.score({}, {})["overall_dispersion"] is None

    # A lopsided profile reports a wider range/std than a flat one with the same mean.
    flat = engine._compute_overall_dispersion(
        {d: {"score": 7.0, "unscored": False} for d in ("market", "product", "technical", "execution")}
    )
    lopsided = engine._compute_overall_dispersion(
        {
            "market": {"score": 9.0, "unscored": False},
            "product": {"score": 9.0, "unscored": False},
            "technical": {"score": 3.0, "unscored": False},
            "execution": {"score": 9.0, "unscored": False},
        }
    )
    assert flat["std"] == 0.0 and flat["range"] == 0.0
    assert lopsided["range"] == 6.0 and lopsided["std"] > flat["std"]

    # A single evidenced driver → spread undefined.
    assert engine._compute_overall_dispersion(
        {
            "market": {"score": 8.0, "unscored": False},
            "product": {"score": 5.0, "unscored": True},
            "technical": {"score": 5.0, "unscored": True},
            "execution": {"score": 5.0, "unscored": True},
        }
    ) is None


def test_full_pipeline_all_dimension_scores_present():
    engine = DeterministicScoringEngine()
    scout = {
        "one_line": "AI compliance copilot for healthcare workflows",
        "problem": "Compliance workflows are manual and expensive.",
        "solution": "Model-driven automation with proprietary compliance datasets.",
        "target_users": "Mid-market healthcare providers",
        "why_now": "Regulatory burden rising 45% and staffing gaps widening.",
        "est_tam": "$8B",
    }
    review = {
        "competition_analysis": ["Crowded incumbent market with fragmented SMB offerings."],
        "team_analysis": ["Experienced ex-Epic and ex-Palantir operators."],
        "business_model_analysis": ["Early revenue with repeatable outbound + partnerships."],
        "market_reasoning": ["Rapid demand growth and regulatory tailwinds."],
        "product_reasoning": ["Clear workflow UX and sticky daily usage."],
        "technical_reasoning": ["Scalable architecture with robust infra controls."],
        "defensibility_reasoning": ["Strong switching costs and proprietary data moat."],
    }
    result = engine.score(scout, review)
    for dim in ("market", "execution", "product", "technical", "defensibility"):
        assert "score" in result[dim]
        assert "confidence" in result[dim]
        assert "components" in result[dim]
        assert 0.0 <= result[dim]["score"] <= 10.0


def test_structured_signals_missing_placeholders_do_not_leak():
    engine = DeterministicScoringEngine()
    scout = {"why_now": "Regulatory pressure is rising quickly", "est_tam": "$3B"}
    review = {
        "structured_signals": {
            "market": {
                "tam": {"value": "[MISSING: tam]", "confidence": 0.9},
                "growth_rate": {"value": "[MISSING]", "confidence": 0.9},
                "urgency": {"label": "[MISSING]", "confidence": 0.9},
                "timing": {"label": "[MISSING]", "confidence": 0.9},
                "competition": {"label": "[MISSING]", "confidence": 0.9},
            }
        }
    }
    result = engine.score(scout, review)
    for dim in ("market", "execution", "product", "technical", "defensibility"):
        for component in result[dim]["components"].values():
            assert component.get("label") != "[MISSING]"
            assert component.get("value") != "[MISSING]"
    assert result["overall_score"] is None


def test_structured_signal_aliases_are_mapped_to_canonical_keys():
    engine = DeterministicScoringEngine()
    scout = {}
    review = {
        "structured_signals": {
            "market": {"growth": {"value": "24%", "confidence": 0.8}},
            "execution": {"gtm": {"label": "repeatable", "confidence": 0.8}},
        }
    }
    result = engine.score(scout, review)
    assert "growth_rate" in result["market"]["components"]
    assert "gtm_effectiveness" in result["execution"]["components"]


def test_partial_reviewer_structured_signals_backfill_other_dimensions():
    engine = DeterministicScoringEngine()
    scout = {
        "one_line": "Workflow automation for logistics operators",
        "problem": "Manual dispatch operations create delays and high error rates.",
        "solution": "AI orchestration with integrations into ERP and TMS systems.",
        "target_users": "Mid-market logistics teams",
        "why_now": "AI adoption tailwinds and labor shortages are accelerating urgency.",
        "est_tam": "$2.5B",
    }
    review = {
        "structured_signals": {
            "market": {
                "tam": {"value": "$2.5B", "confidence": 0.8},
                "growth_rate": {"value": "18%", "confidence": 0.7},
            }
        }
    }
    result = engine.score(scout, review)
    for dim in ("market", "execution", "product", "technical", "defensibility"):
        components = result[dim]["components"]
        assert isinstance(components, dict)
        assert len(components) == 5
