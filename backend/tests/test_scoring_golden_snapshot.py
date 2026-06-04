"""Golden / characterization snapshot of the deterministic scoring engine.

Phase 0 guardrail (P0.1) for the scoring remediation tracked in
``docs/scoring-remediation-checklist.md``.

WHY THIS EXISTS
---------------
The deterministic engine (``DeterministicScoringEngine.score``) is pure: the same
``(scout, review)`` inputs always produce the same scores, with no LLM call. The
existing scoring tests only assert *shape and bounds* (a score is between 0 and 10),
so a refactor could silently change an actual score and nothing would catch it.

These tests pin the EXACT current output for a set of representative fixtures, so any
later change that moves a number is surfaced as a diff and must be made consciously.

IMPORTANT — these values intentionally encode CURRENT behavior, *including known
issues* documented in ``docs/scoring-assessment-audit.md`` (e.g. C2: missing data
defaults to a mid score). Tests named ``test_KNOWN_ISSUE_*`` lock buggy-but-current
behavior on purpose; when the corresponding remediation task lands, that test will
fail and must be updated in the same change, which is the proof the fix took effect.

When a remediation task changes scoring, update the GOLDEN values below in the same
PR and reference the task ID (e.g. P1.2) in the commit.
"""

import pytest

from services.scoring.scoring_engine import DeterministicScoringEngine
from services.scoring import normalization_layer as NL

# Loose enough to ignore float noise, tight enough to catch a real anchor change.
ABS = 0.01

# --- Representative engine fixtures -----------------------------------------------
# (scout, review) inputs. Kept inline to match the house test style.
FIXTURES = {
    "strong_saas": (
        {
            "one_line": "AI compliance copilot for healthcare",
            "problem": "Manual compliance is costly.",
            "solution": "Model-driven automation with proprietary compliance datasets.",
            "target_users": "Mid-market healthcare",
            "why_now": "Regulatory burden rising 45%.",
            "est_tam": "$12B",
        },
        {
            "competition_analysis": ["Crowded incumbent market."],
            "team_analysis": ["Ex-Epic and ex-Palantir operators."],
            "business_model_analysis": ["Early revenue, repeatable outbound."],
            "market_reasoning": ["Rapid demand growth."],
            "product_reasoning": ["Sticky daily usage."],
            "technical_reasoning": ["Scalable robust infra."],
            "defensibility_reasoning": ["Strong switching costs and data moat."],
            "market_confidence": "high",
            "product_confidence": "medium",
            "technical_confidence": "medium",
            "execution_confidence": "medium",
            "defensibility_confidence": "medium",
        },
    ),
    "weak_thin": (
        {
            "one_line": "A social app",
            "problem": "People are bored.",
            "solution": "Another feed.",
            "est_tam": "$200M",
        },
        {
            "market_confidence": "low",
            "product_confidence": "low",
            "technical_confidence": "low",
            "execution_confidence": "low",
            "defensibility_confidence": "low",
        },
    ),
    "all_missing": ({}, {}),
    "structured_signals": (
        {},
        {
            "structured_signals": {
                "market": {
                    "tam": {"value": "$3B", "confidence": 0.8},
                    "growth_rate": {"value": "24%", "confidence": 0.8},
                    "urgency": {"label": "high", "confidence": 0.7},
                    "timing": {"label": "favorable", "confidence": 0.7},
                    "competition": {"label": "moderate", "confidence": 0.6},
                },
                "execution": {
                    "traction": {"label": "early_revenue", "confidence": 0.7},
                    "team_execution": {"label": "credible_team", "confidence": 0.7},
                },
            }
        },
    ),
}

# Captured from the current engine (DEBUG_SCORING off). Update consciously.
#
# overall_score updated by P2.1 (defensibility excluded from the canonical overall;
# overall is now the 4-dim mean of market/product/technical/execution, identical to
# utils.scoring.compute_overall_score). Dimension scores are unchanged. The previous
# 5-dim-equal-weight overalls (e.g. strong_saas 6.28) were dragged down by
# defensibility's systematic low default (~2.35).
GOLDEN = {
    "strong_saas": {
        "overall_score": 7.26,
        "dims": {"market": 7.88, "product": 8.25, "technical": 6.15, "execution": 6.75, "defensibility": 2.35},
    },
    "weak_thin": {
        "overall_score": 4.43,
        "dims": {"market": 5.48, "product": 5.60, "technical": 2.80, "execution": 3.85, "defensibility": 2.35},
    },
    "all_missing": {
        "overall_score": 3.96,
        "dims": {"market": 5.78, "product": 3.85, "technical": 2.80, "execution": 3.40, "defensibility": 2.35},
    },
    "structured_signals": {
        "overall_score": 4.31,
        "dims": {"market": 6.30, "product": 3.85, "technical": 2.80, "execution": 4.30, "defensibility": 2.35},
    },
}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_engine_overall_score_golden(name):
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    assert result["overall_score"] == pytest.approx(GOLDEN[name]["overall_score"], abs=ABS), (
        f"{name}: overall_score drifted from golden snapshot. "
        f"If intentional, update GOLDEN and reference the remediation task."
    )


