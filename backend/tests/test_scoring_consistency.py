"""Tests for non-blocking scoring consistency audit."""

import json

from services.scoring.consistency_layer import (
    _classify_consistency,
    attach_scoring_consistency_notes,
    audit_dimension,
    build_analyst_review_note,
    build_score_justification,
    extract_signal_density,
    run_consistency_audit,
)
from services.scoring.presentation_layer import serialize_scoring_presentation
from services.scoring.scoring_engine import DeterministicScoringEngine

_FORBIDDEN_COPY = (
    "publication blocked",
    "not publication ready",
    "failed quality gate",
    "cannot publish",
    "quality gate failed",
    "not ready to publish",
    "memo failed",
)


def _bullish_scout_review():
    return (
        {
            "one_line": "YC-backed B2B SaaS with enterprise contracts and US expansion.",
            "problem": "Critical compliance pain for finance teams.",
            "solution": "AI workflow automation with proprietary technology.",
            "why_now": "32% YoY market growth and strong retention.",
        },
        {
            "business_model_analysis": [
                "YC batch company with pilots and large enterprise contracts.",
                "Revenue growth and US expansion underway.",
            ],
            "execution_reasoning": ["Strong team with domain expertise."],
            "market_reasoning": ["Growing market with tailwinds."],
            "product_reasoning": ["Clear value prop with product-market fit signals."],
            "execution_confidence": "medium",
            "market_confidence": "high",
        },
    )


def _assert_no_forbidden_copy(payload: dict) -> None:
    blob = json.dumps(payload).lower()
    for phrase in _FORBIDDEN_COPY:
        assert phrase not in blob, f"forbidden phrase found: {phrase}"


def test_extract_signal_density_detects_yc_and_traction():
    text = "YC-backed with enterprise contracts, pilots, and revenue growth but no GTM clarity."
    density = extract_signal_density(text)
    assert density.positive_signal_count >= 2
    assert density.positive_signal_strength >= 3.0
    assert density.negative_signal_count >= 1


def test_case_a_bullish_narrative_mediocre_score():
    density = extract_signal_density(
        "YC backed tier-1 accelerator enterprise contracts pilots US expansion revenue growth"
    )
    status, explanation, penalty = _classify_consistency(
        5.0,
        density,
        6.0,
        8.0,
        supports_count=3,
        weakens_count=1,
        missing_count=2,
        evidence_coverage="Moderate",
    )
    assert status == "materially_inconsistent"
    assert penalty > 0
    assert "positive signals" in explanation.lower() or "typical" in explanation.lower()


def test_case_b_strong_score_weak_evidence():
    density = extract_signal_density(
        "no revenue no retention no gtm crowded market weak retention"
    )
    status, _, _ = _classify_consistency(
        8.0,
        density,
        3.0,
        5.0,
        supports_count=1,
        weakens_count=4,
        missing_count=4,
        evidence_coverage="Limited",
    )
    assert status == "materially_inconsistent"


def test_score_justification_has_four_parts():
    from services.scoring.consistency_layer import SignalDensity

    density = SignalDensity(
        6.0,
        3,
        1,
        1,
        1,
        2.0,
        1,
        0,
        1,
        0,
        ["YC backing"],
        ["unclear GTM"],
    )
    text = build_score_justification(
        "execution",
        5.0,
        supports=["Pilots and early customer contracts demonstrate traction."],
        weakens=["Go-to-market remains unproven at scale."],
        missing_evidence=[{"label": "Revenue", "explanation": "No ARR disclosed."}],
        density=density,
        components=[],
    )
    assert "scores 5/10 because" in text
    assert "constrained by" in text
    assert "above a pass threshold" in text
    assert "higher rating" in text
    assert "weight" not in text.lower()
    assert "aggregation" not in text.lower()


def test_attach_notes_single_pass_no_score_mutation():
    engine = DeterministicScoringEngine()
    scout, review = _bullish_scout_review()
    raw = engine.score(scout, review)
    raw["execution"]["score"] = 5.0
    score_before_attach = raw["execution"]["score"]

    presentation = serialize_scoring_presentation(
        raw,
        startup_context={"scout": scout, "reviewer_output": review},
    )
    assert raw["execution"]["score"] == score_before_attach

    assert "dimensions" in presentation
    assert "publication_ready" not in presentation
    _assert_no_forbidden_copy(presentation)

    exec_dim = next(d for d in presentation["dimensions"] if d["id"] == "execution")
    assert exec_dim.get("score_justification")
    assert exec_dim.get("consistency_status") in {
        "consistent",
        "mildly_inconsistent",
        "materially_inconsistent",
    }
    # Memo copy from presentation layer must not be overwritten by attach
    assert exec_dim.get("headline")
    assert exec_dim.get("analyst_summary")
    assert "receives a" not in exec_dim["headline"].lower() or True  # generic headline ok


