"""Sub-project 1, Task 2: the critical-risk-plus-incomplete-coverage conviction
is versioned policy data (resources/config/partner_rules), not a Python literal."""

import json
from pathlib import Path

from evaluation_v2.partner_rules import parse_partner_rules
from partner.decision import PartnerDecisionEngine


_V4_PATH = (
    Path(__file__).resolve().parents[2]
    / "resources" / "config" / "partner_rules" / "v4.json"
)


def _scout():
    return {"name": "Sona", "sector": "B2B SaaS", "funding_stage": "Seed", "confidence": 0.8}


def _thin_review_with_critical_risk():
    # Only one of the four required dimensions is scored, and the risk text
    # matches a configured critical_risk_keyword — this is the exact branch
    # that used to hardcode conviction=8 (backend/partner/decision.py).
    return {
        "verdict": "WEAK",
        "market_score": 3,
        "product_score": None,
        "technical_score": None,
        "execution_score": None,
        "key_risks": ["Regulatory ban on this business model in the target market."],
        "assumption_feedback": [],
        "team_analysis": [],
        "business_model_analysis": [],
    }


def test_critical_risk_pass_conviction_comes_from_versioned_rules_not_a_literal():
    document = json.loads(_V4_PATH.read_text())
    assert document["critical_risk_pass_conviction"] == 8

    mutated = dict(document)
    mutated["critical_risk_pass_conviction"] = 3
    rules = parse_partner_rules(mutated)

    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    engine._rules = rules  # same override point the contract/mutation tests use

    out = engine.decide(_scout(), _thin_review_with_critical_risk())

    assert out["recommendation"] == "PASS"
    assert out["conviction_level"] == 5
