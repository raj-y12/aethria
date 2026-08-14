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
        "opportunity_id": None,
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
    legacy_startup_id = "bc9ccd98-ba8d-46d4-9c4d-5f0c6925d02a"
    connection = _Connection(
        fetchrows=[
            _company_row(),
            _opportunity_row(legacy_startup_id=legacy_startup_id),
        ]
    )
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
    assert "set opportunity_id = $3" in sql
    assert "update public.source_observations" in sql
    assert "insert into public.domain_outbox" in sql
    assert "observation_resolved" in str(connection.calls)
    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == legacy_startup_id
    assert payload["compatibility_reason"] == "canonical identity resolved"


@pytest.mark.asyncio
async def test_admission_replay_uses_stable_observation_opportunity_link():
    admission_row = _observation_row(
        company_id=_company_row()["company_id"],
        opportunity_id=_opportunity_row()["opportunity_id"],
        linked_opportunity_id=_opportunity_row()["opportunity_id"],
        identity_status="resolved",
        identity_confidence=1,
    )
    connection = _Connection(fetchrows=[admission_row])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.get_admission_for_observation(
        user_id="fund-a", observation_id=_observation_row()["observation_id"]
    )

    assert result is not None
    assert result.opportunity_id == _opportunity_row()["opportunity_id"]
    sql = connection.calls[0][1].lower()
    assert "p.opportunity_id = o.opportunity_id" in sql
    assert "p.latest_observation_id = o.observation_id" not in sql


@pytest.mark.asyncio
async def test_resolved_historical_observation_without_stable_link_blocks_replay():
    admission_row = _observation_row(
        company_id=_company_row()["company_id"],
        opportunity_id=None,
        linked_opportunity_id=None,
        identity_status="resolved",
        identity_confidence=1,
    )
    repository = IdentityRepository(_Pool(_Connection(fetchrows=[admission_row])))

    result = await repository.get_admission_for_observation(
        user_id="fund-a", observation_id=_observation_row()["observation_id"]
    )

    assert result is not None
    assert result.status is IdentityStatus.RESOLVED
    assert result.opportunity_id is None
    assert result.blocks_evaluation is True


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
async def test_linked_legacy_projection_ids_are_tenant_scoped():
    connection = _Connection(
        fetches=[[{"legacy_startup_id": "11111111-1111-4111-8111-111111111111"}]]
    )
    repository = IdentityRepository(_Pool(connection))

    result = await repository.list_linked_legacy_startup_ids(user_id="fund-a")

    assert result == ["11111111-1111-4111-8111-111111111111"]
    assert "where user_id=$1" in connection.calls[0][1].lower()


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


@pytest.mark.asyncio
async def test_operator_create_from_case_is_one_transactional_resolution():
    case_row = {
        "identity_case_id": "5fefdc39-aef8-4993-b356-95cb927027ef",
        "user_id": "fund-a",
        "observation_id": _observation_row()["observation_id"],
        "status": "open",
        "reason_code": "insufficient_verified_identifier",
        "candidates": json.dumps([]),
        "selected_company_id": None,
        "resolution_note": None,
        "resolved_by": None,
        "resolved_at": None,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
    }
    connection = _Connection(
        fetchrows=[case_row, _observation_row(identity_status="ambiguous"), _company_row(), _opportunity_row()]
    )
    repository = IdentityRepository(_Pool(connection))

    result = await repository.create_company_from_case(
        user_id="fund-a",
        identity_case_id=case_row["identity_case_id"],
        canonical_name="Acme",
        canonical_domain="https://acme.com",
        resolved_by="operator-1",
    )

    assert result.status is IdentityStatus.RESOLVED
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "for update" in sql
    assert "insert into public.companies" in sql
    assert "verification_status" in sql
    assert "insert into public.opportunities" in sql
    assert "update public.identity_resolution_cases" in sql
    assert "identity_case.resolved" in str(connection.calls)


