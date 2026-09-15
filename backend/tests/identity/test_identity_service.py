import pytest

from identity.models import (
    IdentityAdmission,
    IdentityStatus,
    SourceObservationInput,
)
from identity.service import IdentityService


class _Repository:
    def __init__(self, matches=None, existing_admission=None):
        self.matches = matches or []
        self.existing_admission = existing_admission
        self.calls = []

    async def record_observation(self, value):
        self.calls.append(("record", value))
        return type("Observation", (), {"observation_id": "observation-1"})()

    async def get_admission_for_observation(self, **kwargs):
        self.calls.append(("get_admission", kwargs))
        return self.existing_admission

    async def find_companies_by_verified_identifiers(self, **kwargs):
        self.calls.append(("find", kwargs))
        return self.matches

    async def resolve_existing_admission(self, **kwargs):
        self.calls.append(("resolve", kwargs))
        return IdentityAdmission(
            user_id=kwargs["user_id"],
            observation_id=kwargs["observation_id"],
            status=IdentityStatus.RESOLVED,
            company_id=kwargs["company_id"],
            opportunity_id="opportunity-1",
            confidence=kwargs["confidence"],
            matched_identifier=kwargs["matched_identifier"],
        )

    async def create_company_admission(self, **kwargs):
        self.calls.append(("create", kwargs))
        return IdentityAdmission(
            user_id=kwargs["observation"].user_id,
            observation_id=kwargs["observation_id"],
            status=IdentityStatus.RESOLVED,
            company_id="company-new",
            opportunity_id="opportunity-new",
            confidence=kwargs["confidence"],
            created=True,
        )

    async def open_identity_case(self, **kwargs):
        self.calls.append(("case", kwargs))
        return IdentityAdmission(
            user_id=kwargs["observation"].user_id,
            observation_id=kwargs["observation_id"],
            status=IdentityStatus.AMBIGUOUS,
            identity_case_id="case-1",
            confidence=kwargs["confidence"],
            blocks_evaluation=True,
            candidates=kwargs["candidates"],
        )


@pytest.mark.asyncio
async def test_raw_website_hint_cannot_override_conflicting_retrieved_identity():
    repo = _Repository()
    result = await IdentityService(repo).admit(SourceObservationInput(
        user_id="fund-a", channel="manual_lookup", observed_name="Assiduous",
        observed_domain="assiduous.ai", source_metadata={"operator_confirmed_identity": True},
        resolution_payload={"query": "Assiduous", "canonical_name": "Assiduous",
            "website": "https://assiduous.ai", "confidence": 0.9,
            "alternative_matches": [{"name": "Assiduous", "website": "https://assiduous.tech", "match_score": 1.0, "reason": "competing domain"}],
            "candidates": [{"name": "Assiduous", "website": "https://assiduous.tech", "confidence": 1.0}]},
    ))
    assert result.blocks_evaluation
    assert not any(call[0] == "create" for call in repo.calls)


def _observation(**overrides):
    values = {
        "user_id": "fund-a",
        "channel": "manual_lookup",
        "observed_name": "Acme",
        "observed_domain": "acme.com",
        "source_metadata": {"operator_confirmed_identity": True},
        "resolution_payload": {
            "resolution_status": "FOUND",
            "confidence": 0.94,
            "website": "https://acme.com",
            "candidates": [],
        },
    }
    values.update(overrides)
    return SourceObservationInput(**values)


@pytest.mark.asyncio
async def test_exact_verified_identifier_match_attaches_to_existing_company():
    repository = _Repository(
        matches=[
            {
                "company_id": "company-existing",
                "canonical_name": "Acme",
                "canonical_domain": "acme.com",
                "confidence": 1.0,
            }
        ]
    )

    admission = await IdentityService(repository).admit(_observation())

    assert admission.company_id == "company-existing"
    assert admission.blocks_evaluation is False
    assert any(call[0] == "resolve" for call in repository.calls)
    assert not any(call[0] == "create" for call in repository.calls)


@pytest.mark.asyncio
async def test_picker_confirmed_new_domain_creates_company_and_opportunity():
    repository = _Repository()

    admission = await IdentityService(repository).admit(_observation())

    assert admission.company_id == "company-new"
    assert admission.opportunity_id == "opportunity-new"
    assert admission.created is True


@pytest.mark.asyncio
async def test_same_name_without_safe_identifier_opens_case_instead_of_merging():
    repository = _Repository()
    observation = _observation(
        observed_domain=None,
        source_metadata={},
        resolution_payload={"resolution_status": "LOW_CONFIDENCE", "confidence": 0.4},
    )

    admission = await IdentityService(repository).admit(observation)

    assert admission.status is IdentityStatus.AMBIGUOUS
    assert admission.blocks_evaluation is True
    find = next(call for call in repository.calls if call[0] == "find")
    assert find[1]["identifiers"] == []


@pytest.mark.asyncio
async def test_two_strong_picker_candidates_open_case():
    repository = _Repository()
    observation = _observation(
        observed_domain=None,
        source_metadata={},
        resolution_payload={
            "resolution_status": "NEEDS_REVIEW",
            "confidence": 0.81,
            "candidates": [
                {"name": "Acme", "website": "https://acme.com", "confidence": 0.92},
                {"name": "Acme", "website": "https://acme.io", "confidence": 0.9},
            ],
        },
    )

    admission = await IdentityService(repository).admit(observation)

    assert admission.identity_case_id == "case-1"
    assert {candidate.canonical_domain for candidate in admission.candidates} == {
        "acme.com",
        "acme.io",
    }


@pytest.mark.asyncio
async def test_one_strong_picker_candidate_can_create_without_a_name_merge():
    repository = _Repository()
    observation = _observation(
        observed_domain=None,
        source_metadata={},
        resolution_payload={
            "resolution_status": "FOUND",
            "confidence": 0.91,
            "candidates": [
                {"name": "Acme", "website": "https://acme.dev", "confidence": 0.91}
            ],
        },
    )

    admission = await IdentityService(repository).admit(observation)

    assert admission.created is True
    create = next(call for call in repository.calls if call[0] == "create")
    assert create[1]["canonical_domain"] == "acme.dev"


@pytest.mark.asyncio
async def test_conflicting_verified_identifiers_never_auto_merge():
    repository = _Repository(
        matches=[
            {"company_id": "company-a", "canonical_name": "Acme A", "confidence": 1.0},
            {"company_id": "company-b", "canonical_name": "Acme B", "confidence": 1.0},
        ]
    )

    admission = await IdentityService(repository).admit(_observation())

    assert admission.status is IdentityStatus.AMBIGUOUS
    assert admission.blocks_evaluation is True


@pytest.mark.asyncio
async def test_idempotent_observation_returns_existing_admission():
    existing = IdentityAdmission(
        user_id="fund-a",
        observation_id="observation-1",
        status="resolved",
        company_id="company-existing",
        opportunity_id="opportunity-existing",
        confidence=1,
    )
    repository = _Repository(existing_admission=existing)

    admission = await IdentityService(repository).admit(_observation())

    assert admission == existing
    assert not any(call[0] in {"find", "create", "case"} for call in repository.calls)
