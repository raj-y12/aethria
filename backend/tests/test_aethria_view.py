"""Template Aethria view builder."""

from reviewer.aethria_view import build_aethria_view


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
    assert view.focal_question
    assert "disagreed" in view.tension_summary.lower() or "diverged" in view.tension_summary.lower()