def _case_group_row(*, case_id, observed_domain, observed_name="Acme", channel="manual_lookup", **overrides):
    row = {
        "identity_case_id": case_id,
        "user_id": "fund-a",
        "observation_id": case_id,  # distinct per row for this fixture's purposes
        "status": "open",
        "reason_code": "insufficient_verified_identifier",
        "candidates": json.dumps([]),
        "selected_company_id": None,
        "resolution_note": None,
        "resolved_by": None,
        "resolved_at": None,
        "created_at": _input().observed_at,
        "updated_at": _input().observed_at,
        "observed_domain": observed_domain,
        "observed_name": observed_name,
        "channel": channel,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_two_observations_with_the_same_verified_domain_produce_one_group():
    rows = [
        _case_group_row(case_id="case-1", observed_domain="acme.com", observed_name="Acme Inc"),
        _case_group_row(case_id="case-2", observed_domain="https://www.acme.com/about", observed_name="Acme"),
    ]
    connection = _Connection(fetches=[rows])
    repository = IdentityRepository(_Pool(connection))

    groups = await repository.list_case_groups(user_id="fund-a", status="open")

    assert len(groups) == 1
    group = groups[0]
    assert group.canonical_domain == "acme.com"
    assert len(group.cases) == 2
    assert {case.identity_case_id for case in group.cases} == {"case-1", "case-2"}
    assert set(group.observed_names) == {"Acme Inc", "Acme"}


@pytest.mark.asyncio
async def test_two_observations_matching_only_on_ambiguous_name_stay_ungrouped():
    rows = [
        _case_group_row(case_id="case-1", observed_domain=None, observed_name="Acme"),
        _case_group_row(case_id="case-2", observed_domain=None, observed_name="Acme"),
    ]
    connection = _Connection(fetches=[rows])
    repository = IdentityRepository(_Pool(connection))

    groups = await repository.list_case_groups(user_id="fund-a", status="open")

    assert len(groups) == 2
    assert all(group.canonical_domain is None for group in groups)
    assert all(len(group.cases) == 1 for group in groups)
    assert groups[0].group_key != groups[1].group_key


@pytest.mark.asyncio
async def test_three_observations_two_share_a_domain_one_does_not():
    rows = [
        _case_group_row(case_id="case-1", observed_domain="acme.com"),
        _case_group_row(case_id="case-2", observed_domain="acme.com"),
        _case_group_row(case_id="case-3", observed_domain="other.com", observed_name="Other Co"),
    ]
    connection = _Connection(fetches=[rows])
    repository = IdentityRepository(_Pool(connection))

    groups = await repository.list_case_groups(user_id="fund-a", status="open")

    assert len(groups) == 2
    acme_group = next(g for g in groups if g.canonical_domain == "acme.com")
    other_group = next(g for g in groups if g.canonical_domain == "other.com")
    assert len(acme_group.cases) == 2
    assert len(other_group.cases) == 1


class _ConflictInsertConnection:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, sql, *args):
        self.connection.calls.append(("execute", sql, args))
        if "insert into public.company_identifiers" in sql.lower():
            return "INSERT 0 0"
        return "OK"


