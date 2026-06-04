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
# - P3.2: extraction no longer fabricates labels when a component's source text is
#   empty; aggregation renormalizes over evidenced components and flags a fully
#   no-evidence dimension `unscored` (placeholder score kept, excluded from the
#   overall). Rolled out across ALL dimensions. Effects:
#     * all_missing → every dimension unscored, overall = None (a no-data company is
#       honestly unscored, not a fabricated mid score).
#     * weak_thin → scores rose (4.34→4.69) because fabricated LOW labels that used to
#       drag the score are now excluded (the old system under-scored sparse companies).
#     * structured_signals → product/technical/defensibility unscored (the fixture only
#       supplied market + execution signals).
#     * strong_saas → unchanged (every dimension has evidence).
GOLDEN = {
    "strong_saas": {
        "overall_score": 7.26,
        "dims": {"market": 7.88, "product": 8.25, "technical": 6.15, "execution": 6.75, "defensibility": 2.35},
    },
    "weak_thin": {
        "overall_score": 4.69,
        "dims": {"market": 5.10, "product": 5.90, "technical": 3.90, "execution": 3.85, "defensibility": 4.40},
    },
    "all_missing": {
        # Every dimension is a placeholder 5.0 but unscored=True; overall is None.
        "overall_score": None,
        "dims": {"market": 5.00, "product": 5.00, "technical": 5.00, "execution": 5.00, "defensibility": 5.00},
    },
    "structured_signals": {
        "overall_score": 5.95,
        "dims": {"market": 6.30, "product": 5.00, "technical": 5.00, "execution": 5.60, "defensibility": 5.00},
    },
}

# Dimensions expected to be flagged `unscored` (no evidence) per fixture.
UNSCORED_DIMS = {
    "strong_saas": set(),
    "weak_thin": set(),
    "all_missing": {"market", "product", "technical", "execution", "defensibility"},
    "structured_signals": {"product", "technical", "defensibility"},
}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_engine_overall_score_golden(name):
    scout, review = FIXTURES[name]
    result = DeterministicScoringEngine().score(scout, review)
    expected = GOLDEN[name]["overall_score"]
    if expected is None:
        assert result["overall_score"] is None, f"{name}: expected unscored overall (None)"
    else:
        assert result["overall_score"] == pytest.approx(expected, abs=ABS), (
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
    if not core:
        # Every core driver is unscored → the overall is undefined (None).
        assert result["overall_score"] is None
    else:
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


def test_FIXED_off_vocabulary_label_is_unrecognized_not_five_C2():
    """Audit §5, now FIXED: a label outside the controlled vocabulary used to silently
    map to a neutral 5.0 and count as evidence. The normalizer now returns the
    `UNRECOGNIZED_LABEL` sentinel, and the engine excludes such a component from
    aggregation (treated as no-evidence) instead of scoring it 5.0.
    """
    assert NL.is_unrecognized(NL.normalize_team_execution("promising"))  # valid: weak/decent/credible_team/strong/elite
    assert NL.is_unrecognized(NL.normalize_differentiation("promising"))  # valid: none/slight/clear/strong
    # a recognized label still scores normally
    assert NL.normalize_team_execution("elite") == 10.0

    # end to end: an off-vocab label is excluded, not scored 5.0
    scout = {"one_line": "AI copilot", "solution": "model automation", "problem": "manual work"}
    review = {"structured_signals": {"product": {"differentiation": {"label": "promising", "confidence": 0.9}}}}
    comp = DeterministicScoringEngine().score(scout, review)["product"]["components"]["differentiation"]
    assert comp.get("unrecognized_label") is True
    assert comp.get("value") is None and comp.get("label") is None


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
