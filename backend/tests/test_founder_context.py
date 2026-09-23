from context import build_founder_context
from context import apply_founder_grounding_guard
from resolver.founder_resolver import (
    FounderCandidate,
    FounderEvidence,
    FounderFieldConflict,
    FounderResolution,
)


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
