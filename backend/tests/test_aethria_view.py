"""Historical Aethria view records remain readable."""

from investment_analysis.projection import polish_aethria_view_for_api


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
    assert out["headline"] == "VibeFlow — Evidence read."
    assert out["thesis_fit_line"] == ""
