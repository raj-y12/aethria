"""Sub-project 1, Task 1: the canonical evaluator's recommendation takes
precedence over partner's own score-threshold ladder when supplied."""

from partner.decision import PartnerDecisionEngine


def _base_scout():
    return {
        "name": "Sona",
        "one_line": "AI-driven ops insights",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.8,
    }


def _base_review(**scores):
    review = {
        "verdict": "MEDIUM",
        "market_score": 6,
        "product_score": 6,
        "technical_score": 6,
        "execution_score": 6,
        "defensibility_score": None,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced founder with prior exit."],
        "business_model_analysis": ["Clear B2B SaaS pricing with gross-margin potential."],
        "thesis_alignment_score": 0.7,
    }
    review.update(scores)
    return review


def test_canonical_advance_overrides_a_low_score_that_would_otherwise_pass():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=5, product_score=5, technical_score=5, execution_score=5)

    out = engine.decide(_base_scout(), review, canonical_recommendation="advance")

    assert out["recommendation"] == "INVEST"


def test_canonical_decision_does_not_reaverage_criteria_or_reviewer_scores():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=1, product_score=1, technical_score=1, execution_score=1)
    criteria = [
        {"criterion": "market", "score": 8, "evidence_sufficiency": "sufficient"},
        {"criterion": "product", "score": 3, "evidence_sufficiency": "sufficient"},
        {"criterion": "technical", "score": 8, "evidence_sufficiency": "sufficient"},
        {"criterion": "execution", "score": 3, "evidence_sufficiency": "sufficient"},
    ]

    out = engine.decide(
        _base_scout(),
        review,
        canonical_recommendation="advance",
        canonical_criteria=criteria,
        canonical_confidence=0.9,
    )

    assert out["recommendation"] == "INVEST"
    assert out["company_quality"] is None
    assert "secondary score threshold" in out["decision_rationale"]
    assert "1.0/10" not in out["decision_rationale"]
    assert "3.0/10" not in out["decision_rationale"]


def test_canonical_pass_overrides_a_high_score_that_would_otherwise_invest():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=9, product_score=9, technical_score=9, execution_score=9)

    out = engine.decide(_base_scout(), review, canonical_recommendation="pass")

    assert out["recommendation"] == "PASS"


def test_missing_canonical_recommendation_is_the_same_fail_closed_monitor():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=9, product_score=9, technical_score=9, execution_score=9)

    with_canonical = engine.decide(_base_scout(), review, canonical_recommendation="insufficient_evidence")
    without_canonical = engine.decide(_base_scout(), review, canonical_recommendation=None)

    assert with_canonical["recommendation"] == without_canonical["recommendation"] == "MONITOR"


def test_no_canonical_recommendation_never_falls_back_to_the_verdict_ladder():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(
        verdict="STRONG", market_score=9, product_score=9, technical_score=9, execution_score=9
    )

    with_none = engine.decide(_base_scout(), review, canonical_recommendation=None)
    without_param = engine.decide(_base_scout(), review)

    assert with_none["recommendation"] == without_param["recommendation"] == "MONITOR"


def test_a_critical_risk_still_forces_pass_even_when_canonical_says_advance():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(
        verdict="STRONG", market_score=9, product_score=9, technical_score=9, execution_score=9
    )
    # Must match a configured critical_risk_keyword (resources/config/partner_rules) —
    # this engine detects critical risk by keyword, not free text.
    review["key_risks"] = ["Regulatory ban on this business model in the target market."]

    out = engine.decide(_base_scout(), review, canonical_recommendation="advance")

    assert out["recommendation"] == "PASS"


def test_canonical_recommendation_never_enters_the_legacy_grey_zone_ladder():
    """A canonical evaluation is already the evidence-policy outcome; Partner
    may add named safety gates but must not ask an LLM or rerun score bands."""
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review(
        market_score=7, product_score=7, technical_score=6, execution_score=6,
    )  # Core-dim avg = 6.5 — borderline band, triggers LLM escalation.

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE",
            confidence=6,
            rationale="LLM rationale",
            next_action="Monitor market and track progress",
            human_review_required=True,
            assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    out = engine.decide(_base_scout(), review, canonical_recommendation="advance")

    assert not llm_kwargs
    assert out["recommendation"] == "INVEST"
    assert out["company_quality"] is None
    assert "secondary score threshold" in out["decision_rationale"]
