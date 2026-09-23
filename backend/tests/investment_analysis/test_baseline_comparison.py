"""Explicit new-authority expectations beside the unchanged Phase 0 baseline.

These are model mocks, not a claim about production model quality. E deliberately
uses a Partner PASS: its old low thesis-fit score is not factual evidence and
must not be silently carried forward as a new deterministic exclusion.
"""
import json

import pytest

from tests.evaluation_v2.historical_fixtures import GOLDEN
from tests.investment_analysis.test_authority import run_case


@pytest.mark.asyncio
@pytest.mark.parametrize("case,proposal,action,scores,state", [
    ("A_strong_verified", 8, "ADVANCE", [8, 8, 8, 8, 8], "advance"),
    ("B_strong_looking_unverified", 9, "ADVANCE", [None] * 5, "insufficient_evidence"),
    ("C_contradictory", 8, "ADVANCE", [8, 8, 8, 8, 8], "insufficient_evidence"),
    ("D_missing_dimension", 8, "ADVANCE", [8, 8, 8, None, 8], "insufficient_evidence"),
    ("E_out_of_mandate", 8, "PASS", [8, 8, 8, 8, 8], "pass"),
    ("F_legacy_canonical_diverge", 9, "ADVANCE", [9, 9, 9, 9, 9], "advance"),
    ("G_insufficient_evidence", 8, "ADVANCE", [None] * 5, "insufficient_evidence"),
])
async def test_new_authority_against_frozen_companies(case, proposal, action, scores, state):
    baseline = json.loads(GOLDEN.read_text())[case]
    result, calls = await run_case(case, proposal=proposal, action=action)
    assert [item.score for item in result.evaluation.criteria] == scores
    assert result.evaluation.recommendation.state.value == state
    assert result.partner.judgment.action.value == action
    assert [stage for stage, _ in calls] == ["reviewer", "partner"]
    assert all(item.cap_reason for item in result.validation.assessments if item.validated_score is None)
    # A supported PASS does not need the human escalation used for advancement
    # or insufficient evidence.
    assert result.partner.human_review_required is (case != "E_out_of_mandate")
    assert "criterion_score" not in str(calls[0][1]["factual_evidence"])
    if case == "F_legacy_canonical_diverge":
        assert {item["score"] for item in baseline["evaluation"]["criteria"]} == {6}
        assert set(baseline["legacy_reviewer_scores"].values()) == {9}
        # New 9 is an explicit Reviewer proposal supported by strong evidence;
        # neither historical 6 nor legacy Reviewer 9 was sent to the model.
        assert all(item.proposed_score == 9 for item in result.validation.assessments)
