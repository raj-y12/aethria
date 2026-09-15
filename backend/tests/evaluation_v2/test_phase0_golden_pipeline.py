"""Freeze current evaluator + canonical Partner mapping before Phase 1.

These are synthetic startups, with frozen evidence and no external calls. The
legacy scores are frozen Reviewer handoff inputs, not a claim to execute the
unreachable legacy Partner threshold ladder. Golden output is checked in, never
regenerated during tests. Policy/rubric versions are deliberately pinned.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from evaluation_v2.partner_rules import parse_partner_rules
from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.service import evaluate_snapshot, snapshot_claims
from partner.decision import PartnerDecisionEngine

CONFIG = Path(__file__).resolve().parents[3] / "resources" / "config"
GOLDEN = Path(__file__).with_name("phase0_golden_pipeline.json")
CLOCK = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
DIMENSIONS = ("market", "product", "technical", "execution", "defensibility")
CASES = {
    "A_strong_verified": "Verified high anchors map advance to INVEST; IC review remains required.",
    "B_strong_looking_unverified": "High legacy scores cannot rescue unverified source evidence.",
    "C_contradictory": "A scored market with a contradicting source blocks the recommendation.",
    "D_missing_dimension": "Missing execution stays null, never a numerical zero.",
    "E_out_of_mandate": "Canonical advance is held at MONITOR by Partner's mandate gate.",
    "F_legacy_canonical_diverge": "Legacy 9 versus canonical 6 stays divergent: 6 is the inclusive MONITOR boundary.",
    "G_insufficient_evidence": "No claims or links yields insufficient_evidence and human review.",
}


def _inputs(case):
    claims = [
        {
            "claim_id": f"{case}-{dimension}",
            "claim_type": dimension,
            "normalized_value": {"criterion_score": 8.0, "score_band": "high"},
            "display_text": f"Verified {dimension} evidence for synthetic startup {case}.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        }
        for dimension in DIMENSIONS
    ]
    links = [
        {
            "claim_id": claim["claim_id"],
            "evidence_item_id": f"source-{claim['claim_id']}",
            "relationship": "supports",
            "support_strength": 0.9,
            "verification_state": "verified",
            "source_quality": 0.9,
            "trust_class": "independent",
            "untrusted_input": False,
            "prompt_injection_detected": False,
            "evidence_effective_at": "2026-09-01T00:00:00+00:00",
            "evidence_expires_at": "2027-01-01T00:00:00+00:00",
            "artifact_effective_at": "2026-09-01T00:00:00+00:00",
            "retrieved_at": "2026-09-01T01:00:00+00:00",
        }
        for claim in claims
    ]
    review = {
        "verdict": "STRONG",
        **{f"{dimension}_score": 9.0 for dimension in DIMENSIONS},
        "key_risks": [],
        "assumption_feedback": [],
        "score_reasoning": {},
        "team_analysis": ["Synthetic founder operating history."],
        "business_model_analysis": ["Synthetic annual contracts."],
        "thesis_alignment_score": 0.9,
        "thesis_alignment_confidence": 0.9,
    }
    if case == "B_strong_looking_unverified":
        for link in links:
            link["verification_state"] = "unverified"
    elif case == "C_contradictory":
        links.append({**links[0], "evidence_item_id": "source-market-contradiction", "relationship": "contradicts"})
    elif case == "D_missing_dimension":
        claims = [claim for claim in claims if claim["claim_type"] != "execution"]
        links = [link for link in links if not link["claim_id"].endswith("-execution")]
    elif case == "E_out_of_mandate":
        review["thesis_alignment_score"] = 0.1
    elif case == "F_legacy_canonical_diverge":
        for claim in claims:
            claim["normalized_value"] = {"criterion_score": 6.0, "score_band": "mid"}
    elif case == "G_insufficient_evidence":
        claims, links = [], []
    return claims, links, review


def _run(case):
    rules_document = json.loads((CONFIG / "partner_rules/v4.json").read_text())
    rubric = json.loads((CONFIG / "evaluation_rubric/v3.json").read_text())
    dimensions = {dimension: {"weight": 20, "criteria": []} for dimension in DIMENSIONS}
    policy_hash = hashlib.sha256(json.dumps(dimensions, sort_keys=True).encode()).hexdigest()
    policy = evaluation_policy_from_compiled(
        {"policy_version_id": "phase0-fixture-policy-v1", "policy_hash": policy_hash, "dimensions": dimensions},
        partner_rules=rules_document,
        rubric=rubric,
    )
    claims, links, review = _inputs(case)
    before = deepcopy((claims, links, review))
    snapshot, digest = snapshot_claims(claims, links, evaluation_at=CLOCK)
    result = evaluate_snapshot(snapshot, policy, evaluation_at=CLOCK)
    engine = PartnerDecisionEngine(
        use_llm_fallback=False,
        tenant_user_id="phase0-golden-tenant",
        use_resource_fund_thesis_fallback=False,
    )
    engine._rules = parse_partner_rules(rules_document)
    engine._fund_config = {}
    partner = engine.decide(
        {"name": case, "one_line": "Synthetic B2B infrastructure", "sector": "B2B SaaS", "funding_stage": "Seed", "confidence": 0.9},
        review,
        canonical_recommendation=result.recommendation.state.value,
        canonical_criteria=[criterion.model_dump(mode="json") for criterion in result.criteria],
        canonical_confidence=result.recommendation.confidence,
    )
    assert engine.llm_call_count == 0
    assert before == (claims, links, review)
    assert digest == result.snapshot_hash
    return {
        "rationale": CASES[case],
        "policy": {key: getattr(policy, key) for key in ("policy_version_id", "policy_hash", "rubric_version", "partner_rules_version", "partner_rules_hash")},
        "evidence_state": {"claims": claims, "links": links},
        "evaluation": result.model_dump(mode="json"),
        "legacy_reviewer_scores": {dimension: review[f"{dimension}_score"] for dimension in DIMENSIONS},
        "partner": {key: partner.get(key) for key in (
            "recommendation", "canonical_recommendation", "human_review_required", "company_quality",
            "conviction_level", "decision_rationale", "decision_drivers", "next_action", "mandate_gate",
            "mandate_override_required", "fund_fit", "fund_fit_label", "fund_fit_confidence",
        )},
    }


@pytest.mark.parametrize("case", CASES)
def test_phase0_current_evidence_evaluation_and_partner_golden(case):
    expected = json.loads(GOLDEN.read_text())[case]
    assert _run(case) == expected
