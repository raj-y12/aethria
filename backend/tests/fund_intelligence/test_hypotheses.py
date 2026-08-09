from fund_intelligence.hypotheses import build_hypotheses


def _observation(
    observation_id,
    observation_type,
    *,
    segment=None,
    sample_size=6,
    sufficiency="moderate",
    rate=None,
    supporting=None,
    contradictory=None,
    metric=None,
):
    return {
        "observation_id": observation_id,
        "observation_type": observation_type,
        "segment": segment or {"scope": "fund"},
        "supporting_case_ids": supporting or [f"case-{index}" for index in range(sample_size)],
        "contradictory_case_ids": contradictory or [],
        "sample_size": sample_size,
        "time_window": {"from": "2026-01-01T00:00:00+00:00", "to": "2026-02-01T00:00:00+00:00"},
        "thesis_versions": ["thesis-1"],
        "mandate_versions": ["thesis-1"],
        "policy_versions": ["policy-1"],
        "metric": metric or {"numerator": round(sample_size * (rate or 0)), "denominator": sample_size, "rate": rate or 0},
        "sufficiency": sufficiency,
        "descriptive_confidence": 0.75,
        "limitations": ["Descriptive association only; this observation does not establish causality."],
    }


def test_low_sufficiency_does_not_generate_a_hypothesis():
    observations = [
        _observation("fund", "override_rate", sample_size=3, sufficiency="emerging", rate=0.66),
        _observation("sector", "override_rate", segment={"dimension": "sector", "value": "fintech"}, sample_size=3, sufficiency="emerging", rate=1.0),
    ]

    assert build_hypotheses(observations) == []


def test_segmented_hypothesis_is_grounded_and_retains_contradictions():
    observations = [
        _observation("fund", "override_rate", sample_size=10, sufficiency="strong", rate=0.2),
        _observation(
            "sector",
            "override_rate",
            segment={"dimension": "sector", "value": "infrastructure"},
            sample_size=6,
            rate=0.67,
            supporting=["case-1", "case-2", "case-3", "case-4"],
            contradictory=["case-5", "case-6"],
        ),
    ]

    result = build_hypotheses(observations)
    assert len(result) == 1
    hypothesis = result[0]
    assert hypothesis["hypothesis_family"] == "segment_specific_behavior"
    assert hypothesis["source_observation_ids"] == ["fund", "sector"]
    assert hypothesis["supporting_case_ids"] == ["case-1", "case-2", "case-3", "case-4"]
    assert hypothesis["contradictory_case_ids"] == ["case-5", "case-6"]
    assert "infrastructure" in hypothesis["statement"]
    assert hypothesis["status"] == "descriptive_hypothesis"
    assert "policy" in " ".join(hypothesis["limitations"]).lower()


def test_mandate_divergence_uses_only_versions_present_in_source_observation():
    observations = [
        _observation(
            "mandate",
            "mandate_behavior",
            sample_size=12,
            sufficiency="strong",
            supporting=["a", "b", "c", "d", "e", "f"],
            contradictory=["g", "h"],
            metric={"agreement_rate_by_thesis": {"thesis-a": 0.8, "thesis-b": 0.3}},
        ),
    ]

    hypothesis = build_hypotheses(observations)[0]
    assert hypothesis["hypothesis_family"] == "mandate_behavior_divergence"
    assert hypothesis["mandate_versions"] == ["thesis-a", "thesis-b"]
    assert "thesis-a" in hypothesis["statement"]
    assert "sector" not in hypothesis["statement"]


def test_hypothesis_generation_is_deterministic_and_has_no_outcome_fields():
    observations = [
        _observation("b", "override_rate", segment={"dimension": "sector", "value": "b"}, sample_size=6, rate=0.8),
        _observation("a", "override_rate", segment={"dimension": "sector", "value": "a"}, sample_size=6, rate=0.8),
        _observation("fund", "override_rate", sample_size=10, sufficiency="strong", rate=0.2),
    ]
    first = build_hypotheses(observations)
    second = build_hypotheses(list(reversed(observations)))
    assert first == second
    assert all("outcome" not in hypothesis for hypothesis in first)
