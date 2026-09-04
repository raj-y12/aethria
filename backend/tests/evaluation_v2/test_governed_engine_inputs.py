from __future__ import annotations

from dataclasses import FrozenInstanceError
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites
from evaluation_v2.governed_scoring import validate_governed_scoring_trace
from partner.engine import PartnerEngine
from reviewer.engine import ReviewerEngine
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.reviewer_resolution import apply_resolution_to_primary
from utils.adapters import partner_output_to_partner_info, reviewer_output_to_review_info


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


def _prerequisites(user_id="user-a", *, embedding_backed: bool = False):
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
    if embedding_backed:
        thesis.update(
            {
                "embedding": [0.1, 0.2, 0.3],
                "embedding_model": "text-embedding-3-small",
                "alignment_mode": "embedding",
            }
        )
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


def test_governed_reviewer_does_not_construct_a_secondary_scorer(monkeypatch):
    import reviewer.engine as reviewer_module

    prerequisites = _prerequisites()
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

    assert reviewer.active_thesis == prerequisites.thesis_context
    assert reviewer.active_thesis is not prerequisites.thesis_context
    assert reviewer.use_structured_scoring is False
    assert reviewer.structured_scoring_engine is None
    assert reviewer.use_resource_fund_thesis_fallback is False
    assert all(
        persona._use_resource_fund_thesis_fallback is False
        for persona in (
            reviewer.reviewer,
            reviewer.skeptical_reviewer,
            reviewer.opportunist_reviewer,
        )
    )


def test_governed_reviewer_omits_model_score_fields_regardless_of_environment(monkeypatch):
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

    assert reviewer.use_structured_scoring is False
    assert reviewer.structured_scoring_engine is None
    assert all(
        persona._structured_scoring_enabled is False
        for persona in (
            reviewer.reviewer,
            reviewer.skeptical_reviewer,
            reviewer.opportunist_reviewer,
        )
    )


def test_governed_reviewer_has_no_secondary_scorer_to_fail_over_to():
    reviewer = ReviewerEngine.__new__(ReviewerEngine)
    reviewer.evaluation_prerequisites = _prerequisites()
    reviewer.structured_scoring_engine = None

    assert reviewer.structured_scoring_engine is None


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

    partner = partner_module.PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    assert partner._rules is prerequisites.partner_rules
    assert partner._fund_config == prerequisites.fund_config
    assert partner._fund_config is not prerequisites.fund_config
    assert partner.evaluation_policy == prerequisites.policy
    assert partner.evaluation_policy is not prerequisites.policy
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
        "user_id": "user-a",
        "policy_version_id": "policy-live",
        "policy_hash": _compiled_policy()["policy_hash"],
        "rubric_version": "tenant-rubric:policy-live",
        "scoring_runtime_version": _compiled_policy()["scoring_runtime"][
            "semantic_version"
        ],
        "scoring_runtime_hash": _compiled_policy()["scoring_runtime_hash"],
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


def test_partner_without_canonical_evaluation_never_decides_from_reviewer_scores():
    from partner.decision import PartnerDecisionEngine

    decision = PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="user-a",
    ).decide(
        _decision_scout(),
        {
            "market_score": 10,
            "product_score": 10,
            "technical_score": 10,
            "execution_score": 10,
            "overall_summary": "Legacy reviewer scorecard says this is strong.",
            "key_risks": [],
            "verdict": "STRONG",
        },
    )

    assert decision["recommendation"] == "MONITOR"
    assert "canonical evaluation is blocked" in decision["decision_rationale"].lower()


class _PersistingReviewerPersona:
    grounding_contracts: list[dict | None] = []

    def __init__(self, *_args, **kwargs):
        self._last_token_usage = 0
        self.fund_thesis = None
        contract = kwargs.get("structured_signal_grounding")
        self.grounding_contracts.append(
            dict(contract) if isinstance(contract, dict) else None
        )

    def set_fund_thesis(self, thesis):
        self.fund_thesis = thesis

    async def review(self, _scout):
        return {
            "overall_summary": "Governed production-path review",
            "key_risks": [],
            "verdict": "MEDIUM",
            "team_analysis": ["Experienced operating team"],
            "business_model_analysis": ["Clear enterprise subscription model"],
            "structured_signals": {},
            # Simulates the Reviewer base parser's normalized missing/malformed
            # LLM alignment result under an active thesis.
            "thesis_alignment_score": None,
        }

    def close(self):
        pass


