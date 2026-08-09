from fund_intelligence.replay import build_replay_preview


def _hypothesis(family="segment_specific_behavior"):
    return {
        "hypothesis_id": "hypothesis-1",
        "hypothesis_family": family,
        "segment": {"dimension": "sector", "value": "infrastructure"},
        "supporting_case_ids": ["evaluation-2", "evaluation-1"],
        "contradictory_case_ids": ["evaluation-3"],
        "mandate_versions": ["thesis-1"],
        "policy_versions": ["policy-1"],
        "time_window": {"from": "2026-01-01T00:00:00+00:00", "to": "2026-02-01T00:00:00+00:00"},
    }


def test_current_segment_hypothesis_is_explicitly_not_replayable():
    result = build_replay_preview(_hypothesis())

    assert result["replay_status"] == "not_replayable"
    assert result["historical_cases_evaluated"] == []
    assert result["cases_changed"] == []
    assert result["cases_unchanged"] == []
    assert result["cases_indeterminate"] == ["evaluation-1", "evaluation-2", "evaluation-3"]
    assert result["outcome_context_used_for_replay"] is False
    assert "policy delta" in " ".join(result["limitations"])


def test_mandate_divergence_is_not_replayable_without_machine_readable_policy_difference():
    result = build_replay_preview(_hypothesis("mandate_behavior_divergence"))

    assert result["replay_status"] == "not_replayable"
    assert "criterion transformation" in " ".join(result["limitations"])


def test_replay_preview_does_not_mutate_the_hypothesis_or_add_outcome_context():
    hypothesis = _hypothesis()
    before = dict(hypothesis)

    result = build_replay_preview(hypothesis)

    assert hypothesis == before
    assert "outcomes" not in result
