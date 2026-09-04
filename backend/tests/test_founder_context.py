import asyncio
import json
import logging

from founder_context import build_founder_context
from founder_context import apply_founder_grounding_guard
from resolver.founder_resolver import (
    FounderCandidate,
    FounderEvidence,
    FounderFieldConflict,
    FounderResolution,
)
from reviewer.engine import ReviewerEngine
from reviewer.reviewer import DefaultReviewer


def _resolution(*, rich=True, private=False, conflict=False):
    evidence = FounderEvidence(
        url="https://manna.aero/team",
        title="Manna leadership",
        snippet=(
            "Bobby Healy is Founder and CEO of Manna. He previously founded CarTrawler, "
            "built logistics businesses, led engineering teams, and raised venture funding."
            if rich
            else "Bobby Healy is Founder and CEO of Manna."
        ),
        source_type="official_site",
        supports="Founder and leadership evidence",
        access_class="restricted" if private else "public",
    )
    candidate = FounderCandidate(
        name="Bobby Healy",
        role="Founder & CEO",
        previous_employment=["CarTrawler"] if rich else [],
        education=[],
        evidence=[evidence],
        conflicts=(
            [FounderFieldConflict(field="role", values=["CEO", "CTO"], source_urls=[evidence.url])]
            if conflict
            else []
        ),
        field_confidence={"name": 0.9, "role": 0.9},
        confidence=0.9,
    )
    return FounderResolution(
        company="Manna Air Delivery",
        website="https://manna.aero",
        founders=[candidate],
        resolution_status="FOUND" if rich else "PARTIAL",
        confidence=0.9 if rich else 0.45,
        missing_fields=[] if rich else ["previous_employment", "domain_experience"],
    )


def test_founder_context_preserves_history_capabilities_and_provenance():
    context = build_founder_context(_resolution())

    assert context["chars"] <= 4000
    assert context["has_verified_identity"] is True
    assert context["has_history"] is True
    assert "CarTrawler" in context["text"]
    assert "founder_startup_experience" in {claim["claim_type"] for claim in context["claims"]}
    assert "https://manna.aero/team" in context["text"]


def test_shallow_founder_history_forces_uncertainty_and_does_not_invent_strength():
    context = build_founder_context(_resolution(rich=False))

    assert context["has_verified_identity"] is True
    assert context["has_history"] is False
    assert context["missing_information"]
    assert "prior startup" not in context["text"].lower()


def test_insufficient_founder_history_forces_uncertainty_in_founder_market_fit_text():
    context = build_founder_context(_resolution(rich=False))
    guarded = apply_founder_grounding_guard(
        {"team_analysis": ["Proven founder with deep prior startup experience."]},
        context,
    )

    assert "proven founder" not in guarded["team_analysis"][0].lower()
    assert "uncertain" in guarded["team_analysis"][0].lower()


def test_founder_conflicts_and_private_evidence_are_explicit_and_filtered():
    conflicted = build_founder_context(_resolution(conflict=True))
    assert conflicted["has_conflict"] is True
    assert "conflict" in conflicted["text"].lower()

    private = build_founder_context(_resolution(private=True))
    assert private["has_verified_identity"] is False
    assert "Manna leadership" not in private["text"]


def test_all_three_reviewer_personas_receive_the_same_bounded_founder_packet():
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
    payload = {"_canonical_founder_context": build_founder_context(_resolution())}

    results = asyncio.run(engine._review_personas(payload))

    assert len(results) == 3
    received = [
        reviewer.received[0]["_canonical_founder_context"]
        for reviewer in (engine.reviewer, engine.skeptical_reviewer, engine.opportunist_reviewer)
    ]
    assert received == [payload["_canonical_founder_context"]] * 3


def test_reviewer_preparation_bridges_persisted_founder_resolution_before_fanout():
    engine = object.__new__(ReviewerEngine)
    engine.tenant_user_id = "user_test"
    engine.regulatory_context_loader = None
    engine.logger = logging.getLogger("test.reviewer")

    prepared = asyncio.run(
        engine._prepare_scout_for_llm(
            {"id": "startup-1", "founder_resolution": _resolution()}
        )
    )

    assert prepared["_canonical_founder_context"]["has_history"] is True


def test_legacy_reviewer_prompt_keeps_scout_context_and_founder_packet():
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
            return {
                "choices": [{"message": {"content": json.dumps({
                    "overall_summary": "Founder evidence is available for diligence.",
                    "key_risks": [],
                    "verdict": "MEDIUM",
                })}}],
                "usage": None,
            }

    completions = Completions()
    reviewer.client.chat = type("Chat", (), {"completions": completions})()
    result = reviewer._call_llm_sync(
        {
            "name": "Manna Air Delivery",
            "one_line": "Scout founder prose remains present.",
            "sector": "logistics",
            "_canonical_founder_context": build_founder_context(_resolution()),
        }
    )

    assert result is not None
    assert "Scout founder prose remains present." in completions.prompt
    assert "CANONICAL FOUNDER EVIDENCE" in completions.prompt
    assert "Founder-Market Fit" in completions.prompt
