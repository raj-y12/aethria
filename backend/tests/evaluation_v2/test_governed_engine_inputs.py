from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites


def _compiled_policy():
    return {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {
            "market": {
                "weight": 60,
                "criteria": [{"id": "market_quality", "source_components": ["tam"]}],
            },
            "execution": {
                "weight": 40,
                "criteria": [
                    {"id": "execution_quality", "source_components": ["traction"]}
                ],
            },
        },
    }


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
    fund_config = {
        "scoringWeights": [
            {"key": "market", "weight": 70},
            {"key": "execution", "weight": 30},
        ],
        "scoreBands": [
            {"id": "pass", "min": 0, "max": 59, "label": "Pass"},
            {"id": "invest", "min": 60, "max": 100, "label": "Invest"},
        ],
    }
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
        fund_config=fund_config,
        policy=evaluation_policy_from_compiled(compiled, partner_rules=rules),
    )


class _ReviewerPersona:
    def __init__(self, *_args, **_kwargs):
        self.fund_thesis = None

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
    assert reviewer.structured_scoring_engine.dimension_weights == {
        "market": 70.0,
        "execution": 30.0,
    }


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
