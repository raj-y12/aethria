"""Round-four Partner threshold and historical-replay regressions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from evaluation_v2.partner_rules import parse_partner_rules
from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.prerequisites import EvaluationPrerequisites
from partner.decision import PartnerDecisionEngine
from services.scoring.policy_compiler import compile_policy_from_fund_config


_CONFIG_ROOT = Path(__file__).resolve().parents[3] / "resources" / "config"


def _rules(version: str) -> dict[str, Any]:
    path = _CONFIG_ROOT / "partner_rules" / f"v{version}.json"
    return json.loads(path.read_text())


def _scout() -> dict[str, Any]:
    return {
        "name": "Threshold Authority Co",
        "one_line": "Governed policy infrastructure",
        "sector": "Infrastructure",
        "funding_stage": "Seed",
        "confidence": 0.9,
    }


def _legacy_review(*, verdict: str, score: float) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "market_score": score,
        "product_score": score,
        "technical_score": score,
        "execution_score": score,
        "defensibility_score": score,
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced operating team."],
        "business_model_analysis": ["Validated recurring revenue model."],
    }


def _governed_prerequisites() -> EvaluationPrerequisites:
    # Deliberately conflicts with active v4's 6.0/8.0 Partner boundaries. These
    # published display/workflow inputs are hash-bound, but they are not a
    # second Partner decision ladder.
    compiled = compile_policy_from_fund_config(
        {
            "scoringWeights": [
                {"key": "market", "weight": 50},
                {"key": "execution", "weight": 50},
            ],
            "thresholds": {
                "autoPass": 69,
                "partnerReview": 70,
                "monitor": 80,
                "escalation": 90,
            },
        },
        require_publish_ready=True,
    )
    compiled["policy_version_id"] = "policy-round4"
    rules = _rules("4")
    return EvaluationPrerequisites(
        user_id="user-round4",
        thesis_context={"version_id": "thesis-round4"},
        thesis_version_id="thesis-round4",
        compiled_scoring_policy=compiled,
        partner_rules=rules,
        fund_config=compiled["decision_inputs"],
        policy=evaluation_policy_from_compiled(compiled, partner_rules=rules),
    )


def _governed_review(
    prerequisites: EvaluationPrerequisites, *, score: float
) -> dict[str, Any]:
    compiled = prerequisites.compiled_scoring_policy
    runtime = compiled["scoring_runtime"]
    persona_trace = {
        **{
            dimension: {
                "score": score,
                "confidence": 0.9,
                "components": {"evidence": {"value": "verified"}},
                "unscored": False,
            }
            for dimension in compiled["dimensions"]
        },
        "overall_score": score,
        "overall_confidence": 0.9,
        "user_id": prerequisites.user_id,
        "policy_version_id": compiled["policy_version_id"],
        "policy_hash": compiled["policy_hash"],
        "rubric_version": prerequisites.policy.rubric_version,
        "scoring_runtime_version": runtime["semantic_version"],
        "scoring_runtime_hash": compiled["scoring_runtime_hash"],
    }
    resolved_trace = {
        **deepcopy(persona_trace),
        "trace_kind": "resolved_consensus",
        "resolution_strategy": {"method": "exact_consensus"},
        "persona_count": 1,
        "input_traces": [
            {"reviewer_type": "DefaultReviewer", "trace": persona_trace}
        ],
    }
    verdict = (
        "STRONG"
        if score >= prerequisites.policy.advance_threshold
        else "MEDIUM"
        if score >= prerequisites.policy.pass_threshold
        else "WEAK"
    )
    return {
        "verdict": verdict,
        "derived_verdict": verdict,
        "market_score": score,
        "product_score": score,
        "technical_score": score,
        "execution_score": score,
        "defensibility_score": score,
        "structured_scoring": resolved_trace,
        "key_risks": [],
        "assumption_feedback": [],
        "team_analysis": ["Experienced operating team."],
        "business_model_analysis": ["Validated recurring revenue model."],
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [(5.99, "PASS"), (6.0, "MONITOR"), (7.99, "MONITOR"), (8.0, "INVEST")],
)
def test_full_governed_decide_uses_one_active_rules_threshold_authority(
    score: float, expected: str
) -> None:
    prerequisites = _governed_prerequisites()
    engine = PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id=prerequisites.user_id,
        evaluation_prerequisites=prerequisites,
    )

    decision = engine.decide(
        _scout(), _governed_review(prerequisites, score=score)
    )

    assert engine._canonical_recommendation(score) == expected
    assert decision["recommendation"] == expected


@pytest.mark.parametrize(
    ("verdict", "score", "expected"),
    [
        ("WEAK", 5.99, {"recommendation": "PASS", "decision": "NO"}),
        ("WEAK", 6.0, {"recommendation": "MONITOR", "decision": "MAYBE"}),
        ("WEAK", 7.2, {"recommendation": "MONITOR", "decision": "MAYBE"}),
        ("WEAK", 8.0, {"recommendation": "INVEST", "decision": "YES"}),
        ("MEDIUM", 8.0, {"recommendation": "INVEST", "decision": "YES"}),
    ],
)
def test_historical_v3_replays_score_authoritative_behavior(
    verdict: str, score: float, expected: dict[str, str]
) -> None:
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine._rules = parse_partner_rules(_rules("3"))
    engine._fund_config = {}
    engine.evaluation_policy = None

    decision = engine.decide(_scout(), _legacy_review(verdict=verdict, score=score))

    assert {
        "recommendation": decision["recommendation"],
        "decision": decision["decision"],
    } == expected