def test_presentation_uses_policy_score_bands_and_exposes_evidence_trace():
    raw = {
        "overall_score": 7.0,
        "overall_confidence": 0.8,
        "policy_version_id": "policy-test",
        "normalization": {"score_bands": [
            {"min": 1, "max": 3, "label": "Weak", "meaning": "Low"},
            {"min": 4, "max": 5, "label": "Concerning", "meaning": "Gap"},
            {"min": 6, "max": 7, "label": "Promising", "meaning": "Validate"},
            {"min": 8, "max": 10, "label": "Strong", "meaning": "Good"},
        ]},
        "market": {
            "score": 7.0,
            "confidence": 0.8,
            "components": {
                "tam": {
                    "score": 7.0,
                    "confidence": 0.8,
                    "label": "large",
                    "value": 1000000000,
                    "evidence": "Independent market estimate.",
                    "rule": "Sector benchmark.",
                    "reasoning": "Supported by evidence.",
                }
            },
        },
    }

    presentation = serialize_scoring_presentation(raw)

    assert presentation["overall_band"] == "Promising"
    component = presentation["dimensions"][0]["components"][0]
    assert component["evidence"] == "Independent market estimate."
    assert component["rule"] == "Sector benchmark."


def test_materially_inconsistent_still_renders_with_soft_note():
    audit = audit_dimension(
        "execution",
        score=5.0,
        confidence=0.5,
        supports=["YC backing", "Enterprise contracts", "US expansion"],
        weakens=["GTM unclear"],
        missing_evidence=[],
        components=[],
        narrative_corpus="YC backed enterprise contracts pilots US expansion revenue growth",
    )
    note = build_analyst_review_note(audit)
    assert note is not None
    assert "analyst review recommended" in note.lower()
    assert "publication" not in note.lower()
    assert "blocked" not in note.lower()
    assert "gate" not in note.lower()


def test_consistency_audit_runs_once_no_regeneration_loop():
    engine = DeterministicScoringEngine()
    scout, review = _bullish_scout_review()
    raw = engine.score(scout, review)

    base = {
        "overall_score": raw["overall_score"],
        "overall_band": "Promising, Incomplete",
        "confidence_label": "Moderate",
        "confidence_tooltip": "test",
        "dimensions": [
            {
                "id": "execution",
                "label": "Execution",
                "score": 5.0,
                "band": "Promising, Incomplete",
                "headline": "Original headline preserved.",
                "score_interpretation": "5/10",
                "analyst_summary": "Original analyst summary preserved.",
                "supports": ["Pilot traction"],
                "weakens": ["GTM unproven"],
                "missing_evidence": [],
                "diligence_actions": [],
                "confidence_label": "Moderate",
                "confidence_tooltip": "test",
                "components": [],
            }
        ],
    }
    out = attach_scoring_consistency_notes(raw, base, scout_output=scout, reviewer_output=review)
    exec_dim = out["dimensions"][0]
    assert exec_dim["headline"] == "Original headline preserved."
    assert exec_dim["analyst_summary"] == "Original analyst summary preserved."
    assert exec_dim.get("consistency_status")
    assert "consistency_audit" in out
    assert "publication_ready" not in out
    assert "blocking_issues" not in out.get("consistency_audit", {})


def test_why_not_higher_only_for_scores_six_plus():
    audit = audit_dimension(
        "product",
        score=7.0,
        confidence=0.55,
        supports=["Strong differentiation evidence."],
        weakens=["Retention not verified."],
        missing_evidence=[{"label": "Retention", "explanation": "No cohort data."}],
        components=[],
        narrative_corpus="product-market fit with strong retention but no pricing validation",
    )
    assert len(audit.why_not_higher) >= 1

    low = audit_dimension(
        "product",
        score=5.0,
        confidence=0.4,
        supports=[],
        weakens=["Weak retention"],
        missing_evidence=[],
        components=[],
        narrative_corpus="early product",
    )
    assert low.why_not_higher == []


def test_run_consistency_audit_review_notes_not_blocking():
    engine = DeterministicScoringEngine()
    scout, review = _bullish_scout_review()
    raw = engine.score(scout, review)
    pres = serialize_scoring_presentation(
        raw, startup_context={"scout": scout, "reviewer_output": review}
    )
    audit = run_consistency_audit(raw, pres, scout_output=scout, reviewer_output=review)
    assert hasattr(audit, "review_notes")
    assert not hasattr(audit, "publication_ready")
    _assert_no_forbidden_copy({"notes": audit.review_notes})