async def _run_persisted_governed_review(
    tmp_path,
    monkeypatch,
    traces: list[dict],
    *,
    adversarial_resolution: bool = False,
    embedding_backed: bool = False,
):
    import meta.calibrator as calibrator_module
    import reviewer.engine as reviewer_module
    from models import ScoutInfo
    from utils.storage import Storage

    prerequisites = _prerequisites(embedding_backed=embedding_backed)
    prerequisites.thesis_context["parsed_json"].update(
        {
            "stage_focus": ["Seed"],
            "geography": ["Europe"],
            "preferences": ["institutional"],
        }
    )
    storage = Storage(str(tmp_path / "startups.json"))
    storage.add_startup(
        ScoutInfo(
            startup_id="production-handoff",
            name="PrecisionCo",
            one_line="Production handoff fixture",
            sector="Infrastructure",
            problem="Decision traces can drift between stages.",
            solution="Persist one governed consensus artifact.",
            target_users="Institutional venture funds",
            why_now="Auditability is a prerequisite for automation.",
            scout_type="market_driven",
            confidence_score=0.9,
            funding_stage="Seed",
            location="Dublin, Europe",
        )
    )
    monkeypatch.setattr(reviewer_module, "DefaultReviewer", _PersistingReviewerPersona)
    monkeypatch.setattr(reviewer_module, "SkepticalReviewer", _PersistingReviewerPersona)
    monkeypatch.setattr(reviewer_module, "OpportunistReviewer", _PersistingReviewerPersona)
    monkeypatch.setattr(
        reviewer_module, "enrich_scout_for_reviewer_llm", lambda scout, _uid: scout
    )
    monkeypatch.setattr(calibrator_module, "load_calibration_state", lambda _uid: {})
    if adversarial_resolution:
        def mutate_compatibility_fields(primary, _results):
            for dimension in (
                "market",
                "product",
                "technical",
                "execution",
                "defensibility",
            ):
                primary[f"{dimension}_score"] = 10
            primary["overall_score"] = 10
            return ["adversarial compatibility mutation"], "mutated"

        monkeypatch.setattr(
            reviewer_module, "apply_resolution_to_primary", mutate_compatibility_fields
        )

    engine = reviewer_module.ReviewerEngine(
        api_key="",
        storage=storage,
        tenant_user_id="user-a",
        evaluation_prerequisites=prerequisites,
    )

    class _TraceSequence:
        def __init__(self, values):
            self._values = iter(values)

        def score(self, _scout, _review):
            return deepcopy(next(self._values))

    engine.structured_scoring_engine = _TraceSequence(traces)
    saved = await engine.run_startup(
        "production-handoff",
        bypass_agent_enabled_gate=True,
    )
    return saved, storage.get_startup("production-handoff"), prerequisites


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "traces",
    [
        [_persona_trace(9), _persona_trace(9), _persona_trace(9)],
        [_persona_trace(9), _persona_trace(5), _persona_trace(5)],
        [_persona_trace(9), _persona_trace(9, missing_dimension="defensibility"), _persona_trace(9)],
    ],
    ids=["identical", "disagreement", "missing-dimension"],
)
async def test_governed_reviewer_persists_qualitative_research_only(tmp_path, monkeypatch, traces):
    saved, reloaded, prerequisites = await _run_persisted_governed_review(
        tmp_path, monkeypatch, traces
    )

    assert saved is True
    assert reloaded is not None and reloaded.review_info is not None
    assert reloaded.review_info.structured_scoring is None
    assert reloaded.review_info.overall_score is None
    assert reloaded.review_info.market_score is None
    expected_grounding = prerequisites.compiled_scoring_policy["scoring_runtime"][
        "evidence_grounding"
    ]
    assert _PersistingReviewerPersona.grounding_contracts[-3:] == [expected_grounding] * 3


@pytest.mark.asyncio
async def test_embedding_backed_active_thesis_without_alignment_blocks_otherwise_invest(
    tmp_path, monkeypatch
):
    saved, reloaded, prerequisites = await _run_persisted_governed_review(
        tmp_path,
        monkeypatch,
        [_persona_trace(9), _persona_trace(9), _persona_trace(9)],
        embedding_backed=True,
    )

    assert saved is True
    assert reloaded is not None and reloaded.review_info is not None
    assert reloaded.review_info.fund_thesis_version_id == "thesis-live"
    assert reloaded.review_info.thesis_alignment_score is None

    partner = PartnerEngine(
        storage=SimpleNamespace(_user_id="user-a"),
        tenant_user_id="user-a",
        use_llm_fallback=False,
        evaluation_prerequisites=prerequisites,
    )
    entry = partner._build_entry(reloaded)
    assert entry is not None
    assert (
        entry["review"].get("thesis_alignment_state")
        == "missing_under_active_thesis"
    )

    decision = partner.decision_engine.decide(
        entry["scout"],
        entry["review"],
        fund_thesis=partner.fund_thesis,
    )

    assert decision["recommendation"] == "MONITOR"
    assert decision["human_review_required"] is True
    assert decision["mandate_gate"] == "alignment_missing"
    assert decision["mandate_gate"] != "no_mandate"
    assert partner_output_to_partner_info(decision).mandate_gate == "alignment_missing"


