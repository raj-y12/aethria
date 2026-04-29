"""
Regression: scout facts on ScoutInfo must reach reviewer/scorer payloads (ReviewerEngine shape).
"""

from models import ScoutInfo, Startup
from reviewer.engine import ReviewerEngine
from services.scoring.extraction_layer import extract_structured_signals, _scout_narrative_bundle


def _scout_info(**overrides):
    data = {
        "startup_id": "wire-1",
        "name": "WireCo",
        "one_line": "B2B automation for compliance teams",
        "sector": "B2B SaaS",
        "problem": "Manual compliance workflows cost enterprises millions annually.",
        "solution": "AI-assisted policy monitoring with pilot ARR from three F500 accounts.",
        "target_users": "Mid-market and enterprise risk teams",
        "why_now": "New SEC rules drive 18% YoY spend on GRC tooling.",
        "scout_type": "market_driven",
        "confidence_score": 0.82,
        "primary_thesis": "Regulatory tailwinds expand GRC TAM.",
        "key_assumptions": ["Buyers expand budget", "Product integrates with ServiceNow"],
        "biggest_unknown": "Sales cycle length",
        "references": ["https://wireco.example.com", "https://news.example.com/wireco"],
        "est_tam": "$14B",
        "funding_stage": "Seed",
    }
    data.update(overrides)
    return ScoutInfo(**data)


def test_build_scout_output_payload_includes_tam_stage_references_scout_type():
    startup = Startup(startup_id="wire-1", scout_info=_scout_info())
    payload = ReviewerEngine._build_scout_output_payload(startup)
    assert payload["id"] == "wire-1"
    assert payload["est_tam"] == "$14B"
    assert payload["funding_stage"] == "Seed"
    assert payload["scout_type"] == "market_driven"
    assert len(payload["references"]) == 2
    assert payload["problem"].startswith("Manual compliance")


def test_engine_shaped_scout_output_flows_est_tam_to_market_extraction():
    startup = Startup(
        startup_id="wire-2",
        scout_info=_scout_info(startup_id="wire-2", est_tam="$8B"),
    )
    scout_output = ReviewerEngine._build_scout_output_payload(startup)
    extracted = extract_structured_signals(scout_output, {})
    tam = extracted["market"]["tam"]
    assert tam.get("value") == "$8B"


def test_scout_narrative_bundle_includes_problem_and_est_tam():
    startup = Startup(
        startup_id="wire-3",
        scout_info=_scout_info(startup_id="wire-3"),
    )
    scout_output = ReviewerEngine._build_scout_output_payload(startup)
    bundle = _scout_narrative_bundle(scout_output)
    assert "Manual compliance" in bundle
    assert "$14B" in bundle or "14B" in bundle
