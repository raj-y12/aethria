"""Sub-project 1, Task 4: facts that used to only nudge conviction_adjust
silently are now named on decision_drivers instead."""

from partner.decision import PartnerDecisionEngine


def _scout(**overrides):
    scout = {
        "name": "Sona", "sector": "B2B SaaS", "funding_stage": "Pre-Seed", "confidence": 0.8,
    }
    scout.update(overrides)
    return scout


def _review(**overrides):
    review = {
        "verdict": "STRONG",
        "market_score": 8, "product_score": 8, "technical_score": 8, "execution_score": 8,
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced founder with prior exit."],
        "business_model_analysis": ["Clear B2B SaaS pricing with gross-margin potential."],
    }
    review.update(overrides)
    return review


def test_reviewer_red_flag_does_not_override_a_canonical_recommendation():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    # A real red_flag_keyword (resources/config/partner_rules) — this predicate
    # previously only flipped human_review_required, with no visible reason.
    review = _review(key_risks=["Founder background check is missing."])

    out = engine.decide(_scout(), review, canonical_recommendation="advance")

    assert out["decision_drivers"] == ["canonical_advance"]


def test_portfolio_size_does_not_apply_a_hidden_adjustment_to_canonical_recommendation():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine.portfolio_store = _FakePortfolioStore(total=25, sector_counts={})

    out = engine.decide(_scout(funding_stage="Pre-Seed"), _review(), canonical_recommendation="advance")

    assert out["decision_drivers"] == ["canonical_advance"]


def test_sector_concentration_does_not_apply_a_hidden_adjustment_to_canonical_recommendation():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine.portfolio_store = _FakePortfolioStore(total=5, sector_counts={"B2B SaaS": 3})

    out = engine.decide(_scout(), _review(), canonical_recommendation="advance")

    assert out["decision_drivers"] == ["canonical_advance"]


class _FakePortfolioStore:
    def __init__(self, *, total: int, sector_counts: dict):
        self._total = total
        self._sector_counts = sector_counts

    def get_all_portfolio(self):
        return [{"startup_id": f"s{i}"} for i in range(self._total)]

    def get_all_startups(self):
        return [
            {"sector": sector, "metadata": {}}
            for sector, count in self._sector_counts.items()
            for _ in range(count)
        ] or [{"sector": "Other", "metadata": {}} for _ in range(self._total)]

    def get_startup(self, startup_id):
        return {"metadata": {"funding_stage": "Seed"}}