@pytest.mark.asyncio
async def test_governed_reviewer_drops_adversarial_numeric_mutation(
    tmp_path, monkeypatch
):
    saved, reloaded, _ = await _run_persisted_governed_review(
        tmp_path,
        monkeypatch,
        [_persona_trace(5), _persona_trace(5), _persona_trace(5)],
        adversarial_resolution=True,
    )

    assert saved is True
    assert reloaded.review_info.market_score is None
    assert reloaded.review_info.overall_score is None
    assert reloaded.review_info.structured_scoring is None


@pytest.mark.asyncio
async def test_governed_reviewer_does_not_consume_mixed_policy_score_traces(
    tmp_path, monkeypatch
):
    stale = _persona_trace(9, policy_version_id="stale-policy")
    saved, reloaded, _ = await _run_persisted_governed_review(
        tmp_path,
        monkeypatch,
        [_persona_trace(9), stale, _persona_trace(9)],
    )

    assert saved is True
    assert reloaded is not None and reloaded.review_info is not None
    assert reloaded.review_info.structured_scoring is None


@pytest.mark.parametrize(
    "trace",
    [
        None,
        {},
        {**_exact_trace(9), "policy_version_id": "wrong-version"},
        {**_exact_trace(9), "policy_hash": "wrong-hash"},
        {**_exact_trace(9), "scoring_runtime_version": "9.9.9"},
        {**_exact_trace(9), "scoring_runtime_hash": "wrong-runtime-hash"},
        {
            **_exact_trace(9),
            "execution": {"score": 9, "confidence": 0.9, "unscored": True},
        },
    ],
    ids=[
        "absent",
        "malformed",
        "wrong-version",
        "wrong-hash",
        "wrong-runtime-version",
        "wrong-runtime-hash",
        "incomplete",
    ],
)
def test_governed_partner_ignores_every_reviewer_structured_trace(trace):
    review = _governed_review(9)
    review["structured_scoring"] = trace

    decision = _governed_partner().decide(_decision_scout(), review)
    assert decision["recommendation"] == "MONITOR"
    assert "canonical evaluation is blocked" in decision["decision_rationale"].lower()


@pytest.mark.parametrize("user_id", [None, "user-b"])
def test_governed_trace_rejects_missing_or_cross_tenant_identity(user_id):
    trace = _persona_trace(9)
    if user_id is None:
        trace.pop("user_id")
    else:
        trace["user_id"] = user_id

    with pytest.raises(RuntimeError, match="tenant"):
        validate_governed_scoring_trace(trace, _prerequisites())


def test_governed_partner_does_not_decide_from_a_complete_reviewer_trace():
    decision = _governed_partner().decide(_decision_scout(), _governed_review(9))

    assert decision["recommendation"] == "MONITOR"


def test_reviewer_consensus_trace_is_discarded_at_the_persistence_boundary():
    review = _governed_review_from_persona_traces(
        [_persona_trace(9), _persona_trace(5), _persona_trace(5)]
    )

    assert review["market_score"] is None
    assert review["overall_score"] is None
    assert review["structured_scoring"] is None

    serialized = json.loads(json.dumps(review))
    decision = _governed_partner().decide(_decision_scout(), serialized)
    assert decision["recommendation"] == "MONITOR"


def test_reviewer_consensus_missingness_is_not_promoted_to_an_assessment():
    review = _governed_review_from_persona_traces(
        [
            _persona_trace(9),
            _persona_trace(9, missing_dimension="defensibility"),
            _persona_trace(9),
        ]
    )

    assert review["structured_scoring"] is None
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


def test_governed_persona_rubric_identity_mismatch_fails_before_consensus():
    stale = _persona_trace(8)
    stale["rubric_version"] = "tenant-rubric:stale-policy"

    with pytest.raises(RuntimeError, match="rubric version does not match"):
        _governed_review_from_persona_traces(
            [_persona_trace(8), stale, _persona_trace(8)]
        )


