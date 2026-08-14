import asyncio
from types import SimpleNamespace
import pytest

from regulatory_context import (
    apply_regulatory_grounding_guard,
    build_reviewer_regulatory_context,
    CanonicalReviewerRegulatoryContextProvider,
)
from reviewer.engine import ReviewerEngine
from reviewer.reviewer import DefaultReviewer
import json


def _context(*, operational=True, expansion=False, contradictory=False):
    claims = []
    evidence = []
    if operational:
        claims.append({
            "claim_id": "op-1",
            "claim_type": "operational_feasibility",
            "status": "current",
            "confidence": 0.95,
            "display_text": "The company operates commercially in Ireland today.",
        })
        evidence.append({
            "claim_id": "op-1",
            "relationship": "supports",
            "source_locator": "official.example/operations",
            "display_excerpt": "The company operates commercially in Ireland today.",
            "verification_state": "verified",
            "access_class": "public",
        })
    if expansion:
        claims.append({
            "claim_id": "exp-1",
            "claim_type": "regulatory_expansion_risk",
            "status": "current",
            "confidence": 0.8,
            "display_text": "Expansion into Germany requires regulatory approval.",
        })
        evidence.append({
            "claim_id": "exp-1",
            "relationship": "supports",
            "source_locator": "regulator.example/approval",
            "display_excerpt": "Expansion into Germany requires regulatory approval.",
            "verification_state": "verified",
            "access_class": "public",
        })
    if contradictory:
        evidence.append({
            "claim_id": "op-1",
            "relationship": "contradicts",
            "source_locator": "registry.example/status",
            "display_excerpt": "The current operating status is disputed.",
            "verification_state": "disputed",
            "access_class": "public",
        })
    return build_reviewer_regulatory_context(claims=claims, evidence=evidence)


def test_current_operation_prevents_categorical_impossibility_but_preserves_expansion_risk():
    context = _context(expansion=True)
    result = apply_regulatory_grounding_guard(
        {
            "overall_summary": "The company cannot operate legally.",
            "key_risks": ["Regulatory expansion may require approval."],
        },
        context,
    )

    assert "cannot operate legally" not in result["overall_summary"]
    assert "verified evidence" in result["overall_summary"]
    assert "expansion" in result["key_risks"][0]


def test_contradictory_and_insufficient_context_force_uncertainty():
    contradictory = apply_regulatory_grounding_guard(
        {"key_risks": ["Current operation is impossible."]},
        _context(contradictory=True),
    )
    insufficient = apply_regulatory_grounding_guard(
        {"key_risks": ["The company cannot operate today."]},
        _context(operational=False),
    )

    assert "uncertain" in contradictory["key_risks"][0].lower()
    assert "uncertain" in insufficient["key_risks"][0].lower()


def test_regulatory_packet_is_bounded_and_keeps_public_private_boundary():
    context = build_reviewer_regulatory_context(
        claims=[{
            "claim_id": "private",
            "claim_type": "operational_feasibility",
            "status": "current",
            "confidence": 0.9,
            "display_text": "Private operator note.",
        }],
        evidence=[{
            "claim_id": "private",
            "relationship": "supports",
            "source_locator": "private.example",
            "display_excerpt": "Private operator note.",
            "verification_state": "verified",
            "access_class": "tenant_confidential",
        }],
        max_chars=240,
    )

    assert context["chars"] <= 240
    assert "Private operator note." in context["text"]
    assert context["has_verified_current_operation"] is True


def test_all_three_legacy_personas_receive_the_same_grounded_packet():
    class FakeReviewer:
        def __init__(self):
            self.received = []

        async def review(self, payload):
            self.received.append(payload)
            return {"verdict": "MEDIUM"}

    engine = object.__new__(ReviewerEngine)
    engine.reviewer = FakeReviewer()
    engine.skeptical_reviewer = FakeReviewer()
    engine.opportunist_reviewer = FakeReviewer()
    payload = {"_canonical_regulatory_context": _context()}

    results = asyncio.run(engine._review_personas(payload))

    assert len(results) == 3
    received = [reviewer.received[0] for reviewer in (
        engine.reviewer,
        engine.skeptical_reviewer,
        engine.opportunist_reviewer,
    )]
    assert [item["_canonical_regulatory_context"] for item in received] == [
        payload["_canonical_regulatory_context"]
    ] * 3


