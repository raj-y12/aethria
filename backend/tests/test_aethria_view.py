"""Template Aethria view builder."""

from reviewer.aethria_view import (
    build_aethria_view,
    polish_aethria_view_for_api,
)


def test_build_aethria_view_basic():
    rev = {
        "derived_verdict": "MEDIUM",
        "verdict": "STRONG",
        "overall_summary": "Test.",
        "key_risks": ["Can they ship?"],
        "thesis_fit_points": ["Fits B2B SaaS mandate."],
        "thesis_deviation_points": [],
    }
    scout = {"name": "Acme Corp"}
    consensus = {"reviewer_disagreement": True}
    view = build_aethria_view(
        review_output=rev,
        scout_output=scout,
        consensus=consensus,
        resolution_notes=["market_score: personas diverged"],
    )
    assert "Acme Corp" in view.headline
    assert "MEDIUM" in view.headline
    assert "Aethria view" not in view.headline
    assert "disagreed" in view.tension_summary.lower() or "diverged" in view.tension_summary.lower()


def test_tension_prefers_disagreement_summary():
    rev = {
        "derived_verdict": "STRONG",
        "verdict": "STRONG",
        "overall_summary": "Ok.",
        "key_risks": ["Risk a"],
        "thesis_fit_points": ["Fits."],
        "disagreement_summary": "Material reviewer disagreement (max spread 3); primary scores adjusted.",
    }
    scout = {"name": "Co"}
    view = build_aethria_view(
        review_output=rev,
        scout_output=scout,
        consensus={"reviewer_disagreement": False},
        resolution_notes=[],
    )
    assert "Material reviewer disagreement" in view.tension_summary


def test_focal_question_prefers_deviation_then_weakest_dim():
    rev = {
        "derived_verdict": "MEDIUM",
        "verdict": "MEDIUM",
        "overall_summary": "Summary.",
        "key_risks": ["Generic risk"],
        "thesis_fit_points": ["Fit a"],
        "thesis_deviation_points": ["Stage too early for mandate."],
        "market_score": 8,
        "product_score": 4,
        "technical_score": 8,
        "execution_score": 8,
        "defensibility_score": 8,
    }
    scout = {"name": "X"}
    view = build_aethria_view(
        review_output=rev,
        scout_output=scout,
        consensus={},
        resolution_notes=[],
    )
    assert "Mandate gap" in view.focal_question
    assert "Stage too early" in view.focal_question

    rev2 = {**rev, "thesis_deviation_points": []}
    view2 = build_aethria_view(
        review_output=rev2,
        scout_output=scout,
        consensus={},
        resolution_notes=[],
    )
    assert "product" in view2.focal_question.lower()


def test_thesis_fit_skips_redundant_first_bullet():
    summary = (
        "Strong alignment with B2B SaaS and developer tooling mandate for enterprise buyers. "
        "Further detail in diligence."
    )
    rev = {
        "derived_verdict": "MEDIUM",
        "verdict": "MEDIUM",
        "overall_summary": summary,
        "key_risks": ["R1"],
        "thesis_fit_points": [
            "Strong alignment with B2B SaaS and developer tooling mandate.",
            "Second distinct fit point about GTM.",
        ],
        "thesis_deviation_points": [],
    }
    scout = {"name": "Co"}
    view = build_aethria_view(
        review_output=rev,
        scout_output=scout,
        consensus={},
        resolution_notes=[],
    )
    assert "Second distinct" in view.thesis_fit_line


def test_polish_legacy_headline_and_dedup_thesis():
    review = {
        "derived_verdict": "MEDIUM",
        "verdict": "MEDIUM",
        "overall_summary": "Strong alignment with B2B SaaS and developer tooling mandate.",
        "aethria_view": {
            "headline": "VibeFlow: Aethria view — MEDIUM.",
            "thesis_fit_line": "Strong alignment with B2B SaaS and developer tooling mandate.",
            "tension_summary": "x",
            "focal_question": "y",
        },
    }
    out = polish_aethria_view_for_api(review["aethria_view"], review, "VibeFlow")
    assert out is not None
    assert out["headline"] == "VibeFlow — MEDIUM."
    assert out["thesis_fit_line"] == ""