def test_governed_persona_tenant_identity_mismatch_fails_before_consensus():
    cross_tenant = _persona_trace(8)
    cross_tenant["user_id"] = "user-b"

    with pytest.raises(RuntimeError, match="tenant"):
        _governed_review_from_persona_traces(
            [_persona_trace(8), cross_tenant, _persona_trace(8)]
        )


def test_governed_single_review_and_adapter_never_synthesize_neutral_scores():
    reviewer = ReviewerEngine.__new__(ReviewerEngine)
    snapshots = reviewer._build_single_reviews(
        [
            {
                "reviewer_type": "DefaultReviewer",
                "overall_summary": "Evidence missing",
                "key_risks": ["No evidence"],
                "verdict": "WEAK",
            }
        ]
    )
    adapted = reviewer_output_to_review_info(
        {
            "overall_summary": "Evidence missing",
            "key_risks": ["No evidence"],
            "verdict": "WEAK",
        }
    )

    assert snapshots[0].market_score is None
    assert snapshots[0].product_score is None
    assert snapshots[0].technical_score is None
    assert snapshots[0].execution_score is None
    assert adapted.market_score is None
    assert adapted.product_score is None
    assert adapted.technical_score is None
    assert adapted.execution_score is None


def test_reviewer_adapter_discards_numeric_assessment_fields():
    adapted = reviewer_output_to_review_info(
        {
            "overall_summary": "Strong research, but separate canonical evidence is required.",
            "key_risks": [],
            "verdict": "MEDIUM",
            "market_score": 9,
            "product_score": 8,
            "technical_score": 7,
            "execution_score": 6,
            "defensibility_score": 5,
            "overall_score": 7.0,
            "overall_label": "STRONG",
            "derived_verdict": "STRONG",
            "score_reasoning": {"market": "Legacy score"},
            "structured_scoring": {"overall_score": 7.0},
            "structured_signals": {"market": {"tam": {"value": "$1B"}}},
        }
    )

    assert adapted.market_score is None
    assert adapted.product_score is None
    assert adapted.technical_score is None
    assert adapted.execution_score is None
    assert adapted.defensibility_score is None
    assert adapted.overall_score is None
    assert adapted.overall_label is None
    assert adapted.derived_verdict is None
    assert adapted.score_reasoning is None
    assert adapted.structured_scoring is None
    assert adapted.structured_signals is None


def test_governed_consensus_preserves_dynamic_missing_reason_provenance():
    prerequisites = _prerequisites()
    prerequisites.compiled_scoring_policy["dimensions"]["impact"] = {
        "id": "impact",
        "weight": 10,
        "criteria": [],
    }
    traces = []
    for score, reviewer_type in ((9, "DefaultReviewer"), (7, "SkepticalReviewer"), (8, "OpportunistReviewer")):
        trace = _persona_trace(score)
        trace["impact"] = {
            "score": score,
            "confidence": 0.8,
            "components": {},
            "unscored": False,
        }
        traces.append({"reviewer_type": reviewer_type, "structured_scoring": trace})
    traces[1]["structured_scoring"]["impact"] = {
        "score": None,
        "confidence": 0.0,
        "components": {},
        "unscored": True,
        "missing_reasons": ["no_impact_measurement", "no_counterfactual"],
    }
    traces[1]["structured_scoring"]["overall_score"] = None

    from evaluation_v2.governed_scoring import resolve_governed_scoring_traces

    resolved = resolve_governed_scoring_traces(traces, prerequisites)

    assert resolved["impact"]["score"] is None
    assert resolved["impact"]["missing_reasons"] == [
        "SkepticalReviewer:no_impact_measurement",
        "SkepticalReviewer:no_counterfactual",
    ]


def test_governed_partner_ignores_an_unresolved_persona_trace_even_when_identity_matches():
    review = _governed_review(9)
    review["structured_scoring"] = _persona_trace(9)

    assert _governed_partner().decide(_decision_scout(), review)["recommendation"] == "MONITOR"


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


def test_governed_trace_accepts_score_band_metadata():
    trace = _persona_trace(7)
    trace["score_bands"] = [{"min": 1, "max": 3, "label": "Weak"}]

    validated = validate_governed_scoring_trace(trace, _prerequisites())

    assert validated["score_bands"] == trace["score_bands"]


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
    "score",
    [
        5.99, 6.0, 6.01, 7.99, 8.0, 8.01,
    ],
)
def test_governed_partner_does_not_use_reviewer_boundary_scores(score):
    review = _governed_review(score)

    assert review["market_score"] is None
    assert review["reviews"][0]["market_score"] is None
    assert review["structured_scoring"] is None
    decision = _governed_partner().decide(_decision_scout(), review)
    assert decision["recommendation"] == "MONITOR"


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
