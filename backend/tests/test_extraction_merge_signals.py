"""Merge policy and extractor enrichments for structured_signals."""

from services.scoring.extraction_layer import (
    extract_structured_signals,
    _provided_has_substantive_signal,
    _sanitize_provided_structured_signals,
)


def test_substantive_gate_accepts_label_only_or_value_only():
    sanitized = _sanitize_provided_structured_signals(
        {
            "market": {
                "tam": {"value": "$5B", "confidence": 0.8},
                "urgency": {"label": "high", "confidence": 0.7},
            }
        }
    )
    assert _provided_has_substantive_signal(sanitized) is True


def test_merge_prefers_deterministic_traction_when_llm_slot_empty():
    scout = {
        "one_line": "ExampleCo infrastructure monitoring",
        "problem": "Paying enterprise customers include several Fortune 500 pilots.",
        "solution": "Unified observability plane.",
        "why_now": "Incident costs rising.",
        "target_users": "SRE teams",
        "primary_thesis": "Bundled alerts reduce MTTR.",
    }
    review = {
        "structured_signals": {
            "market": {
                "urgency": {"label": "high", "confidence": 0.75},
            },
            "execution": {
                "traction": {"value": None, "reasoning": "No traction stated.", "confidence": 0.2},
            },
        },
    }
    sig = extract_structured_signals(scout, review)
    lab = sig["execution"]["traction"].get("label")
    assert lab in ("early_adoption", "early_revenue", "mvp", "scaling", "strong_scale")


def test_team_execution_detects_founder_markers_in_scout_bundle():
    scout = {
        "one_line": "DevTools",
        "problem": "CI/CD friction for distributed teams.",
        "solution": "Merge queue automation.",
        "why_now": "Shift-left adoption.",
        "target_users": "Platform engineers",
        "primary_thesis": "Founding team includes CTO previously at Google.",
    }
    sig = extract_structured_signals(scout, {})
    assert sig["execution"]["team_execution"].get("label") == "credible_team"
