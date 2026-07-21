from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites
from evaluation_v2.governed_scoring import validate_governed_scoring_trace
from reviewer.engine import ReviewerEngine
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.reviewer_resolution import apply_resolution_to_primary
from utils.adapters import reviewer_output_to_review_info


def _compiled_policy():
    compiled = compile_policy_from_fund_config(
        {
            "scoringWeights": [
                {"key": "market", "weight": 70},
                {"key": "execution", "weight": 30},
            ],
        },
        require_publish_ready=True,
    )
    compiled["policy_version_id"] = "policy-live"
    return compiled


def _partner_rules():
    path = (
        Path(__file__).resolve().parents[3]
        / "resources/config/partner_rules/v3.json"
    )
    rules = json.loads(path.read_text())
    rules["version"] = "rules-v3-exact"
    return rules


def _prerequisites(user_id="user-a"):
    compiled = _compiled_policy()
    rules = _partner_rules()
    thesis = {
        "thesis_id": "thesis-a",
        "version_id": "thesis-live",
        "version_number": 3,
        "raw_text": "Exact mandate",
        "parsed_json": {"sectors": ["Infrastructure"]},
        "embedding": [],
        "embedding_model": "none",
        "alignment_mode": "rule_based",
    }
    return EvaluationPrerequisites(
        user_id=user_id,
        thesis_context=thesis,
        thesis_version_id="thesis-live",
        compiled_scoring_policy=compiled,
        partner_rules=rules,
        fund_config=compiled["decision_inputs"],
        policy=evaluation_policy_from_compiled(compiled, partner_rules=rules),
    )


class _ReviewerPersona:
    def __init__(self, *_args, **kwargs):
        self.fund_thesis = None
        self._use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback"
        )
        self._structured_scoring_enabled = kwargs.get("structured_scoring_enabled")

    def set_fund_thesis(self, thesis):
        self.fund_thesis = thesis

    def close(self):
        pass


def test_governed_reviewer_consumes_exact_compiled_policy_without_reload(monkeypatch):
    import reviewer.engine as reviewer_module

    prerequisites = _prerequisites()
    monkeypatch.setattr(
        reviewer_module,
        "load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("governed reviewer must not reload settings")
        ),
    )
    monkeypatch.setattr(
        reviewer_module,
        "load_active_policy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("governed reviewer must not reload policy")
        ),
    )
    monkeypatch.setattr(reviewer_module, "DefaultReviewer", _ReviewerPersona)
    monkeypatch.setattr(reviewer_module, "SkepticalReviewer", _ReviewerPersona)
    monkeypatch.setattr(reviewer_module, "OpportunistReviewer", _ReviewerPersona)

    reviewer = reviewer_module.ReviewerEngine(
        api_key="",
        storage=SimpleNamespace(_user_id="user-a"),
        tenant_user_id="user-a",
        active_thesis=prerequisites.thesis_context,
        evaluation_prerequisites=prerequisites,
    )

    assert reviewer.active_thesis is prerequisites.thesis_context
    assert reviewer.structured_scoring_engine.policy is prerequisites.compiled_scoring_policy
    assert reviewer.structured_scoring_engine.dimension_weights["market"] == 70.0
    assert reviewer.structured_scoring_engine.dimension_weights["execution"] == 30.0
    assert reviewer.use_resource_fund_thesis_fallback is False
    assert all(
        persona._use_resource_fund_thesis_fallback is False
        for persona in (
            reviewer.reviewer,
            reviewer.skeptical_reviewer,
            reviewer.opportunist_reviewer,
        )
    )


