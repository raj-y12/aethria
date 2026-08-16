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


def test_canonical_pass_overrides_a_high_score_that_would_otherwise_invest():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=9, product_score=9, technical_score=9, execution_score=9)

    out = engine.decide(_base_scout(), review, canonical_recommendation="pass")

    assert out["recommendation"] == "PASS"


def test_canonical_insufficient_evidence_does_not_force_the_ladder_either_way():
    """insufficient_evidence has no INVEST/PASS/MONITOR equivalent — the engine's
    own evidence-coverage branch owns that distinction, so this must fall back
    to the score-based ladder rather than being coerced onto it."""
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(market_score=9, product_score=9, technical_score=9, execution_score=9)

    with_canonical = engine.decide(_base_scout(), review, canonical_recommendation="insufficient_evidence")
    without_canonical = engine.decide(_base_scout(), review, canonical_recommendation=None)

    assert with_canonical["recommendation"] == without_canonical["recommendation"]


def test_no_canonical_recommendation_falls_back_to_the_verdict_ladder():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(
        verdict="STRONG", market_score=9, product_score=9, technical_score=9, execution_score=9
    )

    with_none = engine.decide(_base_scout(), review, canonical_recommendation=None)
    without_param = engine.decide(_base_scout(), review)

    assert with_none["recommendation"] == without_param["recommendation"] == "INVEST"


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


def test_canonical_override_also_reaches_the_grey_zone_llm_escalation_path():
    """The LLM-escalation trigger sites (_decide_with_llm) build their own
    final_recommendation from score_recommendation/branch_recommendation and
    don't route through _emit_deterministic — they need the same override
    applied at their own call sites (sub-project 1, Task 5)."""
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

    assert llm_kwargs.get("final_recommendation") == "INVEST"
    assert out["recommendation"] == "INVEST"
