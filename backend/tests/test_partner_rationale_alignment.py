"""Headline (canonical recommendation) vs deterministic rationale alignment."""

from partner.decision import PartnerDecisionEngine


def _scout():
    return {
        "name": "Co",
        "one_line": "AI-driven ops insights",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.8,
    }


def _review(**kw):
    base = {
        "verdict": "MEDIUM",
        "market_score": 7,
        "product_score": 7,
        "technical_score": 6,
        "execution_score": 6,
        "defensibility_score": None,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Team note."],
        "business_model_analysis": ["Model note."],
        "thesis_alignment_score": 0.7,
    }
    base.update(kw)
    return base


def test_pass_opening_not_monitor():
    eng = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    out = eng.decide(
        _scout(),
        _review(market_score=5, product_score=5, technical_score=5, execution_score=5),
        canonical_recommendation="pass",
    )
    assert out.get("recommendation") == "PASS"
    rl = (out.get("rationale") or "").lower()
    assert "canonical evaluation recommends pass" in rl


def test_monitor_opening_not_pass():
    eng = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    out = eng.decide(
        _scout(),
        _review(market_score=7, product_score=7, technical_score=7, execution_score=7),
        canonical_recommendation="monitor",
    )
    assert out.get("recommendation") == "MONITOR"
    rl = (out.get("rationale") or "").lower()
    assert "canonical evaluation recommends monitor" in rl


def test_invest_opening_not_pass():
    eng = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    out = eng.decide(
        _scout(),
        _review(
            verdict="STRONG",
            market_score=8,
            product_score=8,
            technical_score=8,
            execution_score=8,
        ),
        canonical_recommendation="advance",
    )
    assert out.get("recommendation") == "INVEST"
    rl = (out.get("rationale") or "").lower()
    assert "canonical evaluation recommends advance" in rl


def test_decision_drivers_nonempty_when_weak_verdict():
    eng = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    out = eng.decide(
        _scout(),
        _review(
            verdict="WEAK",
            market_score=4,
            product_score=4,
            technical_score=4,
            execution_score=4,
        ),
        canonical_recommendation="pass",
    )
    assert out.get("recommendation") == "PASS"
    drivers = out.get("decision_drivers") or []
    assert isinstance(drivers, list)
    assert drivers and drivers[0] == "canonical_pass"
