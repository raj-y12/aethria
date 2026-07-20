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
# - Criterion-evidence fix: _aggregate_policy_criteria used to recompute each dimension's
#   score from its policy criteria while folding in NO-evidence components at their neutral
#   5.0 placeholder — silently reintroducing the leak aggregate_dimension already excludes.
#   Missing components (and fully-missing criteria) are now excluded and weights
#   renormalized over evidenced signals, so a partially-evidenced dimension reads from real
#   evidence only. Effects:
#     * weak_thin → drivers move toward their evidenced signals (technical 3.90→2.56,
#       execution 3.85→3.36 as weak evidence is no longer cushioned by 5.0 placeholders;
#       market 5.10→5.20, product 5.90→6.29); overall 4.69→4.35.
#     * structured_signals → evidenced dimensions rise off the 5.0 floor (market 6.30→7.60,
#       execution 5.60→6.33); overall 5.95→6.96. Unscored dims unchanged.
#     * strong_saas / all_missing → unchanged.
# - Thin-evidence safety: calibration is now enabled by default and evidence eligibility
#   requires component `evidence` or `rule` metadata. This deliberately changes only
#   the fixtures that rely on inference without that metadata:
#     * strong_saas has grounded extraction evidence, so it remains scored, but its
#       display values are confidence-discounted (overall 7.26→6.63).
#     * weak_thin retains only its rule-supported Technical signal; its other
#       dimensions are unscored rather than inferred from sparse narrative.
#     * structured_signals carries no evidence/rule metadata, so every dimension is
#       unscored instead of publishing the supplied labels and values as fact.
GOLDEN = {
    "strong_saas": {
        "overall_score": 6.63,
        "dims": {"market": 6.83, "product": 7.79, "technical": 6.11, "execution": 5.80, "defensibility": 3.68},
    },
    "weak_thin": {
        "overall_score": 4.00,
        "dims": {"market": 5.00, "product": 5.00, "technical": 4.00, "execution": 5.00, "defensibility": 5.00},
    },
    "all_missing": {
        # Every dimension is a placeholder 5.0 but unscored=True; overall is None.
        "overall_score": None,
        "dims": {"market": 5.00, "product": 5.00, "technical": 5.00, "execution": 5.00, "defensibility": 5.00},
    },
    "structured_signals": {
        # Value-only / label-only reviewer signals without evidence or a rule are no
        # longer eligible to manufacture a display score.
        "overall_score": None,
        "dims": {"market": 5.00, "product": 5.00, "technical": 5.00, "execution": 5.00, "defensibility": 5.00},
    },
}

