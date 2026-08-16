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


def test_red_flag_keyword_is_named_not_just_a_silent_conviction_penalty():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    # A real red_flag_keyword (resources/config/partner_rules) — this predicate
    # previously only flipped human_review_required, with no visible reason.
    review = _review(key_risks=["Founder background check is missing."])

    out = engine.decide(_scout(), review)

    assert "red_flag_language_in_key_risks" in out["decision_drivers"]


def test_large_pre_seed_portfolio_penalty_is_named_not_silent():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine.portfolio_store = _FakePortfolioStore(total=25, sector_counts={})

    out = engine.decide(_scout(funding_stage="Pre-Seed"), _review())

    assert "large_portfolio_pre_seed_caution" in out["decision_drivers"]


def test_sector_concentration_penalty_is_named_not_only_prose():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine.portfolio_store = _FakePortfolioStore(total=5, sector_counts={"B2B SaaS": 3})

    out = engine.decide(_scout(), _review())

    assert "portfolio_sector_concentration" in out["decision_drivers"]
    # The existing prose sentence still fires too — this is additive, not a replacement.
    assert "sizing discipline" in out["decision_rationale"]


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
