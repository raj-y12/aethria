"""Characterization tests for the two scoring/calibration bugs surfaced in the
design-partner demo. See docs/scoring-remediation-checklist.md (Issue 1 / Issue 2).

These tests LOCK IN CURRENT (buggy) behavior so the fix has an objective before/after.
They are written against the pure deterministic engine (no LLM, no I/O), which is a
function of (scout_output, structured_signals) and therefore fully replayable offline.

Fixtures are synthetic but built from the real signal shapes (see
test_structured_scoring_engine.py). They can be swapped for the literal demo companies
later — every reviewed startup persists `structured_signals` + `structured_scoring` in
Supabase (review_info) and via record_scoring_trail (engine.py P7.1 path), recoverable
by startup id.

WHEN THE FIX LANDS: the asserts marked `# BUG:` are expected to flip. Update them to the
post-fix expectations (documented inline) rather than deleting the test — the point is to
prove the number moved in the intended direction.
"""
from services.scoring.scoring_engine import DeterministicScoringEngine


# ── Issue 1: a STRONG label on near-zero evidence still produces a max sub-score ──────
#
# The reviewer asserts network_effects=strong with confidence 0.2 and no cited evidence.
# Confidence is reported but never discounts the score, so the *displayed sub-score* is
# 10/10 — exactly the demo artifact (high network-effects sub-score on sparse evidence).
THIN_EVIDENCE_SCOUT = {
    "name": "NascentCo",
    "one_line": "Early-stage startup",
    "sector": "devtools",
    "funding_stage": "pre-seed",
    "problem": "Some problem",
    "solution": "Some solution",
}
THIN_EVIDENCE_REVIEW = {
    "structured_signals": {
        "defensibility": {
            "network_effects": {
                "label": "strong",
                "confidence": 0.2,
                "reasoning": "speculative",
                "evidence": "",
            },
        },
        "product": {
            "value_prop": {"label": "clear", "confidence": 0.3, "reasoning": "short tagline"},
            "differentiation": {"label": "clear", "confidence": 0.25, "reasoning": "guess"},
        },
    }
}


def test_issue1_strong_label_low_confidence_yields_max_subscore_BUG():
    """BUG: confidence 0.2 does not discount the score; 'strong' -> full 10.0 sub-score.

    Post-fix expectation (1A confidence-discount): a strong/0.2 signal should resolve to
    roughly the unproven baseline (~5.0-6.0), and the defensibility dimension should be
    flagged evidence_capped (1B). Flip these asserts when the fix lands.
    """
    engine = DeterministicScoringEngine()
    result = engine.score(THIN_EVIDENCE_SCOUT, THIN_EVIDENCE_REVIEW)

    ne = result["defensibility"]["components"]["network_effects"]
    assert ne["label"] == "strong"
    assert ne["confidence"] == 0.2
    # BUG: full-credit score despite near-zero evidence confidence.
    assert ne["score"] == 10.0
    # BUG: no evidence-sufficiency flag exists on the dimension yet.
    assert "evidence_capped" not in result["defensibility"]


# ── Issue 2: when both companies have thin evidence, stage/quality ordering collapses ──
#
# A multi-billion-$ enterprise and a pre-seed company, each with sparse scout narrative.
# The enterprise's real-world scale (traction/team/scalability) is never extracted, so
# those fact-derived components abstain and the score floats on generic qualitative
# defaults — identical to the pre-seed. The headline cannot separate them; ordering even
# inverts.
ENTERPRISE_THIN_SCOUT = {
    "name": "BigCo",
    "sector": "fintech",
    "funding_stage": "Series C",
    "one_line": "Enterprise payments platform for global commerce",
    "problem": "payments are complex",
    "solution": "a payments platform",
    "why_now": "digital payments growing",
    "est_tam": "30B",
}
ENTERPRISE_THIN_REVIEW = {
    "product_reasoning": ["usable product"],
    "market_reasoning": ["growing market"],
}
PRE_SEED_THIN_SCOUT = {
    "name": "TinyCo",
    "sector": "devtools",
    "funding_stage": "pre-seed",
    "one_line": "AI tool for developers",
    "problem": "manual workflow is inefficient",
    "solution": "workflow automation dashboard",
    "why_now": "AI tailwind",
    "est_tam": "400M",
}
PRE_SEED_THIN_REVIEW = {
    "product_reasoning": ["usable"],
    "market_reasoning": ["steady growth"],
}


def test_issue2_thin_evidence_collapses_stage_ordering_BUG():
    """BUG: with symmetric thin evidence, a Series C $30B company scores at or below a
    pre-seed. The 'absent fact-derived evidence is excluded, not penalized' design lets
    both float on generic qualitative defaults.

    Post-fix expectation (2A maturity-gap + 1A/1B): the enterprise should not be dragged
    below the pre-seed purely by sparse extraction, and/or both should be visibly
    low-confidence + maturity-gapped so a human can tell them apart. Flip when fixed.
    """
    engine = DeterministicScoringEngine()
    ent = engine.score(ENTERPRISE_THIN_SCOUT, ENTERPRISE_THIN_REVIEW)
    pre = engine.score(PRE_SEED_THIN_SCOUT, PRE_SEED_THIN_REVIEW)

    gap = (ent["overall_score"] or 0) - (pre["overall_score"] or 0)
    # BUG: the enterprise lands BELOW the pre-seed (gap is negative / not meaningfully positive).
    assert gap < 0.5
    # Both headline scores sit in the same indistinct mid band.
    assert 4.0 <= ent["overall_score"] <= 6.5
    assert 4.0 <= pre["overall_score"] <= 6.5
