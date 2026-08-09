from fund_intelligence.proposals import build_counterfactual_proposals


def _hypothesis(**overrides):
    value = {
        "hypothesis_id": "hypothesis-1",
        "hypothesis_family": "segment_specific_behavior",
        "statement": "The fund appears to record overrides more often in infrastructure.",
        "segment": {"dimension": "sector", "value": "infrastructure"},
        "supporting_case_ids": ["case-1", "case-2"],
        "contradictory_case_ids": ["case-3"],
        "sample_size": 6,
        "sufficiency": "moderate",
        "descriptive_confidence": 0.75,
        "mandate_versions": ["thesis-1"],
        "policy_versions": ["policy-1"],
        "time_window": {"from": "2026-01-01", "to": "2026-02-01"},
    }
    value.update(overrides)
    return value


def test_existing_hypothesis_without_policy_semantics_is_insufficient_basis():
    proposal = build_counterfactual_proposals([_hypothesis()])[0]

    assert proposal["proposal_status"] == "insufficient_basis"
    assert proposal["exact_rule"] is None
    assert proposal["source_hypothesis_id"] == "hypothesis-1"
    assert proposal["supporting_case_ids"] == ["case-1", "case-2"]
    assert proposal["contradictory_case_ids"] == ["case-3"]
    assert "criterion" in " ".join(proposal["assumptions_required"]).lower()


def test_explicit_existing_policy_rule_produces_deterministic_draft_counterfactual():
    hypothesis = _hypothesis(
        counterfactual_rule={
            "adaptation_type": "scoring_weight_adjustment",
            "policy_path": "scoringWeights",
            "dimension": "technical",
            "delta": -1.0,
            "parameter_sources": ["hypothesis-1"],
        }
    )

    first = build_counterfactual_proposals([hypothesis])
    second = build_counterfactual_proposals([dict(hypothesis)])
    assert first == second
    proposal = first[0]
    assert proposal["proposal_status"] == "draft_counterfactual"
    assert proposal["adaptation_type"] == "scoring_weight_adjustment"
    assert proposal["exact_rule"]["delta"] == -1.0
    assert proposal["provenance"]["owner"] == "aethria"
    assert proposal["provenance"]["basis"] == "explicit_structured_rule"


def test_untraceable_numeric_rule_is_rejected_without_inventing_a_threshold():
    hypothesis = _hypothesis(
        counterfactual_rule={
            "adaptation_type": "escalation_threshold_adjustment",
            "policy_path": "thresholds.escalation",
            "delta": 5,
            "parameter_sources": [],
        }
    )

    proposal = build_counterfactual_proposals([hypothesis])[0]
    assert proposal["proposal_status"] == "insufficient_basis"
    assert proposal["exact_rule"] is None
    assert "trace" in " ".join(proposal["assumptions_required"]).lower()