def test_legacy_reviewer_prompt_keeps_scout_context_and_guards_output():
    reviewer = DefaultReviewer(
        api_key="sk-test",
        model="gpt-test",
        tenant_user_id="user_test",
        use_resource_fund_thesis_fallback=False,
    )

    class Completions:
        def __init__(self):
            self.prompt = ""

        def create(self, *, messages, **kwargs):
            self.prompt = messages[-1]["content"]
            content = json.dumps({
                    "overall_summary": "The company cannot operate legally.",
                    "key_risks": ["Expansion may require approval."],
                    "verdict": "MEDIUM",
                })
            return {"choices": [{"message": {"content": content}}], "usage": None}

    completions = Completions()
    reviewer.client.chat = type("Chat", (), {"completions": completions})()
    context = _context(expansion=True)
    result = reviewer._call_llm_sync({
        "name": "Acme",
        "one_line": "Scout prose remains present.",
        "sector": "regulated services",
        "_canonical_regulatory_context": context,
    })

    assert "Scout prose remains present." in completions.prompt
    assert "CANONICAL REGULATORY EVIDENCE" in completions.prompt
    assert "prefer company-specific verified evidence" in completions.prompt
    assert reviewer._last_regulatory_context_chars == context["chars"]
    assert "cannot operate legally" not in result["overall_summary"]
    assert "Expansion may require approval." in result["key_risks"]
    from utils.prompt_version import hash_prompt
    assert result["prompt_version"] == hash_prompt(reviewer.SYSTEM_PROMPT)


def test_non_default_personas_use_compact_contract_but_keep_divergence_fields():
    from reviewer.skeptical import SkepticalReviewer

    reviewer = SkepticalReviewer(
        api_key="sk-test",
        model="gpt-test",
        tenant_user_id="user_test",
        use_resource_fund_thesis_fallback=False,
        structured_scoring_enabled=True,
    )

    class Completions:
        def __init__(self):
            self.prompt = ""

        def create(self, *, messages, **kwargs):
            self.prompt = messages[-1]["content"]
            return {
                "choices": [{"message": {"content": json.dumps({
                    "structured_signals": {},
                    "overall_summary": "Risk-first read.",
                    "key_risks": ["Execution evidence is thin."],
                    "verdict": "WEAK",
                    "diligence_red_flags": ["Missing team information"],
                    "assumption_feedback": ["Traction remains unverified."],
                })}}],
                "usage": None,
            }

    completions = Completions()
    reviewer.client.chat = type("Chat", (), {"completions": completions})()
    result = reviewer._call_llm_sync({
        "name": "Acme",
        "one_line": "Scout context remains available.",
        "sector": "logistics",
    })

    assert result["verdict"] == "WEAK"
    assert result["key_risks"] == ["Execution evidence is thin."]
    assert result["team_analysis"] == []
    assert result["competition_analysis"] == []
    assert result["business_model_analysis"] == []
    assert result["investment_thesis"] == []
    assert result["risk_mitigation"] == []
    assert "team_analysis" not in completions.prompt
    assert "competition_analysis" not in completions.prompt
    assert "business_model_analysis" not in completions.prompt
    assert "investment_thesis" not in completions.prompt
    assert "risk_mitigation" not in completions.prompt
    assert "COMPLETE structured_signals" in completions.prompt
    assert result["prompt_version"]


@pytest.mark.asyncio
async def test_canonical_provider_filters_restricted_and_cross_tenant_rows():
    class Identity:
        async def get_opportunity_by_legacy_projection(self, *, user_id, legacy_startup_id):
            assert user_id == "user-a"
            assert legacy_startup_id == "startup-1"
            return SimpleNamespace(opportunity_id="opp-1")

    class Evidence:
        async def get_ledger(self, *, user_id, opportunity_id):
            assert user_id == "user-a"
            assert opportunity_id == "opp-1"
            return {
                "claims": [{
                    "claim_id": "claim-1", "claim_type": "operational_feasibility",
                    "status": "current", "confidence": 0.9,
                    "display_text": "The company operates commercially today.",
                }],
                "claim_evidence_links": [
                    {"claim_id": "claim-1", "evidence_item_id": "item-1", "relationship": "supports"},
                    {"claim_id": "claim-1", "evidence_item_id": "item-2", "relationship": "supports"},
                ],
                "evidence_items": [
                    {"evidence_item_id": "item-1", "artifact_id": "artifact-public",
                     "display_excerpt": "The company operates commercially today.",
                     "source_locator": "public.example", "verification_state": "verified"},
                    {"evidence_item_id": "item-2", "artifact_id": "artifact-private",
                     "display_excerpt": "PRIVATE TENANT SECRET", "source_locator": "private.example",
                     "verification_state": "verified"},
                ],
                "artifacts": [
                    {"artifact_id": "artifact-public", "source_uri": "public.example",
                     "access_class": "public", "prompt_injection_detected": False},
                    {"artifact_id": "artifact-private", "source_uri": "private.example",
                     "access_class": "restricted", "prompt_injection_detected": False},
                ],
            }

    context = await CanonicalReviewerRegulatoryContextProvider(Identity(), Evidence())(
        "user-a", "startup-1"
    )
    assert "The company operates commercially today." in context["text"]
    assert "PRIVATE TENANT SECRET" not in context["text"]
