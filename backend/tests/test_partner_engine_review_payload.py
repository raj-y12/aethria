"""
Regression: PartnerEngine review dict must include fields PartnerDecisionEngine.decide() reads.
"""

from types import SimpleNamespace

from models import ReviewInfo, ScoutInfo, Startup
from partner.engine import PartnerEngine

# Keys emitted by PartnerEngine._build_entry → review (keep in sync with partner/engine.py).
PARTNER_REVIEW_PAYLOAD_KEYS = frozenset(
    {
        "market_score",
        "product_score",
        "technical_score",
        "execution_score",
        "defensibility_score",
        "overall_summary",
        "key_risks",
        "verdict",
        "assumption_feedback",
        "team_analysis",
        "competition_analysis",
        "business_model_analysis",
        "investment_thesis",
        "risk_mitigation",
        "score_reasoning",
        "reviewer_disagreement",
        "score_variance",
        "derived_verdict",
        "thesis_alignment_score",
        "thesis_matches_fund",
        "thesis_fit_points",
        "thesis_deviation_points",
        "thesis_alignment_confidence",
        "confidence_adjusted_score",
        "structured_scoring",
        "structured_signals",
        "resolution_notes",
        "disagreement_summary",
        "aethria_view",
        "reviews",
    }
)


def _minimal_scout() -> ScoutInfo:
    return ScoutInfo(
        startup_id="s-test",
        name="TestCo",
        one_line="Test",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="now",
        scout_type="market_driven",
        confidence_score=0.8,
    )


def test_build_entry_forwards_confidence_adjusted_score():
    review_info = ReviewInfo(
        market_score=7,
        product_score=7,
        technical_score=6,
        execution_score=6,
        overall_summary="Summary.",
        key_risks=[],
        verdict="MEDIUM",
        confidence_adjusted_score=6.174,
        derived_verdict="MEDIUM",
    )
    startup = Startup(
        startup_id="s-test",
        scout_info=_minimal_scout(),
        review_info=review_info,
    )
    storage = SimpleNamespace(_user_id="user-test")
    engine = PartnerEngine(
        storage=storage,
        tenant_user_id="user-test",
        use_llm_fallback=False,
    )
    entry = engine._build_entry(startup)
    assert entry is not None
    assert entry["review"]["confidence_adjusted_score"] == 6.174


def test_build_entry_review_keys_match_partner_contract():
    review_info = ReviewInfo(
        market_score=6,
        product_score=6,
        technical_score=6,
        execution_score=6,
        overall_summary="x",
        key_risks=[],
        verdict="MEDIUM",
    )
    startup = Startup(
        startup_id="s-test",
        scout_info=_minimal_scout(),
        review_info=review_info,
    )
    storage = SimpleNamespace(_user_id="user-test")
    engine = PartnerEngine(
        storage=storage,
        tenant_user_id="user-test",
        use_llm_fallback=False,
    )
    entry = engine._build_entry(startup)
    assert entry is not None
    assert frozenset(entry["review"]) == PARTNER_REVIEW_PAYLOAD_KEYS