@pytest.mark.parametrize("name", list(FIXTURES))
def test_engine_dimension_scores_golden(name):
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    for dim, expected in GOLDEN[name]["dims"].items():
        assert result[dim]["score"] == pytest.approx(expected, abs=ABS), (
            f"{name}.{dim}: dimension score drifted from golden snapshot."
        )


@pytest.mark.parametrize("name", list(FIXTURES))
def test_overall_is_four_dimension_mean_excluding_defensibility(name):
    """Canonical-score invariant (P2.1/P2.3): the overall is the mean of the four
    core driver dimensions and excludes defensibility. The displayed overall must be
    reproducible from the displayed dimensions (audit B4)."""
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    core = [result[d]["score"] for d in ("market", "product", "technical", "execution")]
    expected = sum(core) / len(core)
    assert result["overall_score"] == pytest.approx(expected, abs=ABS)


# --- Pure normalizer anchor table -------------------------------------------------
# Documents the exact 1-10 anchors, including the missing/off-vocabulary defaults
# that the remediation will change (audit C2 + Layer 3).
NORMALIZER_ANCHORS = [
    (NL.normalize_tam, "$12B", 10.0),
    (NL.normalize_tam, "$3B", 8.5),
    (NL.normalize_tam, "$250M", 4.0),
    (NL.normalize_growth, "40%", 10.0),
    (NL.normalize_traction, "scaling", 8.0),
    (NL.normalize_team_execution, "elite", 10.0),
    (NL.normalize_network_effects, "strong", 10.0),
]


@pytest.mark.parametrize("fn,arg,expected", NORMALIZER_ANCHORS)
def test_normalizer_anchor_golden(fn, arg, expected):
    assert fn(arg) == pytest.approx(expected, abs=ABS)


# --- KNOWN-ISSUE locks (will flip when remediation lands) -------------------------

def test_KNOWN_ISSUE_missing_defaults_to_five_C2():
    """Audit C2 / Layer 3: absent input silently becomes DEFAULT_SCORE=5.0.

    Locks the CURRENT (incorrect) behavior. Task P1.2 (abstain instead of 5.0) must
    consciously flip this; when it does, update this test to assert the new
    `unscored` behavior.
    """
    assert NL.normalize_tam(None) == 5.0
    assert NL.normalize_growth(None) == 5.0
    assert NL.normalize_traction(None) == 5.0
    assert NL.normalize_network_effects(None) == 5.0


def test_KNOWN_ISSUE_off_vocabulary_label_defaults_to_five_C2():
    """Audit §5: a label outside the controlled vocabulary silently maps to 5.0,
    so a differentiated company can read identically to a no-data one. Flips with P1.2.
    """
    assert NL.normalize_team_execution("promising") == 5.0  # valid: weak/decent/credible_team/strong/elite
    assert NL.normalize_differentiation("promising") == 5.0  # valid: none/slight/clear/strong


def test_KNOWN_ISSUE_unknown_market_outscores_known_small_C2():
    """Audit C2 (the headline of the comparability problem): a company with NO market
    data scores HIGHER on Market than a company with a verified-but-small market.

    'all_missing' Market (5.78) > 'weak_thin' Market (5.48), and at the raw anchor
    level missing TAM (5.0) > verified $250M TAM (4.0). Locks current behavior; P1.2
    must invert it (unknown should not beat a known-small, scored company).
    """
    engine = DeterministicScoringEngine()
    unknown = engine.score(*FIXTURES["all_missing"])["market"]["score"]
    known_small = engine.score(*FIXTURES["weak_thin"])["market"]["score"]
    assert unknown > known_small, "Expected current (buggy) ordering: unknown > known-small"
    assert NL.normalize_tam(None) > NL.normalize_tam("$250M")
