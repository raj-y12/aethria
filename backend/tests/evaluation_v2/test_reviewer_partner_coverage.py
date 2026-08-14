from __future__ import annotations

import pytest

from partner.decision import PartnerDecisionEngine
from reviewer.engine import ReviewerEngine
from services.reviewer_resolution import apply_resolution_to_primary
from utils.adapters import reviewer_output_to_review_info


class _TraceScoringEngine:
    def __init__(self, trace):
        self.trace = trace

    def score(self, _scout, _review):
        return self.trace


def _reviewer_output():
    return {
        "market_score": 9,
        "product_score": 9,
        "technical_score": 9,
        "execution_score": 9,
        "defensibility_score": 9,
        "overall_summary": "Promising, subject to evidence coverage.",
        "key_risks": [],
        "verdict": "STRONG",
        "derived_verdict": "STRONG",
        "team_analysis": ["Experienced operating team"],
        "business_model_analysis": ["Clear enterprise subscription model"],
    }


def _trace(scored_dimensions: set[str]):
    dimensions = ("market", "product", "technical", "execution", "defensibility")
    scored = [name for name in dimensions if name in scored_dimensions]
    return {
        **{
            name: {
                "score": 9 if name in scored_dimensions else 5,
                "confidence": 0.9 if name in scored_dimensions else 0,
                "components": {},
                "unscored": name not in scored_dimensions,
            }
            for name in dimensions
        },
        "overall_score": 9 if scored else None,
        "overall_confidence": 0.9 if scored else 0,
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
    }


def _aggregate_traces(scored_dimensions: set[str]):
    engine = ReviewerEngine.__new__(ReviewerEngine)
    engine.structured_scoring_engine = _TraceScoringEngine(_trace(scored_dimensions))
    persona_results = []
    for reviewer_type in (
        "DefaultReviewer",
        "SkepticalReviewer",
        "OpportunistReviewer",
    ):
        result = engine._apply_structured_scoring({}, _reviewer_output())
        result["reviewer_type"] = reviewer_type
        persona_results.append(result)

    primary = dict(persona_results[0])
    engine._blend_numeric_scores_into_primary(primary, persona_results)
    apply_resolution_to_primary(primary, persona_results)
    engine._refresh_derived_after_dimension_changes(primary, persona_results)
    engine._derive_verdict_from_scores(primary)

    # Exercise every persistence-facing aggregation helper used by both the
    # periodic and on-demand Reviewer paths. Missing dimensions must survive
    # consensus, per-persona snapshots, and the ReviewInfo compatibility model.
    consensus = engine._compute_consensus(persona_results)
    snapshots = engine._build_single_reviews(persona_results)
    review_info = reviewer_output_to_review_info(primary)
    review_info.reviews = snapshots
    review_info.consensus_verdict = consensus["consensus_verdict"]
    review_info.reviewer_disagreement = consensus["reviewer_disagreement"]
    review_info.score_variance = consensus["score_variance"]
    return review_info.model_dump(mode="json")


def _partner(monkeypatch):
    return PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
    )


def _scout():
    return {
        "name": "CoverageCo",
        "one_line": "Evidence coverage regression fixture",
        "sector": "Infrastructure",
        "funding_stage": "Seed",
        "confidence": 0.9,
    }


@pytest.mark.parametrize(
    "scored_dimensions",
    [
        set(),
        {"market"},
        {"market", "product", "technical"},
    ],
    ids=["no-scored-dimensions", "one-high-dimension", "partial-required-coverage"],
)
def test_incomplete_reviewer_coverage_remains_non_decisive_through_partner(
    monkeypatch, scored_dimensions
):
    review = _aggregate_traces(scored_dimensions)

    for dimension in {"market", "product", "technical", "execution"} - scored_dimensions:
        assert review[f"{dimension}_score"] is None
        assert all(
            snapshot[f"{dimension}_score"] is None
            for snapshot in review["reviews"]
        )
        assert f"{dimension}_score" not in review["score_variance"]
    assert review["overall_score"] is None
    assert review["confidence_adjusted_score"] is None
    assert review["derived_verdict"] is None

    decision = _partner(monkeypatch).decide(_scout(), review)

    assert decision["recommendation"] == "MONITOR"
    assert decision["decision"] == "MAYBE"
    assert decision["human_review_required"] is True
    assert decision["confidence"] < 0.5
    assert any("evidence" in risk.lower() for risk in decision["risks"])


def test_complete_grounded_reviewer_coverage_can_reach_invest(monkeypatch):
    review = _aggregate_traces(
        {"market", "product", "technical", "execution", "defensibility"}
    )

    assert review["overall_score"] == 9
    assert review["confidence_adjusted_score"] == 9
    assert review["derived_verdict"] == "STRONG"
    decision = _partner(monkeypatch).decide(_scout(), review)

    assert decision["recommendation"] == "INVEST"