@pytest.mark.asyncio
async def test_decision_cases_preserve_historical_evaluation_episodes():
    opportunity = _opportunity_row(
        decision_state="invested",
        current_evaluation_id="evaluation-2",
        current_recommendation_id="recommendation-2",
        current_ruling_id="ruling-2",
        updated_at="current-opportunity-update",
    )
    base = {
        **opportunity,
        "canonical_name": "Acme Current Name",
        "canonical_domain": "current.acme.com",
    }
    evaluations = [
        {
            "evaluation_id": "evaluation-1",
            "opportunity_id": opportunity["opportunity_id"],
            "evidence_snapshot_hash": "evidence-hash-1",
            "evidence_materiality_digest": "materiality-1",
            "claim_snapshot": json.dumps([{"claim_id": "claim-old", "display_text": "Old evidence"}]),
            "thesis_version_id": "thesis-1",
            "policy_version_id": "policy-1",
            "policy_hash": "policy-hash-1",
            "rubric_version": "rubric-1",
            "partner_rules_version": "rules-1",
            "partner_rules_hash": "rules-hash-1",
            "model_manifest": json.dumps({"model": "old"}),
            "prompt_manifest": json.dumps({"prompt": "old"}),
            "status": "completed",
            "created_at": "2026-01-01T10:00:00+00:00",
            "completed_at": "2026-01-01T10:05:00+00:00",
        },
        {
            "evaluation_id": "evaluation-2",
            "opportunity_id": opportunity["opportunity_id"],
            "evidence_snapshot_hash": "evidence-hash-2",
            "evidence_materiality_digest": "materiality-2",
            "claim_snapshot": json.dumps([{"claim_id": "claim-new", "display_text": "New evidence"}]),
            "thesis_version_id": "thesis-2",
            "policy_version_id": "policy-2",
            "policy_hash": "policy-hash-2",
            "rubric_version": "rubric-2",
            "partner_rules_version": "rules-2",
            "partner_rules_hash": "rules-hash-2",
            "model_manifest": json.dumps({"model": "new"}),
            "prompt_manifest": json.dumps({"prompt": "new"}),
            "status": "completed",
            "created_at": "2026-02-01T10:00:00+00:00",
            "completed_at": "2026-02-01T10:05:00+00:00",
        },
    ]
    recommendations = [
        {
            "recommendation_id": "recommendation-1",
            "evaluation_id": "evaluation-1",
            "recommended_state": "pass",
            "attention_priority": 50,
            "recommendation_confidence": 0.53,
            "decision_drivers": json.dumps(["old driver"]),
            "principal_risks": json.dumps(["old risk"]),
            "mandate_conflicts": json.dumps([]),
            "missing_information": json.dumps([]),
            "change_conditions": json.dumps([]),
            "human_review_required": True,
            "change_explanation": None,
            "created_at": "2026-01-01T10:06:00+00:00",
        },
        {
            "recommendation_id": "recommendation-2",
            "evaluation_id": "evaluation-2",
            "recommended_state": "advance",
            "attention_priority": 80,
            "recommendation_confidence": 0.82,
            "decision_drivers": json.dumps(["new driver"]),
            "principal_risks": json.dumps(["new risk"]),
            "mandate_conflicts": json.dumps([]),
            "missing_information": json.dumps([]),
            "change_conditions": json.dumps([]),
            "human_review_required": True,
            "change_explanation": "New evidence changed the recommendation.",
            "created_at": "2026-02-01T10:06:00+00:00",
        },
    ]
    criteria = [
        {"evaluation_id": "evaluation-1", "criterion": "technical", "score": 5,
         "confidence": 0.6, "evidence_sufficiency": "partial", "reasoning": "old",
         "supporting_claim_ids": json.dumps(["claim-old"]), "contradicting_claim_ids": json.dumps([]),
         "missing_evidence": json.dumps([]), "quality_flags": json.dumps([]),
         "deterministic_adjustments": json.dumps({})},
        {"evaluation_id": "evaluation-2", "criterion": "technical", "score": 9,
         "confidence": 0.9, "evidence_sufficiency": "sufficient", "reasoning": "new",
         "supporting_claim_ids": json.dumps(["claim-new"]), "contradicting_claim_ids": json.dumps([]),
         "missing_evidence": json.dumps([]), "quality_flags": json.dumps([]),
         "deterministic_adjustments": json.dumps({})},
    ]
    rulings = [
        {"ruling_id": "ruling-1", "recommendation_id": "recommendation-1", "decision": "pass",
         "rationale": "Old ruling", "risk_acknowledgement": None, "mandate_exception": None,
         "investor_confidence": 0.6, "actor_id": "fund-a", "prior_ruling_id": None,
         "created_at": "2026-01-02T10:00:00+00:00", "override_type": "timing", "override_note": "Old"},
        {"ruling_id": "ruling-2", "recommendation_id": "recommendation-2", "decision": "invest",
         "rationale": "New ruling", "risk_acknowledgement": None, "mandate_exception": None,
         "investor_confidence": 0.82, "actor_id": "fund-a", "prior_ruling_id": "ruling-1",
         "created_at": "2026-02-02T10:00:00+00:00", "override_type": "policy_disagreement", "override_note": "New"},
        {"ruling_id": "ruling-unpaired", "recommendation_id": None, "decision": "monitor",
         "rationale": "No deterministic recommendation link", "risk_acknowledgement": None,
         "mandate_exception": None, "investor_confidence": 0.5, "actor_id": "fund-a",
         "prior_ruling_id": "ruling-2", "created_at": "2026-02-03T10:00:00+00:00",
         "override_type": None, "override_note": None},
    ]
    outcomes = [{
        "outcome_observation_id": "outcome-1", "company_id": opportunity["company_id"],
        "opportunity_id": opportunity["opportunity_id"], "outcome_type": "financing",
        "valence": "positive", "summary": "Raised a subsequent round",
        "verification_state": "verified", "materiality": 4,
        "effective_at": "2026-03-01T10:00:00+00:00", "observed_at": "2026-03-02T10:00:00+00:00",
        "supersedes_outcome_id": None,
    }]
    interpretations = [{
        "interpretation_id": "interpretation-1", "ruling_id": "ruling-1",
        "opportunity_id": opportunity["opportunity_id"], "recommendation_id": "recommendation-1",
        "evaluation_id": "evaluation-1", "version": 1, "source": "aethria_inferred",
        "status": "complete", "rationale_sha256": "rationale-hash",
        "extraction_confidence": 0.75, "positive_factors": json.dumps([{"text": "Old"}]),
        "negative_factors": json.dumps([]), "accepted_risks": json.dumps([]),
        "decisive_factors": json.dumps([]), "overridden_criteria": json.dumps([]),
        "strategic_exception": None, "agreement_with_aethria": "disagree",
        "human_confidence": 0.6,
        "evidence_influence": json.dumps({"status": "unknown", "references": [], "limitations": []}),
        "provenance": json.dumps({"extractor": "rules-v1"}), "correction_note": None,
        "supersedes_interpretation_id": None, "created_at": "2026-01-03T10:00:00+00:00",
    }]
    connection = _Connection(
        fetchrows=[base], fetches=[evaluations, recommendations, criteria, rulings, interpretations, outcomes]
    )
    repository = IdentityRepository(_Pool(connection))

    result = await repository.get_decision_cases(
        user_id="fund-a", opportunity_id=opportunity["opportunity_id"]
    )

    assert [case["evaluation"]["evaluation_id"] for case in result["cases"]] == [
        "evaluation-1", "evaluation-2"
    ]
    assert result["cases"][0]["recommendation"]["recommendation_id"] == "recommendation-1"
    assert result["cases"][0]["rulings"][0]["ruling_id"] == "ruling-1"
    assert result["cases"][0]["rulings"][0]["interpretation"]["interpretation_id"] == "interpretation-1"
    assert result["cases"][1]["rulings"][0]["ruling_id"] == "ruling-2"
    assert result["cases"][0]["decision_time"] == "2026-01-01T10:05:00+00:00"
    assert result["cases"][0]["evaluation"]["claim_snapshot"][0]["claim_id"] == "claim-old"
    assert result["cases"][1]["evaluation"]["claim_snapshot"][0]["claim_id"] == "claim-new"
    assert result["cases"][0]["evaluation"]["evidence_materiality_digest"] == "materiality-1"
    assert result["current_lifecycle"]["decision_state"] == "invested"
    assert result["current_lifecycle"]["updated_at"] == "current-opportunity-update"
    assert result["outcomes"][0]["outcome_type"] == "financing"
    assert "outcomes" not in result["cases"][0]
    assert result["unpaired_rulings"][0]["ruling_id"] == "ruling-unpaired"
    assert all("user_id" not in row for row in result["outcomes"])

    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert sql.count("user_id=$1") >= 5
    assert "opportunity_id=$2" in sql


@pytest.mark.asyncio
async def test_decision_view_exposes_canonical_ruling_history_for_memo_reads():
    row = {
        **_opportunity_row(
            decision_state="active_review",
            current_ruling_id="ruling-advanced",
        ),
        "canonical_name": "Advanced Co",
        "canonical_domain": "advanced.example",
        "recommended_state": "advance",
        "recommendation_confidence": 0.8,
        "decision_drivers": json.dumps(["customer evidence"]),
        "principal_risks": json.dumps([]),
        "missing_information": json.dumps([]),
        "change_conditions": json.dumps([]),
        "current_ruling_decision": "advance",
        "ruling_history": json.dumps([{
            "ruling_id": "ruling-advanced",
            "decision": "advance",
            "rationale": "Advance to diligence.",
            "created_at": "2026-08-11T10:00:00Z",
        }]),
    }
    connection = _Connection(fetchrows=[row])
    repository = IdentityRepository(_Pool(connection))

    result = await repository.get_decision_view(
        user_id="fund-a", opportunity_id=row["opportunity_id"]
    )

    assert result["ruling_history"][0]["decision"] == "advance"
    assert result["ruling_history"][0]["rationale"] == "Advance to diligence."
