import json
from collections import deque

import pytest

from identity.models import (
    IdentityCandidate,
    IdentityStatus,
    IdentifierType,
    NormalizedIdentifier,
    SourceObservationInput,
    VerificationStatus,
)
from identity.repository import IdentityRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, *, fetchrows=(), fetches=()):
        self.fetchrows = deque(fetchrows)
        self.fetches = deque(fetches)
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.popleft() if self.fetchrows else None

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self.fetches.popleft() if self.fetches else []

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "OK"


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


def _input(**overrides):
    values = {
        "user_id": "fund-a",
        "channel": "manual_lookup",
        "observed_name": "Acme",
        "observed_domain": "acme.com",
        "external_event_key": "lookup-1",
        "lookup_id": "lookup-1",
        "source_metadata": {"source": "dispatch"},
    }
    values.update(overrides)
    return SourceObservationInput(**values)


def _observation_row(**overrides):
    row = {
        "observation_id": "0f344581-8b14-461f-ab71-3aafe2e06f11",
        "user_id": "fund-a",
        "channel": "manual_lookup",
        "observed_name": "Acme",
        "observed_domain": "acme.com",
        "external_event_key": "lookup-1",
        "lookup_id": "lookup-1",
        "legacy_startup_id": None,
        "company_id": None,
        "identity_status": "pending",
        "identity_confidence": 0,
        "provider_identifiers": json.dumps({}),
        "source_metadata": json.dumps({"source": "dispatch"}),
        "resolution_payload": None,
        "observed_at": _input().observed_at,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    row.update(overrides)
    return row


def _company_row(**overrides):
    row = {
        "company_id": "5a75bade-5807-474f-a6aa-4c02da080cf6",
        "user_id": "fund-a",
        "canonical_name": "Acme",
        "canonical_domain": "acme.com",
        "identity_confidence": 1.0,
        "status": "active",
        "metadata": json.dumps({}),
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    row.update(overrides)
    return row


def _opportunity_row(**overrides):
    row = {
        "opportunity_id": "03a37384-94cc-4d1e-b5c6-b77b40d2e8cc",
        "user_id": "fund-a",
        "company_id": _company_row()["company_id"],
        "context_key": "primary",
        "decision_state": "discovered",
        "service_level": 1,
        "first_observation_id": _observation_row()["observation_id"],
        "latest_observation_id": _observation_row()["observation_id"],
        "legacy_startup_id": None,
        "current_evaluation_id": None,
        "current_recommendation_id": None,
        "current_ruling_id": None,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    row.update(overrides)
    return row


def _domain():
    return NormalizedIdentifier(
        identifier_type=IdentifierType.DOMAIN,
        normalized_value="acme.com",
        raw_value="https://acme.com",
        verification_status=VerificationStatus.VERIFIED,
        confidence=1,
        is_primary=True,
    )


@pytest.mark.asyncio
async def test_record_observation_is_tenant_idempotent_by_external_event():
    connection = _Connection(fetchrows=[None, _observation_row()])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.record_observation(_input())

    assert result.observation_id == _observation_row()["observation_id"]
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "insert into public.source_observations" in sql
    assert "on conflict (user_id, channel, external_event_key)" in sql
    assert "where external_event_key is not null" in sql
    assert "user_id = $1" in sql


@pytest.mark.asyncio
async def test_company_admission_commits_identity_opportunity_and_outbox_together():
    connection = _Connection(fetchrows=[_company_row(), _opportunity_row()])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.create_company_admission(
        observation=_input(),
        observation_id=_observation_row()["observation_id"],
        identifiers=[_domain()],
        confidence=1,
    )

    assert result.status is IdentityStatus.RESOLVED
    assert result.company_id == _company_row()["company_id"]
    assert result.opportunity_id == _opportunity_row()["opportunity_id"]
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "insert into public.companies" in sql
    assert "insert into public.company_identifiers" in sql
    assert "insert into public.company_aliases" in sql
    assert "insert into public.opportunities" in sql
    assert "update public.source_observations" in sql
    assert "insert into public.domain_outbox" in sql
    assert "observation_resolved" in str(connection.calls)


@pytest.mark.asyncio
async def test_ambiguity_case_creates_no_company_or_opportunity():
    case_row = {
        "identity_case_id": "5fefdc39-aef8-4993-b356-95cb927027ef",
        "user_id": "fund-a",
        "observation_id": _observation_row()["observation_id"],
        "status": "open",
        "reason_code": "multiple_strong_candidates",
        "candidates": json.dumps([]),
        "selected_company_id": None,
        "resolution_note": None,
        "resolved_by": None,
        "resolved_at": None,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    connection = _Connection(fetchrows=[case_row])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.open_identity_case(
        observation=_input(),
        observation_id=_observation_row()["observation_id"],
        candidates=[IdentityCandidate(canonical_name="Acme", canonical_domain="acme.com")],
        reason_code="multiple_strong_candidates",
        confidence=0.8,
    )

    assert result.blocks_evaluation is True
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "insert into public.identity_resolution_cases" in sql
    assert "insert into public.companies" not in sql
    assert "insert into public.opportunities" not in sql


@pytest.mark.asyncio
async def test_verified_identifier_lookup_is_tenant_scoped():
    connection = _Connection(
        fetches=[
            [
                {
                    "company_id": _company_row()["company_id"],
                    "canonical_name": "Acme",
                    "canonical_domain": "acme.com",
                    "confidence": 1.0,
                }
            ]
        ]
    )
    repository = IdentityRepository(_Pool(connection))

    matches = await repository.find_companies_by_verified_identifiers(
        user_id="fund-a", identifiers=[_domain()]
    )

    assert matches[0]["company_id"] == _company_row()["company_id"]
    sql = connection.calls[0][1].lower()
    assert "ci.user_id = $1" in sql
    assert "verification_status = 'verified'" in sql


@pytest.mark.asyncio
async def test_projection_link_is_conditional_tenant_scoped_and_idempotent():
    connection = _Connection(fetchrows=[_opportunity_row(legacy_startup_id="11111111-1111-4111-8111-111111111111")])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.link_legacy_projection(
        user_id="fund-a",
        opportunity_id=_opportunity_row()["opportunity_id"],
        legacy_startup_id="11111111-1111-4111-8111-111111111111",
    )

    assert result.legacy_startup_id == "11111111-1111-4111-8111-111111111111"
    sql = connection.calls[0][1].lower()
    assert "user_id = $2" in sql
    assert "legacy_startup_id is null or legacy_startup_id = $3" in sql


@pytest.mark.asyncio
async def test_cross_tenant_company_read_returns_none():
    connection = _Connection(fetchrows=[None])
    repository = IdentityRepository(_Pool(connection))

    assert await repository.get_company(
        user_id="fund-b", company_id=_company_row()["company_id"]
    ) is None
    assert "user_id = $2" in connection.calls[0][1].lower()


@pytest.mark.asyncio
async def test_operator_case_resolution_links_existing_company_and_opportunity():
    observation = _observation_row(observed_name="Acme Labs")
    case = {
        "identity_case_id": "5fefdc39-aef8-4993-b356-95cb927027ef",
        "user_id": "fund-a",
        "observation_id": observation["observation_id"],
        "status": "resolved",
        "reason_code": "multiple_strong_candidates",
        "candidates": json.dumps([]),
        "selected_company_id": _company_row()["company_id"],
        "resolution_note": "Confirmed from founder email",
        "resolved_by": "operator-1",
        "resolved_at": _input().observed_at,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    connection = _Connection(
        fetchrows=[case, observation, _company_row(), _opportunity_row()]
    )
    repository = IdentityRepository(_Pool(connection))

    result = await repository.resolve_case(
        user_id="fund-a",
        identity_case_id=case["identity_case_id"],
        selected_company_id=_company_row()["company_id"],
        resolved_by="operator-1",
        resolution_note="Confirmed from founder email",
    )

    assert result.status is IdentityStatus.RESOLVED
    assert result.company_id == _company_row()["company_id"]
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "for update" in sql
    assert "identity_case.resolved" in str(connection.calls)
    assert "user_id = $2" in sql


@pytest.mark.asyncio
async def test_verified_identifier_conflict_fails_closed():
    connection = _Connection(
        fetchrows=[
            _company_row(),
            {"company_id": "62d0143b-083d-4b93-9e04-3c6fcc32e2f3"},
        ]
    )
    connection.execute = _ConflictInsertConnection(connection).execute
    repository = IdentityRepository(_Pool(connection))

    with pytest.raises(RuntimeError, match="another company"):
        await repository.create_company_admission(
            observation=_input(),
            observation_id=_observation_row()["observation_id"],
            identifiers=[_domain()],
            confidence=1,
        )


class _ConflictInsertConnection:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, sql, *args):
        self.connection.calls.append(("execute", sql, args))
        if "insert into public.company_identifiers" in sql.lower():
            return "INSERT 0 0"
        return "OK"
