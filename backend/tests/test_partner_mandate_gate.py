"""Mandate-fit gate: company quality and fund fit are separate judgments.

A strong company that is off-thesis must be HELD for an explicit IC exception
rather than auto-recommended INVEST. Thresholds come from the versioned
`mandate_fit` block in partner_rules.
"""

from partner.decision import PartnerDecisionEngine


def _scout(**kw):
    base = {
        "name": "Co",
        "one_line": "AI-driven ops insights",
        "sector": "B2B SaaS",
        "funding_stage": "Seed",
        "confidence": 0.9,
    }
    base.update(kw)
    return base


def _strong_review(**kw):
    """High-quality review that, absent any thesis gate, recommends INVEST."""
    base = {
        "verdict": "STRONG",
        "market_score": 9,
        "product_score": 9,
        "technical_score": 9,
        "execution_score": 9,
        "defensibility_score": 9,
        "score_reasoning": {},
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Strong founding team."],
        "business_model_analysis": ["Clear monetization."],
    }
    base.update(kw)
    return base


def _engine():
    return PartnerDecisionEngine(use_llm_fallback=False, api_key=None)


def test_strong_company_on_thesis_invests():
    out = _engine().decide(_scout(), _strong_review(thesis_alignment_score=0.85))
    assert out["recommendation"] == "INVEST"
    assert out["mandate_gate"] == "clear"
    assert out["fund_fit_label"] == "Strong fit"
    assert out["company_quality"] >= 8.0
    assert out["fund_fit"] == 8.5
    assert out["mandate_override_required"] is False


def test_strong_company_off_thesis_is_held():
    out = _engine().decide(_scout(), _strong_review(thesis_alignment_score=0.15))
    # Quality is investment-grade, but fund fit is below the mandate floor → held.
    assert out["recommendation"] == "MONITOR"
    assert out["decision"] == "MAYBE"
    assert out["mandate_gate"] == "held"
    assert out["mandate_override_required"] is True
    assert out["human_review_required"] is True
    assert out["fund_fit_label"] == "Outside thesis"
    assert "mandate exception" in (out["decision_rationale"] or "").lower()
    assert "exception" in (out["next_action"] or "").lower()


def test_explicit_exception_lets_off_thesis_company_invest():
    review = _strong_review(thesis_alignment_score=0.15, mandate_exception=True)
    out = _engine().decide(_scout(), review)
    # Exception permits the investment, but fit is still honestly off-thesis.
    assert out["recommendation"] == "INVEST"
    assert out["mandate_gate"] == "outside_thesis"
    assert out["fund_fit_label"] == "Outside thesis"
    assert out["mandate_override_required"] is False


def test_thesis_blind_lookup_does_not_gate():
    # No thesis_alignment_score (thesis-blind lookup) → no mandate signals, no gate.
    out = _engine().decide(_scout(), _strong_review())
    assert out["recommendation"] == "INVEST"
    assert out["mandate_gate"] == "no_mandate"
    assert out["fund_fit"] is None
    assert out["mandate_override_required"] is False


def test_acquired_company_with_stale_traction_is_blocked_not_auto_invested():
    """Regression for the Workvivo/Zoom case in docs/known-issues.md: a strong
    review built on pre-acquisition traction must not reach an automatic
    INVEST — it is held for ownership/identity review instead."""
    scout = _scout(why_now="Workvivo was acquired by Zoom in 2023.")
    review = _strong_review(
        overall_summary="Historical customer growth and a 2022 Series B round.",
        thesis_alignment_score=0.85,
    )

    out = _engine().decide(scout, review)

    assert out["recommendation"] != "INVEST"
    assert out["mandate_gate"] == "ownership_conflict"
    assert out["human_review_required"] is True
    assert out["mandate_override_required"] is True
    assert out["ownership_conflict"]["code"] == "ownership_conflict_detected"


def test_operator_verified_spinout_clears_the_ownership_gate():
    scout = _scout(
        why_now="Was acquired by Zoom, then spun back out as an independent company.",
        ownership_verified_spinout=True,
    )
    review = _strong_review(thesis_alignment_score=0.85)

    out = _engine().decide(scout, review)

    assert out["recommendation"] == "INVEST"
    assert out["mandate_gate"] == "clear"