def test_governed_reviewer_ignores_disabled_structured_scoring_environment(monkeypatch):
    import reviewer.engine as reviewer_module

    prerequisites = _prerequisites()
    monkeypatch.setenv("USE_STRUCTURED_SCORING", "false")
    monkeypatch.setattr(reviewer_module, "DefaultReviewer", _ReviewerPersona)
    monkeypatch.setattr(reviewer_module, "SkepticalReviewer", _ReviewerPersona)
    monkeypatch.setattr(reviewer_module, "OpportunistReviewer", _ReviewerPersona)

    reviewer = reviewer_module.ReviewerEngine(
        api_key="",
        storage=SimpleNamespace(_user_id="user-a"),
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    assert reviewer.use_structured_scoring is True
    assert reviewer.structured_scoring_engine is not None
    assert all(
        persona._structured_scoring_enabled is True
        for persona in (
            reviewer.reviewer,
            reviewer.skeptical_reviewer,
            reviewer.opportunist_reviewer,
        )
    )


def test_governed_reviewer_fails_closed_when_scorer_is_unavailable():
    reviewer = ReviewerEngine.__new__(ReviewerEngine)
    reviewer.evaluation_prerequisites = _prerequisites()
    reviewer.structured_scoring_engine = None

    with pytest.raises(RuntimeError, match="governed structured scoring"):
        reviewer._apply_structured_scoring({}, {"market_score": 9})


def test_governed_partner_consumes_exact_rules_and_fund_config_without_reload(monkeypatch):
    import partner.decision as partner_module

    prerequisites = _prerequisites()
    monkeypatch.setattr(
        partner_module,
        "_load_partner_rules",
        lambda: (_ for _ in ()).throw(
            AssertionError("governed partner must not reload rules")
        ),
    )
    monkeypatch.setattr(
        partner_module,
        "load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("governed partner must not reload settings")
        ),
    )

    partner = partner_module.PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    assert partner._rules is prerequisites.partner_rules
    assert partner._fund_config is prerequisites.fund_config
    assert partner.evaluation_policy is prerequisites.policy
    assert partner.evaluation_policy.policy_version_id == "policy-live"
    assert partner.evaluation_policy.partner_rules_version == "rules-v3-exact"
    assert partner.use_resource_fund_thesis_fallback is False


def _exact_trace(score: float) -> dict:
    return {
        **{
            dimension: {
                "score": score,
                "confidence": 0.9,
                "components": {"evidence": {"value": "verified"}},
                "unscored": False,
            }
            for dimension in (
                "market",
                "product",
                "technical",
                "execution",
                "defensibility",
            )
        },
        "overall_score": score,
        "overall_confidence": 0.9,
        "policy_version_id": "policy-live",
        "policy_hash": _compiled_policy()["policy_hash"],
    }


def _persona_trace(
    score: float,
    *,
    missing_dimension: str | None = None,
    policy_version_id: str = "policy-live",
) -> dict:
    trace = _exact_trace(score)
    trace["policy_version_id"] = policy_version_id
    if missing_dimension is not None:
        trace[missing_dimension] = {
            "score": None,
            "confidence": 0.0,
            "components": {},
            "unscored": True,
            "missing_reasons": ["no_grounded_components"],
        }
        trace["overall_score"] = None
    return trace


def _governed_review(score: float) -> dict:
    class Scorer:
        def score(self, _scout, _review):
            return _exact_trace(score)

    reviewer = ReviewerEngine.__new__(ReviewerEngine)
    reviewer.evaluation_prerequisites = _prerequisites()
    reviewer.structured_scoring_engine = Scorer()
    raw = {
        "market_score": 1,
        "product_score": 1,
        "technical_score": 1,
        "execution_score": 1,
        "defensibility_score": 1,
        "overall_summary": "Governed precision handoff",
        "key_risks": [],
        "verdict": "MEDIUM",
        "team_analysis": ["Experienced operating team"],
        "business_model_analysis": ["Clear enterprise subscription model"],
    }
    persona_results = []
    for reviewer_type in (
        "DefaultReviewer",
        "SkepticalReviewer",
        "OpportunistReviewer",
    ):
        result = reviewer._apply_structured_scoring({}, raw)
        result["reviewer_type"] = reviewer_type
        persona_results.append(result)
    primary = dict(persona_results[0])
    reviewer._blend_numeric_scores_into_primary(primary, persona_results)
    apply_resolution_to_primary(primary, persona_results)
    reviewer._refresh_derived_after_dimension_changes(primary, persona_results)
    reviewer._derive_verdict_from_scores(primary)
    review_info = reviewer_output_to_review_info(primary)
    review_info.reviews = reviewer._build_single_reviews(persona_results)
    return review_info.model_dump(mode="json")


