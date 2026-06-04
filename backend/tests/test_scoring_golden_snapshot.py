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
# History:
# - P2.1: defensibility excluded from the overall (now the 4-dim mean of the drivers,
#   identical to utils.scoring.compute_overall_score).
# - P3.2 (market): extraction no longer fabricates neutral labels when the source text
#   is empty; aggregation renormalizes over evidenced components and flags a fully
#   no-evidence dimension `unscored` (excluded from the overall). Effects: all_missing
#   Market is now unscored (placeholder 5.0 but excluded → overall 3.96→3.35);
#   weak_thin Market 5.48→5.1 (fabricated urgency/timing dropped; tam+competition kept).
#   Dimensions other than Market still use their own heuristics (follow-up).
GOLDEN = {
    "strong_saas": {
        "overall_score": 7.26,
        "dims": {"market": 7.88, "product": 8.25, "technical": 6.15, "execution": 6.75, "defensibility": 2.35},
    },
    "weak_thin": {
        "overall_score": 4.34,
        "dims": {"market": 5.10, "product": 5.60, "technical": 2.80, "execution": 3.85, "defensibility": 2.35},
    },
    "all_missing": {
        "overall_score": 3.35,
        # market is a placeholder 5.0 but unscored=True (excluded from the overall).
        "dims": {"market": 5.00, "product": 3.85, "technical": 2.80, "execution": 3.40, "defensibility": 2.35},
    },
    "structured_signals": {
        "overall_score": 4.31,
        "dims": {"market": 6.30, "product": 3.85, "technical": 2.80, "execution": 4.30, "defensibility": 2.35},
    },
}

# Dimensions expected to be flagged `unscored` (no evidence) per fixture.
UNSCORED_DIMS = {
    "strong_saas": set(),
    "weak_thin": set(),
    "all_missing": {"market"},
    "structured_signals": set(),
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
def test_overall_is_mean_of_evidenced_core_dimensions(name):
    """Canonical-score invariant (P2.1/P2.3/P3.2): the overall is the mean of the
    *evidenced* core driver dimensions — defensibility is excluded (modifier) and any
    `unscored` core dimension is excluded (no evidence). The displayed overall must be
    reproducible from the displayed driver dimensions (audit B4)."""
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    core = [
        result[d]["score"]
        for d in ("market", "product", "technical", "execution")
        if not result[d].get("unscored")
    ]
    expected = sum(core) / len(core)
    assert result["overall_score"] == pytest.approx(expected, abs=ABS)


@pytest.mark.parametrize("name", list(FIXTURES))
def test_unscored_dimensions_match_expected(name):
    """P3.2: dimensions with no evidence are flagged `unscored` (and excluded from the
    overall) rather than silently scored as a neutral 5.0."""
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    actual = {d for d in ("market", "product", "technical", "execution", "defensibility")
              if result[d].get("unscored")}
    assert actual == UNSCORED_DIMS[name]


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

def test_normalizer_missing_default_is_superseded_by_aggregation_abstain_C2():
    """The normalizer still returns DEFAULT_SCORE=5.0 for a None input, but this is now
    INERT for the missing case: P3.2 makes extraction emit a missing component (no
    value/label) and aggregation EXCLUDES non-evidenced components, so the 5.0 never
    enters a dimension score. Kept as documentation of the (now-superseded) default.
    """
    assert NL.normalize_tam(None) == 5.0
    assert NL.normalize_growth(None) == 5.0
    assert NL.normalize_traction(None) == 5.0
    assert NL.normalize_network_effects(None) == 5.0


def test_KNOWN_ISSUE_off_vocabulary_label_defaults_to_five_C2():
    """Audit §5 — STILL OPEN: a label outside the controlled vocabulary silently maps
    to 5.0. Unlike the missing case (fixed by P3.2), an off-vocab label IS concrete
    evidence, so aggregation includes it at 5.0. Remaining P3.2 follow-up: treat an
    unrecognized label as unscored rather than a neutral 5.0.
    """
    assert NL.normalize_team_execution("promising") == 5.0  # valid: weak/decent/credible_team/strong/elite
    assert NL.normalize_differentiation("promising") == 5.0  # valid: none/slight/clear/strong


def test_FIXED_unknown_market_is_unscored_not_outscoring_known_small_C2():
    """Audit C2 (the headline of the comparability problem), now FIXED by P3.2.

    A company with NO market data used to score 5.78 on Market — HIGHER than a company
    with a verified-but-small market (5.48). Now the no-data Market is flagged
    `unscored` and excluded from the overall, so it cannot outrank a real, evidenced
    market. The known-small company remains scored.
    """
    engine = DeterministicScoringEngine()
    unknown = engine.score(*FIXTURES["all_missing"])["market"]
    known_small = engine.score(*FIXTURES["weak_thin"])["market"]
    assert unknown.get("unscored") is True, "no-evidence Market must be unscored"
    assert known_small.get("unscored") is False, "known-small Market stays scored"