# Dimensions expected to be flagged `unscored` (no evidence) per fixture.
UNSCORED_DIMS = {
    "strong_saas": set(),
    "weak_thin": {"market", "product", "execution", "defensibility"},
    "all_missing": {"market", "product", "technical", "execution", "defensibility"},
    "structured_signals": {"market", "product", "technical", "execution", "defensibility"},
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


def test_p31_team_evidence_anchors_match_normalizer_vocabulary():
    """P3.1: the behaviorally-anchored labels offered to the reviewer for
    execution.team_execution must be exactly the labels the deterministic normalizer
    recognizes — otherwise the LLM would be told to use labels that then abstain."""
    from reviewer.base import _evidence_anchors_block

    block = _evidence_anchors_block()
    for label in ("weak", "decent", "credible_team", "strong", "elite"):
        assert label in block, f"anchor block missing label {label}"
        assert not NL.is_unrecognized(NL.normalize_team_execution(label)), (
            f"anchor label {label} is not a recognized normalizer label"
        )


def test_p33_evidence_anchors_match_normalizer_vocabulary():
    """P3.3: every label offered to the reviewer in the component evidence-anchor catalog
    must be a label the matching deterministic normalizer recognizes — otherwise the LLM
    would be told to use labels that then abstain. Guards the rolled-out anchors the same
    way P3.1 guarded team_execution."""
    from reviewer.base import COMPONENT_EVIDENCE_ANCHORS, QUALITATIVE_COMPONENTS, VALUE_COMPONENTS

    normalizers = {
        "execution.team_execution": NL.normalize_team_execution,
        "execution.traction": NL.normalize_traction,
        "execution.gtm_effectiveness": NL.normalize_gtm,
        "market.competition": NL.normalize_competition,
        "product.pain_alignment": NL.normalize_pain_alignment,
        "technical.complexity": NL.normalize_complexity,
        "technical.scalability": NL.normalize_scalability,
        "technical.data_advantage": NL.normalize_data_advantage,
        "defensibility.network_effects": NL.normalize_network_effects,
        "defensibility.switching_costs": NL.normalize_switching_costs,
        "defensibility.proprietary_data": NL.normalize_proprietary_data,
        "defensibility.barriers": NL.normalize_barriers,
    }
    # catalog must only contain components we can validate
    assert set(COMPONENT_EVIDENCE_ANCHORS) == set(normalizers)
    for comp_key, anchors in COMPONENT_EVIDENCE_ANCHORS.items():
        fn = normalizers[comp_key]
        for label, _cond in anchors:
            assert not NL.is_unrecognized(fn(label)), (
                f"{comp_key} anchor label {label!r} is not a recognized normalizer label"
            )
    # classification is a clean partition over the 25 components (no overlap)
    classified = set(COMPONENT_EVIDENCE_ANCHORS) | set(QUALITATIVE_COMPONENTS) | set(VALUE_COMPONENTS)
    assert len(classified) == len(COMPONENT_EVIDENCE_ANCHORS) + len(QUALITATIVE_COMPONENTS) + len(VALUE_COMPONENTS)
    assert len(classified) == 25, "all 25 components must be classified exactly once"


def test_p34_qualitative_components_are_flagged_in_engine_output():
    """P3.4 (data side): components with no objective anchor are stamped qualitative=True
    so the memo can tell a qualitative 8 from an evidence-backed 8. Fact-derived and
    value components must NOT carry the flag."""
    from config.scoring_config import (
        FACT_DERIVED_COMPONENTS,
        QUALITATIVE_COMPONENTS,
        VALUE_COMPONENTS,
    )

    out = DeterministicScoringEngine().score(*FIXTURES["strong_saas"])

    def comp(key):
        dim, _, name = key.partition(".")
        return out.get(dim, {}).get("components", {}).get(name)

    for key in QUALITATIVE_COMPONENTS:
        c = comp(key)
        assert isinstance(c, dict), f"{key} missing from engine output"
        assert c.get("qualitative") is True, f"{key} should be flagged qualitative"
    for key in list(FACT_DERIVED_COMPONENTS) + list(VALUE_COMPONENTS):
        c = comp(key)
        assert isinstance(c, dict), f"{key} missing from engine output"
        assert "qualitative" not in c, f"{key} must not be flagged qualitative"


def test_p63_identical_tam_scores_by_sector_benchmark():
    """P6.3: the same TAM must yield sector-appropriate Market.tam scores. $1B is a
    'small' market for fintech (capital-heavy) but mid-band for dev-tools."""
    engine = DeterministicScoringEngine()
    base_review = {"competition_analysis": ["Some competitors."]}

    fintech = engine.score(
        {"name": "F", "sector": "Fintech payments", "est_tam": "$1B", "one_line": "x", "solution": "y", "problem": "z"},
        base_review,
    )
    devtools = engine.score(
        {"name": "D", "sector": "Developer infrastructure", "est_tam": "$1B", "one_line": "x", "solution": "y", "problem": "z"},
        base_review,
    )
    fin_tam = fintech["market"]["components"]["tam"]["score"]
    dev_tam = devtools["market"]["components"]["tam"]["score"]
    assert dev_tam > fin_tam, "an identical $1B TAM must score higher in dev-tools than fintech"
    assert "Fintech" in fintech["sector_tam_benchmark"]
    assert "Dev-tools" in devtools["sector_tam_benchmark"]


def test_p61_stage_cohort_is_captured_and_labelled():
    """P6.1: the engine surfaces the stage cohort (display only; scores stay absolute)."""
    engine = DeterministicScoringEngine()
    base = {"name": "S", "sector": "SaaS", "one_line": "x", "solution": "y", "problem": "z"}

    seed = engine.score({**base, "funding_stage": "Seed"}, {})
    assert seed["stage_cohort"] == "seed" and seed["stage_cohort_label"] == "Seed"

    late = engine.score({**base, "funding_stage": "Series B"}, {})
    assert late["stage_cohort"] == "series_b_plus" and late["stage_cohort_label"] == "Series B+"

    unknown = engine.score(base, {})
    assert unknown["stage_cohort"] == "unknown"

    # cohort must NOT change the absolute scores (decision log: absolute anchors)
    assert seed["market"]["score"] == late["market"]["score"]


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


def test_FIXED_stage_word_does_not_set_traction_score_P62():
    """Audit P6.2, now FIXED: funding/lifecycle stage words ("seed", "pre_revenue",
    "growth") used to be synonyms that hard-mapped into traction labels
    (seed→early_adoption, growth→scaling), so a stage word silently set the traction
    score. They are no longer synonyms — a stage word now abstains (UNRECOGNIZED_LABEL),
    so traction is driven only by actual traction evidence.
    """
    for stage_word in ("seed", "pre_revenue", "pre-revenue", "growth"):
        assert NL.is_unrecognized(NL.normalize_traction(stage_word)), (
            f"stage word {stage_word!r} must not map to a traction label"
        )
    # genuine traction labels still score normally
    assert NL.normalize_traction("scaling") == 8.0
    assert NL.normalize_traction("early_adoption") == 5.0

    # end to end: a stage word in structured_signals traction is excluded, not scored
    scout = {"one_line": "AI copilot", "solution": "model automation", "problem": "manual work"}
    review = {"structured_signals": {"execution": {"traction": {"label": "seed", "confidence": 0.9}}}}
    comp = DeterministicScoringEngine().score(scout, review)["execution"]["components"]["traction"]
    assert comp.get("unrecognized_label") is True
    assert comp.get("value") is None and comp.get("label") is None


def test_FIXED_unknown_market_is_unscored_not_outscoring_known_small_C2():
    """Audit C2 (the headline of the comparability problem), now FIXED by P3.2.

    A company with NO market data used to score 5.78 on Market — HIGHER than a company
    with a verified-but-small market (5.48). A small-market value without evidence or
    a rule is also unscored now: neither case may publish an inferred Market score.
    """
    engine = DeterministicScoringEngine()
    unknown = engine.score(*FIXTURES["all_missing"])["market"]
    known_small = engine.score(*FIXTURES["weak_thin"])["market"]
    assert unknown.get("unscored") is True, "no-evidence Market must be unscored"
    assert known_small.get("unscored") is True, "ungrounded small-market value is unscored"