def _governed_review_from_persona_traces(traces: list[dict]) -> dict:
    class Scorer:
        def __init__(self):
            self._traces = iter(traces)

        def score(self, _scout, _review):
            return next(self._traces)

    reviewer = ReviewerEngine.__new__(ReviewerEngine)
    reviewer.evaluation_prerequisites = _prerequisites()
    reviewer.structured_scoring_engine = Scorer()
    raw = {
        "overall_summary": "Governed consensus handoff",
        "key_risks": [],
        "verdict": "MEDIUM",
        "team_analysis": ["Experienced operating team"],
        "business_model_analysis": ["Clear enterprise subscription model"],
    }
    persona_results = []
    for reviewer_type in (
        "DefaultReviewer",
        "SkepticalReviewer",
        "OpportunistReviewer",
    ):
        result = reviewer._apply_structured_scoring({}, raw)
        result["reviewer_type"] = reviewer_type
        persona_results.append(result)
    primary = dict(persona_results[0])
    reviewer._blend_numeric_scores_into_primary(primary, persona_results)
    notes, summary = apply_resolution_to_primary(primary, persona_results)
    primary["resolution_notes"] = notes
    primary["disagreement_summary"] = summary
    reviewer._refresh_derived_after_dimension_changes(primary, persona_results)
    reviewer._derive_verdict_from_scores(primary)
    review_info = reviewer_output_to_review_info(primary)
    review_info.reviews = reviewer._build_single_reviews(persona_results)
    return review_info.model_dump(mode="json")


def _governed_partner():
    from partner.decision import PartnerDecisionEngine

    return PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
        evaluation_prerequisites=_prerequisites(),
    )


def _decision_scout() -> dict:
    return {
        "name": "PrecisionCo",
        "one_line": "Boundary precision fixture",
        "sector": "Infrastructure",
        "funding_stage": "Seed",
        "confidence": 0.9,
    }


@pytest.mark.parametrize(
    "trace",
    [
        None,
        {},
        {**_exact_trace(9), "policy_version_id": "wrong-version"},
        {**_exact_trace(9), "policy_hash": "wrong-hash"},
        {
            **_exact_trace(9),
            "execution": {"score": 9, "confidence": 0.9, "unscored": True},
        },
    ],
    ids=["absent", "malformed", "wrong-version", "wrong-hash", "incomplete"],
)
def test_governed_partner_rejects_non_exact_structured_trace(trace):
    review = _governed_review(9)
    review["structured_scoring"] = trace

    with pytest.raises(RuntimeError, match="structured scoring trace"):
        _governed_partner().decide(_decision_scout(), review)


def test_governed_partner_accepts_complete_exact_structured_trace():
    decision = _governed_partner().decide(_decision_scout(), _governed_review(9))

    assert decision["recommendation"] == "INVEST"


def test_governed_consensus_trace_is_authoritative_after_persona_resolution():
    review = _governed_review_from_persona_traces(
        [_persona_trace(9), _persona_trace(5), _persona_trace(5)]
    )

    # Conservative resolution is 55% of the mean plus 45% of the minimum.
    expected = pytest.approx(5.7333333333)
    assert review["market_score"] == expected
    assert review["overall_score"] == expected
    assert review["structured_scoring"]["market"]["score"] == expected
    assert review["structured_scoring"]["overall_score"] == expected
    assert review["structured_scoring"]["trace_kind"] == "resolved_consensus"
    assert len(review["structured_scoring"]["input_traces"]) == 3
    assert review["structured_scoring"]["resolution_strategy"] == {
        "version": "reviewer-consensus-v1",
        "material_spread": 2.0,
        "conservative_min_weight": 0.45,
        "missingness": "union",
    }
    resolution = review["structured_scoring"]["market"]["components"][
        "persona_resolution"
    ]
    assert resolution == {
        "strategy": "conservative_mean_floor",
        "scores": [9.0, 5.0, 5.0],
        "spread": 4.0,
    }
    assert {
        item["trace"]["policy_version_id"]
        for item in review["structured_scoring"]["input_traces"]
    } == {"policy-live"}

    serialized = json.loads(json.dumps(review))
    decision = _governed_partner().decide(_decision_scout(), serialized)
    assert decision["recommendation"] == "PASS"


