"""Sub-project 2, Task 3: three of Partner's live dependencies on Reviewer's raw
scores now prefer canonical evaluate_snapshot() signals when supplied — the
evidence-coverage fail-closed gate, the grey-zone LLM-escalation trigger, and
reviewer_disagreement. Legacy Reviewer signals remain the fallback for
opportunities without a canonical evaluation yet."""

from partner.decision import PartnerDecisionEngine


def _base_scout():
    return {
        "name": "Sona",
        "one_line": "AI-driven ops insights",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.8,
    }


def _base_review(**overrides):
    review = {
        "verdict": "MEDIUM",
        "market_score": 7,
        "product_score": 7,
        "technical_score": 7,
        "execution_score": 7,
        "defensibility_score": None,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced founder with prior exit."],
        "business_model_analysis": ["Clear B2B SaaS pricing with gross-margin potential."],
        "thesis_alignment_score": 0.7,
    }
    review.update(overrides)
    return review


def _criterion(criterion, *, score=7.0, evidence_sufficiency="sufficient", contradicting=None):
    return {
        "criterion": criterion,
        "score": score,
        "evidence_sufficiency": evidence_sufficiency,
        "contradicting_claim_ids": contradicting or [],
    }


def _full_criteria(**overrides):
    base = {
        dim: _criterion(dim)
        for dim in ("market", "product", "technical", "execution")
    }
    base.update(overrides)
    return list(base.values())


# --- Evidence-coverage gate ------------------------------------------------

def test_canonical_insufficient_evidence_triggers_the_fail_closed_gate():
    """A dimension canonical marks insufficient forces the same MONITOR/PASS
    fail-closed branch legacy 'unscored' used to, even though Reviewer's own
    structured_scoring has a real number for every dimension."""
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()  # all 4 dims scored in the legacy structured output
    criteria = _full_criteria(market=_criterion("market", score=None, evidence_sufficiency="insufficient"))

    out = engine.decide(
        _base_scout(), review, canonical_recommendation="insufficient_evidence", canonical_criteria=criteria
    )

    assert out["human_review_required"] is True
    assert any("market" in risk for risk in out["risks"])


def test_fully_scored_canonical_criteria_does_not_trigger_the_gate():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    criteria = _full_criteria()

    out = engine.decide(_base_scout(), review, canonical_criteria=criteria)

    assert not any("Insufficient evidence coverage" in risk for risk in out["risks"])


def test_canonical_recommendation_never_prints_or_reuses_reviewer_scores():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(
        market_score=1, product_score=1, technical_score=1, execution_score=1,
    )
    criteria = _full_criteria(
        market=_criterion("market", score=8),
        product=_criterion("product", score=5),
        technical=_criterion("technical", score=3),
        execution=_criterion("execution", score=8),
    )

    out = engine.decide(
        _base_scout(), review, canonical_recommendation="advance", canonical_criteria=criteria
    )

    assert out["recommendation"] == "INVEST"
    assert "secondary score threshold" in out["decision_rationale"]
    assert "Market 1.0/10" not in out["decision_rationale"]


def test_no_canonical_criteria_never_falls_back_to_legacy_structured_scoring():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review(structured_scoring={
        "market": {"score": 7, "unscored": False},
        "product": {"score": None, "unscored": True},
        "technical": {"score": 7, "unscored": False},
        "execution": {"score": 7, "unscored": False},
    })

    out = engine.decide(_base_scout(), review)

    assert out["recommendation"] == "MONITOR"
    assert "canonical evaluation is blocked" in out["decision_rationale"].lower()


# --- Grey-zone escalation trigger ------------------------------------------

def test_low_canonical_confidence_does_not_reenter_the_legacy_grey_zone_ladder():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review(
        market_score=9, product_score=9, technical_score=9, execution_score=9,
    )
    criteria = _full_criteria(
        market=_criterion("market", score=9),
        product=_criterion("product", score=9),
        technical=_criterion("technical", score=9),
        execution=_criterion("execution", score=9),
    )

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE", confidence=5, rationale="grey zone",
            next_action="Monitor market and track progress",
            human_review_required=True, assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    engine.decide(
        _base_scout(), review, canonical_recommendation="advance", canonical_criteria=criteria, canonical_confidence=0.2,
    )

    assert not llm_kwargs


def test_high_canonical_confidence_does_not_force_grey_zone():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review(
        market_score=9, product_score=9, technical_score=9, execution_score=9,
        # Neutralize the unrelated high-thesis-alignment trigger so only the
        # grey-zone signal under test can cause an escalation here.
        thesis_alignment_score=0.1,
    )
    criteria = _full_criteria(
        market=_criterion("market", score=9),
        product=_criterion("product", score=9),
        technical=_criterion("technical", score=9),
        execution=_criterion("execution", score=9),
    )

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="YES", confidence=9, rationale="clear",
            next_action="Monitor market and track progress",
            human_review_required=False, assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    engine.decide(
        _base_scout(), review, canonical_criteria=criteria, canonical_confidence=0.95,
    )

    assert not llm_kwargs, "high canonical confidence should not force grey-zone escalation"


# --- Disagreement trigger ----------------------------------------------------

def test_contradicting_canonical_evidence_requires_human_review_without_llm_rescoring():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review(
        market_score=7, product_score=7, technical_score=6, execution_score=6,
    )
    criteria = _full_criteria(
        market=_criterion("market", score=7, contradicting=["claim-123"]),
    )

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE", confidence=6, rationale="disagreement",
            next_action="Monitor market and track progress",
            human_review_required=True, assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    result = engine.decide(
        _base_scout(), review, canonical_recommendation="advance", canonical_criteria=criteria, canonical_confidence=0.9,
    )

    assert not llm_kwargs
    assert result["human_review_required"] is True
    assert "contradicting_market" in result["decision_drivers"]


def test_no_canonical_criteria_never_uses_reviewer_disagreement_as_a_score_trigger():
    engine = PartnerDecisionEngine(use_llm_fallback=True, api_key=None)
    review = _base_review(
        # Avg = 9.0 — clear of the legacy grey-zone band (6.5-7.5) and the
        # high-thesis-alignment trigger neutralized, so disagreement is the
        # only active trigger.
        market_score=9, product_score=9, technical_score=9, execution_score=9,
        thesis_alignment_score=0.1,
        reviewer_disagreement=True,
    )

    llm_kwargs: dict = {}

    def fake_llm(*args, **kwargs):
        llm_kwargs.update(kwargs)
        return engine._create_decision(
            decision="MAYBE", confidence=6, rationale="disagreement",
            next_action="Monitor market and track progress",
            human_review_required=True, assumption_risks=[],
        )

    engine._decide_with_llm = fake_llm  # type: ignore[method-assign]
    result = engine.decide(_base_scout(), review)

    assert not llm_kwargs
    assert result["recommendation"] == "MONITOR"
