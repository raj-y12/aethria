from datetime import datetime, timezone

from fund_intelligence.observations import build_observations


def _case(
    evaluation_id: str,
    *,
    recommendation: str = "advance",
    ruling: str = "ADVANCE",
    thesis: str = "thesis-1",
    sector: str = "fintech",
    override_type: str | None = None,
    factor: str | None = None,
    outcome: str | None = None,
    day: int = 1,
):
    interpretation = {
        "positive_factors": [factor] if factor else [],
        "negative_factors": [],
        "accepted_risks": [],
        "decisive_factors": [],
        "overridden_criteria": [],
    }
    return {
        "evaluation_id": evaluation_id,
        "decision_time": datetime(2026, 1, day, tzinfo=timezone.utc),
        "thesis_version_id": thesis,
        "policy_version_id": "policy-1",
        "dimensions": {"sector": sector, "stage": "seed", "geography": "ie"},
        "recommendation": {"recommended_state": recommendation},
        "ruling": {"decision": ruling, "override_type": override_type},
        "interpretation": interpretation,
        "outcomes": [{"outcome_type": outcome}] if outcome else [],
    }


def test_low_sample_observations_are_suppressed_and_order_is_deterministic():
    cases = [_case("e-2", day=2), _case("e-1", day=1)]

    assert build_observations(cases) == []

    cases.append(_case("e-3", day=3, sector="healthcare"))
    first = build_observations(cases)
    second = build_observations(list(reversed(cases)))
    assert first == second
    assert all(item["sample_size"] >= 3 for item in first)


def test_agreement_contains_supporting_and_contradictory_cases():
    cases = [
        _case("agree-1"),
        _case("agree-2"),
        _case("disagree-1", ruling="PASS"),
    ]

    observation = next(
        item for item in build_observations(cases)
        if item["observation_type"] == "recommendation_ruling_agreement"
        and item["segment"] == {"scope": "fund"}
    )
    assert observation["metric"] == {"numerator": 2, "denominator": 3, "rate": 2 / 3}
    assert observation["supporting_case_ids"] == ["agree-1", "agree-2"]
    assert observation["contradictory_case_ids"] == ["disagree-1"]


def test_segmented_overrides_and_mandate_drift_are_descriptive():
    cases = [
        _case("a", thesis="thesis-1", sector="fintech", override_type="risk_acknowledged"),
        _case("b", thesis="thesis-1", sector="fintech", override_type="risk_acknowledged"),
        _case("c", thesis="thesis-1", sector="fintech"),
        _case("d", thesis="thesis-2", sector="healthcare", override_type="strategic_exception"),
        _case("e", thesis="thesis-2", sector="healthcare"),
        _case("f", thesis="thesis-2", sector="healthcare"),
    ]

    observations = build_observations(cases)
    sector = next(
        item for item in observations
        if item["observation_type"] == "override_rate"
        and item["segment"] == {"dimension": "sector", "value": "fintech"}
    )
    assert sector["metric"] == {"numerator": 2, "denominator": 3, "rate": 2 / 3}
    drift = next(item for item in observations if item["observation_type"] == "mandate_behavior")
    assert drift["mandate_versions"] == ["thesis-1", "thesis-2"]
    assert "causal" in " ".join(drift["limitations"]).lower()


def test_repeated_factors_are_returned_without_using_outcomes():
    cases = [
        _case("e-1", factor="strong founder-market fit", outcome="write_off"),
        _case("e-2", factor="strong founder-market fit"),
        _case("e-3", factor="strong founder-market fit"),
    ]
    with_outcomes = build_observations(cases)
    without_outcomes = build_observations([{**case, "outcomes": []} for case in cases])
    assert with_outcomes == without_outcomes
    factor = next(item for item in with_outcomes if item["observation_type"] == "recurring_factor")
    assert factor["segment"] == {"factor": "strong founder-market fit"}
    assert factor["metric"] == {"count": 3}


def test_filters_apply_to_historical_case_dimensions_and_dates():
    cases = [
        _case("ie-1", sector="fintech", day=1),
        _case("ie-2", sector="fintech", day=2),
        _case("ie-3", sector="fintech", day=2),
        _case("us-1", sector="healthcare", day=3),
    ]
    result = build_observations(
        cases,
        sector="fintech",
        date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 1, 2, 23, tzinfo=timezone.utc),
    )
    assert result
    assert all(set(item["supporting_case_ids"] + item["contradictory_case_ids"]) <= {"ie-1", "ie-2", "ie-3"} for item in result)


def test_observations_identify_latest_retrospective_interpretation_version():
    cases = [_case(f"e-{index}", factor="retention", day=index) for index in range(1, 4)]
    for case in cases:
        case["ruling"]["ruling_id"] = f"ruling-{case['evaluation_id']}"
        case["interpretation"] = {
            "interpretation_id": f"interpretation-{case['evaluation_id']}-2",
            "version": 2,
            "source": "operator_correction",
            "created_at": "2026-02-01T00:00:00+00:00",
            "positive_factors": ["retention"],
            "negative_factors": [],
            "accepted_risks": [],
            "decisive_factors": [],
            "overridden_criteria": [],
        }

    result = build_observations(cases)
    observation = next(item for item in result if item["observation_type"] == "recurring_factor")

    assert observation["interpretation_as_of"] == "latest_retrospective"
    assert observation["interpretation_provenance"] == [
        {
            "case_id": f"e-{index}",
            "ruling_id": f"ruling-e-{index}",
            "interpretation_id": f"interpretation-e-{index}-2",
            "version": 2,
            "source": "operator_correction",
            "created_at": "2026-02-01T00:00:00+00:00",
        }
        for index in range(1, 4)
    ]
