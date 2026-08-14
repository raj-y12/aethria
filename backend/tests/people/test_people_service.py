from resolver.founder_resolver import FounderCandidate, FounderEvidence, FounderFieldConflict, FounderResolution
from people.service import canonicalize_founder_resolution, normalize_person_name


def _resolution(*founders):
    return FounderResolution(company="Acme", founders=list(founders), resolution_status="FOUND")


def test_person_name_normalization_is_stable():
    assert normalize_person_name("  Zoë  van der Meer ") == "zoe van der meer"


def test_same_verified_profile_is_one_identity_key_even_when_name_varies():
    rows = canonicalize_founder_resolution(
        _resolution(
            FounderCandidate(
                name="Jane Smith", linkedin_url="https://www.linkedin.com/in/jane-smith/",
                evidence=[FounderEvidence(url="https://acme.example/team", supports="founder")],
            ),
            FounderCandidate(
                name="Jane A. Smith", linkedin_url="https://linkedin.com/in/jane-smith",
                evidence=[FounderEvidence(url="https://news.example/acme", supports="founder")],
            ),
        ),
        company_id="company-1",
    )
    assert rows[0].identity_key == rows[1].identity_key


def test_same_name_without_strong_identifier_does_not_merge_across_companies():
    first = canonicalize_founder_resolution(
        _resolution(FounderCandidate(name="Alex Lee", evidence=[FounderEvidence(url="https://a.example")])) ,
        company_id="company-a",
    )[0]
    second = canonicalize_founder_resolution(
        _resolution(FounderCandidate(name="Alex Lee", evidence=[FounderEvidence(url="https://b.example")])) ,
        company_id="company-b",
    )[0]
    assert first.identity_key != second.identity_key


def test_canonicalizer_preserves_temporal_history_and_conflicts():
    row = canonicalize_founder_resolution(
        _resolution(
            FounderCandidate(
                name="Priya Shah", role="Founder & CEO",
                previous_employment=["OldCo"], education=["MIT"],
                conflicts=[FounderFieldConflict(field="role", values=["CEO", "CTO"], source_urls=["https://x.example"])],
                evidence=[FounderEvidence(url="https://acme.example/team", supports="founder")],
            )
        ), company_id="company-1"
    )[0]
    assert row.relationship_type == "founder"
    assert {item.history_type for item in row.history} == {"worked_at_company", "education"}
    assert row.conflict_fields == ("role",)


def test_shallow_candidate_is_marked_unresolved_and_not_promoted():
    row = canonicalize_founder_resolution(
        _resolution(FounderCandidate(name="Unknown Person")), company_id="company-1"
    )[0]
    assert row.persistable is False
    assert row.unresolved_reason == "insufficient_grounding"