def test_governed_consensus_unions_missingness_across_personas_and_partner_holds():
    review = _governed_review_from_persona_traces(
        [
            _persona_trace(9),
            _persona_trace(9, missing_dimension="defensibility"),
            _persona_trace(9),
        ]
    )

    detail = review["structured_scoring"]["defensibility"]
    assert detail["score"] is None
    assert detail["unscored"] is True
    assert detail["missing_reasons"] == ["persona_unscored:defensibility"]
    assert review["defensibility_score"] is None

    decision = _governed_partner().decide(_decision_scout(), review)
    assert decision["recommendation"] != "INVEST"
    assert decision["human_review_required"] is True
    assert "insufficient" in decision["decision_rationale"].lower()


def test_governed_persona_policy_identity_mismatch_fails_before_consensus():
    with pytest.raises(RuntimeError, match="policy version"):
        _governed_review_from_persona_traces(
            [
                _persona_trace(8),
                _persona_trace(8, policy_version_id="stale-policy"),
                _persona_trace(8),
            ]
        )


def test_governed_partner_rejects_unresolved_persona_trace_even_when_identity_matches():
    review = _governed_review(9)
    review["structured_scoring"] = _persona_trace(9)

    with pytest.raises(RuntimeError, match="resolved consensus"):
        _governed_partner().decide(_decision_scout(), review)


def test_governed_trace_requires_every_compiled_dimension_including_defensibility():
    trace = _persona_trace(7)
    trace.pop("defensibility")

    with pytest.raises(RuntimeError, match="incomplete for defensibility"):
        validate_governed_scoring_trace(trace, _prerequisites())


def test_governed_trace_accepts_explicit_unscored_dimension_without_numeric_default():
    trace = _persona_trace(7, missing_dimension="defensibility")

    validated = validate_governed_scoring_trace(trace, _prerequisites())

    assert validated["defensibility"]["score"] is None
    assert validated["defensibility"]["missing_reasons"] == [
        "no_grounded_components"
    ]


@pytest.mark.parametrize(
    "detail",
    [
        {
            "score": 5,
            "confidence": 0,
            "components": {},
            "unscored": True,
            "missing_reasons": ["no_grounded_components"],
        },
        {
            "score": None,
            "confidence": 0,
            "components": {},
            "unscored": False,
            "missing_reasons": ["no_grounded_components"],
        },
        {
            "score": None,
            "confidence": 0,
            "components": {},
            "unscored": True,
            "missing_reasons": [],
        },
    ],
    ids=["numeric-unscored", "null-scored", "missing-reason-absent"],
)
def test_governed_trace_rejects_contradictory_missingness(detail):
    trace = _persona_trace(7)
    trace["defensibility"] = detail

    with pytest.raises(RuntimeError, match="defensibility"):
        validate_governed_scoring_trace(trace, _prerequisites())


def test_governed_trace_rejects_unknown_dimension_and_supports_future_compiled_dimension():
    prerequisites = _prerequisites()
    trace = _persona_trace(7)
    trace["impact"] = dict(trace["market"])
    with pytest.raises(RuntimeError, match="unknown scoring dimensions"):
        validate_governed_scoring_trace(trace, prerequisites)

    prerequisites.compiled_scoring_policy["dimensions"]["impact"] = {
        "id": "impact",
        "weight": 10,
        "criteria": [],
    }
    validated = validate_governed_scoring_trace(trace, prerequisites)
    assert validated["impact"]["score"] == 7


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (5.99, "PASS"),
        (6.0, "MONITOR"),
        (6.01, "MONITOR"),
        (7.99, "MONITOR"),
        (8.0, "INVEST"),
        (8.01, "INVEST"),
    ],
)
def test_governed_reviewer_persistence_partner_handoff_preserves_boundary_precision(
    score, expected
):
    review = _governed_review(score)

    assert review["market_score"] == score
    assert review["reviews"][0]["market_score"] == score
    assert review["structured_scoring"]["market"]["score"] == score
    decision = _governed_partner().decide(_decision_scout(), review)
    assert decision["recommendation"] == expected


