from datetime import datetime, timezone

from fund_intelligence.observations import build_observations


def _case(
    evaluation_id,
    *,
    ruling="advance",
    sector="infrastructure",
    technical=8,
    execution=3,
    accepted_risks=None,
    positive_factors=None,
    day=1,
    outcome=None,
):
    return {
        "evaluation_id": evaluation_id,
        "decision_time": datetime(2026, 1, day, tzinfo=timezone.utc),
        "thesis_version_id": "thesis-1",
        "policy_version_id": "policy-1",
        "dimensions": {"sector": sector, "stage": "pre_seed", "geography": "ie"},
        "criteria": [
            {"criterion": "technical", "score": technical},
            {"criterion": "execution", "score": execution},
        ],
        "recommendation": {"recommended_state": "advance"},
        "ruling": {"decision": ruling, "override_type": "policy_disagreement" if ruling == "pass" else None},
        "interpretation": {
            "accepted_risks": accepted_risks or [],
            "positive_factors": positive_factors or [],
            "negative_factors": [],
            "decisive_factors": [],
        },
        "outcomes": [{"outcome_type": outcome}] if outcome else [],
    }


def test_criterion_tradeoff_retains_contradictory_cases_and_uses_canonical_bands():
    cases = [_case(f"support-{i}", day=i) for i in range(1, 4)]
    cases.append(_case("contradiction", ruling="pass", day=4))

    result = build_observations(cases, observation_type="criterion_tradeoff")
    observation = next(item for item in result if item["involved_criteria"] == ["execution", "technical"])

    assert observation["observation_family"] == "criterion_tradeoff"
    assert observation["direction"] == "strong technical / weak execution"
    assert observation["supporting_case_ids"] == ["support-1", "support-2", "support-3"]
    assert observation["contradictory_case_ids"] == ["contradiction"]
    assert observation["score_band_source"] == "resources/config/evaluation_rubric/v1.json"
    assert observation["value_ranges"] == {"technical": "strong", "execution": "weak"}


def test_practical_gate_is_segment_specific_and_suppresses_insufficient_samples():
    cases = [
        _case("infra-1", ruling="pass", day=1),
        _case("infra-2", ruling="pass", day=2),
        _case("infra-3", ruling="pass", day=3),
        _case("other-1", ruling="advance", sector="healthcare", day=4),
        _case("other-2", ruling="advance", sector="healthcare", day=5),
    ]
    result = build_observations(cases, observation_type="practical_gate")
    infra = next(item for item in result if item["segment"] == {"dimension": "sector", "value": "infrastructure"})
    assert infra["involved_criteria"] == ["execution"]
    assert infra["direction"] == "weak execution associated with non-approval"
    assert infra["sample_size"] == 3
    assert not any(item["segment"] == {"dimension": "sector", "value": "healthcare"} for item in result)


def test_practical_gate_is_emitted_once_per_weak_criterion_not_once_per_strong_pair():
    cases = []
    for day in range(1, 4):
        case = _case(f"gate-{day}", ruling="pass", day=day)
        case["criteria"].append({"criterion": "market", "score": 9})
        cases.append(case)

    result = build_observations(cases, observation_type="practical_gate")

    assert len(result) == 5
    assert all(item["involved_criteria"] == ["execution"] for item in result)
    assert all(item["supporting_case_ids"] == ["gate-1", "gate-2", "gate-3"] for item in result)
    assert len({item["observation_id"] for item in result}) == len(result)
    assert result == build_observations(list(reversed(cases)), observation_type="practical_gate")


def test_discounted_risk_requires_repeated_structured_interpretation_and_ignores_outcomes():
    cases = [
        _case(f"risk-{i}", day=i, accepted_risks=["long sales cycle"], positive_factors=["technical moat"], outcome="write_off")
        for i in range(1, 4)
    ]
    with_outcomes = build_observations(cases, observation_type="discounted_risk")
    without_outcomes = build_observations([{**case, "outcomes": []} for case in cases], observation_type="discounted_risk")
    assert with_outcomes == without_outcomes
    assert with_outcomes[0]["involved_factors"] == ["long sales cycle", "technical moat"]
    assert with_outcomes[0]["direction"] == "accepted risk with recurring positive factor"


def test_interaction_order_is_deterministic_and_mandate_versions_remain_separate():
    cases = [_case(f"a-{i}", day=i) for i in range(1, 4)]
    cases.extend(
        {**_case(f"b-{i}", day=i + 3), "thesis_version_id": "thesis-2"}
        for i in range(1, 4)
    )
    first = build_observations(cases)
    second = build_observations(list(reversed(cases)))
    assert first == second
    thesis_scoped = [
        item for item in first
        if item.get("segment", {}).get("dimension") == "thesis_version_id"
    ]
    assert {tuple(item["mandate_versions"]) for item in thesis_scoped} == {("thesis-1",), ("thesis-2",)}
