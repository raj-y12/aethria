from models import ReviewInfo, ScoutInfo, Startup
from memo_generator import MemoGenerator


def test_memo_uses_guarded_interpretation_and_surfaces_evidence_guard():
    startup = Startup(
        startup_id="s-memo",
        scout_info=ScoutInfo(
            startup_id="s-memo", name="TestCo", one_line="Test", sector="SaaS",
            problem="p", solution="s", target_users="u", why_now="now",
            scout_type="market_driven", confidence_score=0.8,
        ),
        review_info=ReviewInfo(
            market_score=6, product_score=6, technical_score=6, execution_score=6,
            overall_summary="Evidence-consistent regulatory interpretation.",
            key_risks=["Evidence-consistent regulatory interpretation."], verdict="MEDIUM",
            contradiction_guard={"corrections": [{
                "criterion": "regulatory", "state": "directly_contradicted",
                "guarded": "Evidence-consistent regulatory interpretation.",
                "evidence": [{"source_locator": "source.example"}],
            }]},
        ),
    )
    memo = MemoGenerator().generate_memo(startup, for_display=False, tenant_user_id="fund-a")
    assert "Evidence-consistent regulatory interpretation." in memo
    assert "Evidence Guard" in memo
    assert "Execution is impossible" not in memo
