from fastapi.testclient import TestClient

from evidence.models import EvidencePlanRecord
from types import SimpleNamespace
from security.rate_limiter import InMemorySecurityStore


def test_analyst_evidence_view_keeps_restricted_sources_private(monkeypatch):
    repo = _Repository()
    client = _client(monkeypatch, repo)
    response = client.get("/api/opportunities/opp-1/evidence?view=analyst", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    body = response.json()
    assert body["artifacts"][0]["source_uri"] is None
    assert "storage_reference" not in str(body)
    assert "evidence_plans" not in body
    assert repo.calls[0][1]["user_id"] == "user-a"


class _Repository:
    def __init__(self):
        self.calls = []

    async def get_ledger(self, **kwargs):
        self.calls.append(("ledger", kwargs))
        return {
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "access_class": "restricted",
                    "source_uri": "https://private.example/deck",
                    "storage_reference": "s3://secret/deck.pdf",
                }
            ],
            "evidence_items": [],
            "claims": [],
            "claim_evidence_links": [],
            "evidence_plans": [],
        }

    async def create_plan(self, **kwargs):
        self.calls.append(("plan", kwargs))
        return EvidencePlanRecord(
            user_id=kwargs["user_id"],
            evidence_plan_id="plan-1",
            opportunity_id=kwargs["opportunity_id"],
            trigger_type=kwargs["trigger_type"],
            missing_evidence=kwargs["missing_evidence"],
            search_questions=kwargs["search_questions"],
            max_artifacts=kwargs["max_artifacts"],
            budget_usd=kwargs["budget_usd"],
            plan_hash="hash-1",
        )

    async def correct_claim(self, **kwargs):
        self.calls.append(("correct", kwargs))
        from utils.timeutil import utcnow
        return {"claim_id": kwargs["claim_id"], "status": "contradicted", "updated_at": utcnow()}

    async def ingest_artifact(self, artifact, *, items):
        self.calls.append(("confidential", artifact, items))
        return SimpleNamespace(artifact_id="artifact-private", access_class=artifact.access_class), [
            SimpleNamespace(evidence_item_id="item-private")
        ]


def _client(monkeypatch, repository, user_id="user-a"):
    import api
    monkeypatch.setattr(api, "verify_clerk_token", lambda token: user_id)
    monkeypatch.setattr(__import__("routers.deps", fromlist=["x"]), "_security_store", InMemorySecurityStore())
    api.app.state.evidence_repository = repository
    return TestClient(api.app)


def test_evidence_ledger_is_tenant_scoped_and_redacts_storage(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).get(
        "/api/opportunities/opportunity-1/evidence",
        headers={"Authorization": "Bearer t"},
    )
    assert response.status_code == 200
    assert repository.calls[0][1]["user_id"] == "user-a"
    assert "s3://" not in response.text
    assert response.json()["artifacts"][0]["source_uri"] is None


def test_claim_correction_actor_comes_from_authentication(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/claims/claim-1/correct",
        headers={"Authorization": "Bearer t"},
        json={"action": "contradict", "rationale": "Customer source disproves it."},
    )
    assert response.status_code == 200
    assert repository.calls[0][1]["actor_id"] == "user-a"


def test_confidential_intake_is_operator_verified_and_never_returns_secret_location(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/opportunities/opportunity-1/confidential-evidence",
        headers={"Authorization": "Bearer t"},
        json={
            "title": "Founder interview",
            "storage_reference": "s3://tenant-secret/interview.txt",
            "content_hash": "abcdef12345678",
            "excerpt": "Retention is improving.",
        },
    )
    assert response.status_code == 200
    assert response.json()["access_class"] == "tenant_confidential"
    assert response.json()["source_uri"] is None
    _, artifact, items = repository.calls[-1]
    assert artifact.storage_reference.startswith("s3://")
    assert artifact.access_class.value == "tenant_confidential"
    assert items[0].verification_state.value == "verified"
    assert items[0].operator_attribution == "user-a"
