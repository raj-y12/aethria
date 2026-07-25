from fastapi.testclient import TestClient
import pytest

from identity.models import (
    CompanyRecord,
    IdentityAdmission,
    IdentityCaseStatus,
    IdentityResolutionCaseRecord,
    IdentityStatus,
    OpportunityRecord,
    SourceChannel,
    SourceObservationRecord,
)
from authority.models import RolloutMode, RolloutRecord
from authority.service import AuthorityService
from security.rate_limiter import InMemorySecurityStore
from utils.timeutil import utcnow


NOW = utcnow()
LEGACY_STARTUP_ID = "d3d44fa8-6f39-4d8c-bcf4-f979a0fc0cf1"


class _Repository:
    def __init__(self):
        self.company = CompanyRecord(
            company_id="5a75bade-5807-474f-a6aa-4c02da080cf6",
            user_id="user-a",
            canonical_name="Acme",
            canonical_domain="acme.com",
            identity_confidence=1,
            metadata={"private_note": "do not expose"},
        )
        self.observation = SourceObservationRecord(
            observation_id="0f344581-8b14-461f-ab71-3aafe2e06f11",
            user_id="user-a",
            channel=SourceChannel.MANUAL_LOOKUP,
            observed_name="Acme",
            observed_domain="acme.com",
            identity_status=IdentityStatus.AMBIGUOUS,
            source_metadata={"private_note": "do not expose"},
        )
        self.opportunity = OpportunityRecord(
            opportunity_id="03a37384-94cc-4d1e-b5c6-b77b40d2e8cc",
            user_id="user-a",
            company_id=self.company.company_id,
            first_observation_id=self.observation.observation_id,
            latest_observation_id=self.observation.observation_id,
            legacy_startup_id=LEGACY_STARTUP_ID,
        )
        self.case = IdentityResolutionCaseRecord(
            identity_case_id="5fefdc39-aef8-4993-b356-95cb927027ef",
            user_id="user-a",
            observation_id=self.observation.observation_id,
            status=IdentityCaseStatus.OPEN,
            reason_code="multiple_strong_candidates",
            candidates=[
                {
                    "company_id": self.company.company_id,
                    "canonical_name": "Acme",
                    "canonical_domain": "acme.com",
                    "confidence": 0.9,
                    "evidence_urls": ["https://acme.com"],
                }
            ],
        )
        self.actions = []

    async def get_company(self, *, user_id, company_id):
        return self.company if user_id == self.company.user_id and company_id == self.company.company_id else None

    async def get_opportunity(self, *, user_id, opportunity_id):
        return self.opportunity if user_id == self.opportunity.user_id and opportunity_id == self.opportunity.opportunity_id else None

    async def get_opportunity_by_legacy_projection(self, *, user_id, legacy_startup_id):
        if user_id != self.opportunity.user_id or legacy_startup_id != self.opportunity.legacy_startup_id:
            return None
        return self.opportunity

    async def list_observations(self, *, user_id, status=None, limit=100):
        return [self.observation] if user_id == "user-a" else []

    async def list_cases(self, *, user_id, status="open", limit=100):
        return [self.case] if user_id == "user-a" and self.case.status.value == status else []

    async def get_case(self, *, user_id, identity_case_id):
        return self.case if user_id == "user-a" and identity_case_id == self.case.identity_case_id else None

    async def get_admission_for_observation(self, *, user_id, observation_id):
        if self.case.status is not IdentityCaseStatus.RESOLVED:
            return None
        return IdentityAdmission(
            user_id="user-a",
            observation_id=observation_id,
            status=IdentityStatus.RESOLVED,
            company_id=self.company.company_id,
            opportunity_id=self.opportunity.opportunity_id,
            identity_case_id=self.case.identity_case_id,
            confidence=1,
        )

    async def resolve_case(self, **kwargs):
        self.actions.append(("match", kwargs))
        self.case = self.case.model_copy(
            update={
                "status": IdentityCaseStatus.RESOLVED,
                "selected_company_id": kwargs["selected_company_id"],
                "resolved_by": kwargs["resolved_by"],
            }
        )
        return await self.get_admission_for_observation(
            user_id=kwargs["user_id"], observation_id=self.case.observation_id
        )

    async def create_company_from_case(self, **kwargs):
        self.actions.append(("create", kwargs))
        return await self.resolve_case(
            user_id=kwargs["user_id"],
            identity_case_id=kwargs["identity_case_id"],
            selected_company_id=self.company.company_id,
            resolved_by=kwargs["resolved_by"],
            resolution_note=kwargs.get("resolution_note"),
        )

    async def defer_case(self, **kwargs):
        self.actions.append(("defer", kwargs))
        self.case = self.case.model_copy(update={"status": IdentityCaseStatus.DEFERRED})
        return self.case

    async def reject_case(self, **kwargs):
        self.actions.append(("reject", kwargs))
        self.case = self.case.model_copy(update={"status": IdentityCaseStatus.REJECTED})
        return self.case


class _AuthorityRepository:
    def __init__(self, rollout):
        self.rollout = rollout

    async def get_rollout(self, *, user_id):
        assert user_id == self.rollout.user_id
        return self.rollout


def _authority(mode=RolloutMode.LEGACY):
    return AuthorityService(
        _AuthorityRepository(
            RolloutRecord(user_id="user-a", mode=mode, version=2)
        )
    )


