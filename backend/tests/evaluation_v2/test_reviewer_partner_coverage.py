from __future__ import annotations

import pytest

from partner.decision import PartnerDecisionEngine
from reviewer.engine import ReviewerEngine


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


def _apply_trace(scored_dimensions: set[str]):
    engine = ReviewerEngine.__new__(ReviewerEngine)
    engine.structured_scoring_engine = _TraceScoringEngine(_trace(scored_dimensions))
    return engine._apply_structured_scoring({}, _reviewer_output())


def _partner(monkeypatch):
    import partner.decision as decision_module

    monkeypatch.setattr(decision_module, "load_settings", lambda _user_id: {})
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
    review = _apply_trace(scored_dimensions)

    for dimension in {"market", "product", "technical", "execution"} - scored_dimensions:
        assert review[f"{dimension}_score"] is None

    decision = _partner(monkeypatch).decide(_scout(), review)

    assert decision["recommendation"] == "MONITOR"
    assert decision["decision"] == "MAYBE"
    assert decision["human_review_required"] is True
    assert decision["confidence"] < 0.5
    assert any("evidence" in risk.lower() for risk in decision["risks"])


def test_complete_grounded_reviewer_coverage_can_reach_invest(monkeypatch):
    review = _apply_trace(
        {"market", "product", "technical", "execution", "defensibility"}
    )

    decision = _partner(monkeypatch).decide(_scout(), review)

    assert decision["recommendation"] == "INVEST"
