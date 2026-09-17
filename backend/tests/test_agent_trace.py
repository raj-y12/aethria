from datetime import datetime

from agent_trace import (
    build_partner_trace,
    build_review_trace,
    build_scout_trace,
    merge_stage_trace,
)
from api import _backend_to_frontend
from models import ScoutInfo, Startup
from legacy_supabase.storage import _dict_to_row, _row_to_dict


def test_scout_trace_flags_thin_sources_and_on_demand_no_thesis():
    scout = {
        "id": "s1",
        "name": "ThinCo",
        "confidence": 0.42,
        "references": ["ThinCo - https://thin.example"],
        "source_evidence": [{"url": "https://thin.example", "supports": "Company identity evidence"}],
        "origin_type": "on_demand_lookup",
    }

    trace = build_scout_trace(
        scout,
        pipeline_run_id="run-1",
        active_thesis=None,
        settings={"fund_config": {"thresholds": {"confidenceFloor": 0.55}}},
    )

    assert trace["stage"] == "scout"
    assert trace["quality"]["status"] == "warning"
    assert "weak_sources" in trace["quality"]["quality_flags"]
    assert "low_scout_confidence" in trace["quality"]["quality_flags"]
    assert "no_active_thesis_for_on_demand_lookup" in trace["quality"]["quality_flags"]
    assert trace["evidence_coverage"]["source_count"] == 1


def test_review_trace_flags_missing_data_disagreement_and_low_signal_confidence():
    review = {
        "reviewer_disagreement": True,
        "score_variance": {"market_score": 4.5},
        "diligence_red_flags": [
            "Missing founding team details",
            "Missing revenue or traction data",
            "Competitive landscape unclear",
            "Missing valuation data",
        ],
        "structured_signals": {
            "market": {
                "tam": {"confidence": 0.1},
                "growth_rate": {"confidence": 0.2},
            },
            "execution": {"traction": {"confidence": 0.15}},
        },
        "thesis_matches_fund": False,
        "thesis_alignment_score": 0.25,
    }

    trace = build_review_trace(
        review,
        scout={"references": ["https://example.com"]},
        pipeline_run_id="run-1",
        gap_reference_urls=[],
        settings={"fund_config": {"thresholds": {"missingDataThreshold": 35}}},
    )

    quality = trace["quality"]
    assert quality["status"] == "needs_attention"
    assert "contested_review" in quality["quality_flags"]
    assert "missing_evidence" in quality["quality_flags"]
    assert "low_signal_confidence" in quality["quality_flags"]
    assert "thesis_mismatch" in quality["quality_flags"]
    assert "founding_team" in quality["missing_evidence"]
    assert trace["handoff_quality"]["human_review_recommended"] is True


def test_partner_trace_explainability_uses_drivers_and_quality_flags():
    partner = {
        "recommendation": "MONITOR",
        "confidence": 0.6,
        "decision_rationale": "We monitor pending evidence.",
        "decision_drivers": ["contested_review", "missing_evidence"],
        "human_review_required": True,
    }
    review = {
        "score_reasoning": {"market_score": "Large market, but crowded."},
        "thesis_alignment_score": 0.4,
    }
    scout = {"primary_thesis": "Workflow automation wedge.", "references": ["https://example.com"]}
    handoff_quality = {
        "quality_flags": ["weak_sources", "missing_evidence"],
        "missing_evidence": ["traction"],
        "human_review_recommended": True,
    }

    trace = build_partner_trace(
        partner,
        scout=scout,
        review=review,
        pipeline_run_id="run-1",
        handoff_quality=handoff_quality,
        settings={"fund_config": {"thresholds": {"partnerReview": 60, "escalation": 75}}},
    )

    assert trace["quality"]["status"] == "needs_attention"
    assert "weak_sources" in trace["quality"]["quality_flags"]
    assert "missing_evidence" in trace["quality"]["quality_flags"]
    assert "MONITOR" in trace["explainability"]["summary"]
    assert trace["explainability"]["settings_thresholds"]["partnerReview"] == 60


def test_merge_stage_trace_preserves_existing_stages():
    existing = {"scout": {"stage": "scout", "status": "completed"}}
    review = {"stage": "reviewer", "status": "completed"}

    merged = merge_stage_trace(existing, "reviewer", review)

    assert merged["version"] == "1"
    assert merged["scout"]["stage"] == "scout"
    assert merged["reviewer"]["stage"] == "reviewer"


def test_startup_storage_and_api_preserve_agent_trace():
    scout = ScoutInfo(
        startup_id="s1",
        name="TraceCo",
        one_line="Traceable decisions",
        sector="B2B SaaS",
        problem="p",
        solution="s",
        target_users="u",
        why_now="n",
        scout_type="market_driven",
        confidence_score=0.7,
    )
    startup = Startup(
        startup_id="s1",
        scout_info=scout,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        agent_trace={"version": "1", "scout": {"stage": "scout"}},
    )

    row = _dict_to_row(startup.to_dict(), "user-1")
    restored = _row_to_dict(row)
    frontend = _backend_to_frontend(restored)

    assert row["agent_trace"]["scout"]["stage"] == "scout"
    assert restored["agent_trace"]["scout"]["stage"] == "scout"
    assert frontend["agent_trace"]["scout"]["stage"] == "scout"