def test_governed_partner_uses_versioned_policy_boundaries_over_display_bands():
    from partner.decision import PartnerDecisionEngine

    prerequisites = _prerequisites()
    engine = PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    # The exact fund configuration still supplies scoring weights and narrative
    # bands, but decisive state boundaries come only from the versioned policy.
    assert engine._canonical_recommendation(5.99) == "PASS"
    assert engine._canonical_recommendation(6.0) == "MONITOR"
    assert engine._canonical_recommendation(7.99) == "MONITOR"
    assert engine._canonical_recommendation(8.0) == "INVEST"


@pytest.mark.parametrize("engine", ["reviewer", "partner"])
def test_governed_engine_rejects_cross_tenant_context(monkeypatch, engine):
    prerequisites = _prerequisites("user-a")
    if engine == "reviewer":
        import reviewer.engine as reviewer_module

        monkeypatch.setattr(reviewer_module, "DefaultReviewer", _ReviewerPersona)
        monkeypatch.setattr(reviewer_module, "SkepticalReviewer", _ReviewerPersona)
        monkeypatch.setattr(reviewer_module, "OpportunistReviewer", _ReviewerPersona)
        constructor = lambda: reviewer_module.ReviewerEngine(
            api_key="",
            storage=SimpleNamespace(_user_id="user-b"),
            tenant_user_id="user-b",
            active_thesis=prerequisites.thesis_context,
            evaluation_prerequisites=prerequisites,
        )
    else:
        import partner.decision as partner_module

        constructor = lambda: partner_module.PartnerDecisionEngine(
            use_llm_fallback=False,
            tenant_user_id="user-b",
            evaluation_prerequisites=prerequisites,
        )

    with pytest.raises(RuntimeError, match="tenant mismatch"):
        constructor()


def test_execution_context_binding_is_immutable():
    prerequisites = _prerequisites()

    with pytest.raises(FrozenInstanceError):
        prerequisites.user_id = "user-b"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (5.49, "PASS"),
        (5.5, "MONITOR"),
        (5.51, "MONITOR"),
        (7.69, "MONITOR"),
        (7.7, "INVEST"),
        (7.71, "INVEST"),
    ],
)
def test_governed_partner_uses_same_explicit_decisive_boundaries_as_canonical_policy(
    score, expected
):
    from partner.decision import PartnerDecisionEngine

    compiled = _compiled_policy()
    rules = _partner_rules()
    rules["score_thresholds"]["min_avg_pass"] = 5.5
    rules["score_thresholds"]["min_avg_strong_yes"] = 7.7
    rules["verdict_rules"]["STRONG"]["min_avg_for_yes"] = 7.7
    rules["decision_safety"]["claim_confidence"][
        "score_cap_below_full_confidence"
    ] = 7.69
    rules["decision_safety"]["freshness"]["stale_score_cap"] = 7.69
    rules["decision_safety"]["source_quality"][
        "score_cap_below_full_quality"
    ] = 7.69
    policy = evaluation_policy_from_compiled(compiled, partner_rules=rules)
    prerequisites = EvaluationPrerequisites(
        user_id="user-a",
        thesis_context={"version_id": "thesis-live"},
        thesis_version_id="thesis-live",
        compiled_scoring_policy=compiled,
        partner_rules=rules,
        fund_config={},
        policy=policy,
    )
    engine = PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    assert engine._canonical_recommendation(score) == expected