def _client(monkeypatch, repository, *, user_id="user-a", authority_service=None):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda token: user_id)
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.identity_repository = repository
    api.app.state.authority_service = authority_service or _authority()
    return TestClient(api.app)


def test_company_and_opportunity_reads_are_tenant_scoped_and_safe(monkeypatch):
    repository = _Repository()
    own = _client(monkeypatch, repository)
    company = own.get(
        f"/api/companies/{repository.company.company_id}",
        headers={"Authorization": "Bearer t"},
    )
    opportunity = own.get(
        f"/api/opportunities/{repository.opportunity.opportunity_id}",
        headers={"Authorization": "Bearer t"},
    )

    assert company.status_code == opportunity.status_code == 200
    assert "private_note" not in company.text
    other = _client(monkeypatch, repository, user_id="user-b").get(
        f"/api/companies/{repository.company.company_id}",
        headers={"Authorization": "Bearer t"},
    )
    assert other.status_code == 404


def test_legacy_startup_resolves_to_tenant_scoped_canonical_opportunity(monkeypatch):
    repository = _Repository()
    own = _client(monkeypatch, repository).get(
        f"/api/startups/{LEGACY_STARTUP_ID}/opportunity",
        headers={"Authorization": "Bearer t"},
    )
    other = _client(monkeypatch, repository, user_id="user-b").get(
        f"/api/startups/{LEGACY_STARTUP_ID}/opportunity",
        headers={"Authorization": "Bearer t"},
    )

    assert own.status_code == 200
    assert own.json()["opportunity_id"] == repository.opportunity.opportunity_id
    assert own.json()["legacy_startup_id"] == LEGACY_STARTUP_ID
    assert other.status_code == 404


def test_observation_and_case_lists_are_bounded_and_hide_raw_metadata(monkeypatch):
    client = _client(monkeypatch, _Repository())
    observations = client.get(
        "/api/observations?limit=10", headers={"Authorization": "Bearer t"}
    )
    cases = client.get(
        "/api/identity-cases?limit=10", headers={"Authorization": "Bearer t"}
    )

    assert observations.status_code == cases.status_code == 200
    assert "private_note" not in observations.text
    assert cases.json()["cases"][0]["candidates"][0]["evidence_urls"] == [
        "https://acme.com"
    ]
    too_many = client.get(
        "/api/observations?limit=1000", headers={"Authorization": "Bearer t"}
    )
    assert too_many.status_code == 422


def test_operator_can_match_create_defer_and_reject_with_server_actor(monkeypatch):
    repository = _Repository()
    client = _client(monkeypatch, repository)
    case_id = repository.case.identity_case_id

    matched = client.post(
        f"/api/identity-cases/{case_id}/resolve",
        headers={"Authorization": "Bearer t"},
        json={"action": "match", "selected_company_id": repository.company.company_id},
    )
    repeated = client.post(
        f"/api/identity-cases/{case_id}/resolve",
        headers={"Authorization": "Bearer t"},
        json={"action": "match", "selected_company_id": repository.company.company_id},
    )

    assert matched.status_code == repeated.status_code == 200
    assert repository.actions[0][1]["resolved_by"] == "user-a"
    assert len([action for action in repository.actions if action[0] == "match"]) == 1

    for action in ("create", "defer", "reject"):
        fresh = _Repository()
        local = _client(monkeypatch, fresh)
        body = {"action": action}
        if action == "create":
            body.update({"canonical_name": "Acme", "canonical_domain": "acme.com"})
        response = local.post(
            f"/api/identity-cases/{fresh.case.identity_case_id}/resolve",
            headers={"Authorization": "Bearer t"},
            json=body,
        )
        assert response.status_code == 200
        assert fresh.actions[0][0] == action


def test_resolution_rejects_invalid_action_shape_without_database_details(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        f"/api/identity-cases/{repository.case.identity_case_id}/resolve",
        headers={"Authorization": "Bearer t"},
        json={"action": "match"},
    )

    assert response.status_code == 422
    assert repository.actions == []


@pytest.mark.parametrize(
    ("mode", "canonical_writes_allowed"),
    [(RolloutMode.LEGACY, False), (RolloutMode.SHADOW, True)],
)
def test_identity_resolution_keeps_legacy_shape_and_adds_authority_metadata(
    monkeypatch, mode, canonical_writes_allowed
):
    repository = _Repository()
    response = _client(
        monkeypatch, repository, authority_service=_authority(mode)
    ).post(
        f"/api/identity-cases/{repository.case.identity_case_id}/resolve",
        headers={"Authorization": "Bearer t"},
        json={"action": "match", "selected_company_id": repository.company.company_id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["authority"] == {
        "mode": mode.value,
        "version": 2,
        "kill_switch": False,
        "canonical_writes_allowed": canonical_writes_allowed,
        "canonical_reads_allowed": False,
        "last_reconciliation_status": None,
    }
    assert repository.actions[0][0] == "match"


def test_identity_resolution_is_blocked_before_mutation_in_canonical_read(monkeypatch):
    repository = _Repository()
    response = _client(
        monkeypatch,
        repository,
        authority_service=_authority(RolloutMode.CANONICAL_READ),
    ).post(
        f"/api/identity-cases/{repository.case.identity_case_id}/resolve",
        headers={"Authorization": "Bearer t"},
        json={"action": "match", "selected_company_id": repository.company.company_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTHORITY_CANONICAL_ONLY"
    assert repository.actions == []
