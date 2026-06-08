"""Robust label-vocabulary handling (memo "outside the recognized vocabulary" fix).

The deterministic normalizer used to abstain — and the engine then wrote a raw
"Label 'X' is outside the recognized vocabulary; treated as no evidence." string straight
into the memo — for three avoidable reasons:

  1. separator mismatch: the LLM emits ``pre_product`` but the vocabulary key is
     ``pre-product`` (hyphen), so the same label never matched;
  2. a natural mid-tier word (``moderate``) for a vocabulary that has no explicit middle
     (differentiation = none/slight/clear/strong, ux = clunky/usable/smooth/exceptional);
  3. an honest ``unknown`` / ``n/a`` ("no information") being treated as a vocabulary
     error rather than as no evidence.

These tests pin the fix while preserving the audited C2/P6.2 invariants: a *genuinely*
off-vocabulary label (and stage words) must still abstain — only now with a clean,
user-facing diligence message and never the internal vocabulary diagnostic.
"""

import services.scoring.normalization_layer as NL
from services.scoring.scoring_engine import DeterministicScoringEngine


SCOUT = {"one_line": "AI copilot", "solution": "model automation", "problem": "manual work"}


def _component(review, dimension, component):
    return DeterministicScoringEngine().score(SCOUT, review)[dimension]["components"][component]


# ── separator canonicalization ────────────────────────────────────────────────────
def test_separator_variants_resolve_to_the_same_tier():
    assert NL.normalize_traction("pre_product") == NL.normalize_traction("pre-product") == 2.0
    assert NL.normalize_traction("early_adoption") == NL.normalize_traction("early adoption") == 5.0
    assert NL.normalize_switching_costs("very_high") == NL.normalize_switching_costs("very high") == 10.0
    assert not NL.is_unrecognized(NL.normalize_traction("pre_product"))


def test_pre_product_scores_end_to_end_instead_of_abstaining():
    comp = _component(
        {"structured_signals": {"execution": {"traction": {"label": "pre_product", "confidence": 0.7}}}},
        "execution",
        "traction",
    )
    assert comp["score"] == 2.0
    assert comp.get("unrecognized_label") is None


# ── generic mid-tier gradation ──────────────────────────────────────────────────────
def test_moderate_resolves_to_the_vocabulary_midpoint():
    # vocabularies WITHOUT an explicit middle term still resolve "moderate"
    assert not NL.is_unrecognized(NL.normalize_differentiation("moderate"))
    assert not NL.is_unrecognized(NL.normalize_ux("moderate"))
    d = NL.normalize_differentiation("moderate")  # none/slight/clear/strong -> 2/5/7/9
    assert 4.0 <= d <= 8.0
    # synonyms of "middle" behave the same
    assert NL.normalize_ux("medium") == NL.normalize_ux("moderate")


def test_explicit_vocabulary_tier_takes_precedence_over_gradation():
    # competition/network_effects DO enumerate "moderate" — the explicit score wins,
    # the generic midpoint fallback must not override it.
    assert NL.normalize_competition("moderate") == 7.0
    assert NL.normalize_network_effects("moderate") == 7.0


# ── honest "no information" labels ──────────────────────────────────────────────────
def test_is_no_information_classifies_abstention_tokens():
    for token in ("unknown", "Unknown", "n/a", "N/A", "tbd", "not disclosed", "no data", "unspecified"):
        assert NL.is_no_information(token), token
    for token in ("strong", "moderate", "pre-product", "elite"):
        assert not NL.is_no_information(token), token


def test_unknown_is_clean_no_evidence_not_a_vocabulary_error():
    for dimension, component in (("execution", "growth_velocity"), ("product", "ux")):
        comp = _component(
            {"structured_signals": {dimension: {component: {"label": "unknown", "confidence": 0.5}}}},
            dimension,
            component,
        )
        # honest "unknown" → no-evidence, NOT flagged as an off-vocabulary error
        assert comp.get("unrecognized_label") is None
        assert comp.get("value") is None and comp.get("label") is None
        assert "vocabulary" not in comp["reasoning"].lower()
        assert "no evidence" not in comp["reasoning"].lower()


def test_explicit_unknown_tier_still_scores():
    # brand/competition use "unknown" as a real tier — must keep scoring, not abstain.
    assert NL.normalize_brand("unknown") == 3.0
    assert NL.normalize_competition("unknown") == 5.0


# ── invariants: genuine off-vocabulary and stage words still abstain (audit C2/P6.2) ─
def test_genuine_off_vocabulary_still_abstains_but_with_clean_reasoning():
    assert NL.is_unrecognized(NL.normalize_differentiation("promising"))
    assert NL.is_unrecognized(NL.normalize_team_execution("promising"))
    comp = _component(
        {"structured_signals": {"product": {"differentiation": {"label": "promising", "confidence": 0.9}}}},
        "product",
        "differentiation",
    )
    assert comp.get("unrecognized_label") is True
    assert comp.get("value") is None and comp.get("label") is None
    # the user-facing reasoning must never carry the internal vocabulary diagnostic
    assert "vocabulary" not in comp["reasoning"].lower()
    assert "outside the recognized" not in comp["reasoning"].lower()


def test_stage_words_still_do_not_set_traction_score():
    for stage_word in ("seed", "pre_revenue", "pre-revenue", "growth"):
        assert NL.is_unrecognized(NL.normalize_traction(stage_word)), stage_word


def test_no_reasoning_field_ever_mentions_the_internal_vocabulary_diagnostic():
    # sweep a few off-vocabulary labels across components and assert the leak is gone
    cases = [
        ("product", "differentiation", "promising"),
        ("execution", "traction", "seed"),
        ("technical", "scalability", "questionable"),
    ]
    for dimension, component, label in cases:
        comp = _component(
            {"structured_signals": {dimension: {component: {"label": label, "confidence": 0.6}}}},
            dimension,
            component,
        )
        assert "recognized vocabulary" not in comp["reasoning"].lower()
