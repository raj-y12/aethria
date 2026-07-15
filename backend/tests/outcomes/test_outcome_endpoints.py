from fastapi.testclient import TestClient

from security.rate_limiter import InMemorySecurityStore


class _Repository:
    def __init__(self):
        self.calls = []

    async def process_import(self, **kwargs):
        self.calls.append(("import", kwargs))
        return {
            "batch": {"import_batch_id": "batch-1", "status": "completed"},
            "rows": [],
            "idempotent_replay": False,
        }

    async def create_outcome(self, outcome, **kwargs):
        self.calls.append(("outcome", {"outcome": outcome, **kwargs}))
        return {
            "outcome": {"outcome_type": outcome.outcome_type.value},
            "interpretation": {
                "causal_inference_supported": False,
                "allowed_use": "context_and_monitoring",
            },
        }


def _client(monkeypatch, repository):
    import api

    monkeypatch.setattr(api, "verify_clerk_token", lambda token: "user-a")
    monkeypatch.setattr(
        __import__("routers.deps", fromlist=["x"]),
        "_security_store",
        InMemorySecurityStore(),
    )
    api.app.state.channel_outcome_repository = repository
    return TestClient(api.app)


def test_csv_intake_passes_only_normalized_candidates_to_identity_path(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/imports/csv",
        headers={"Authorization": "Bearer t"},
        json={
            "source": "crm_csv",
            "idempotency_key": "crm-import-001",
            "csv_text": "company_name,website,notes\nAcme,https://acme.com,private note\n",
            "name_field": "company_name",
            "domain_field": "website",
        },
    )
    assert response.status_code == 200
    call = repository.calls[0][1]
    assert call["user_id"] == "user-a"
    assert call["candidates"][0].observed_domain == "acme.com"
    assert "private note" not in str(call["candidates"][0].model_dump())


def test_outcome_response_is_explicitly_non_causal(monkeypatch):
    repository = _Repository()
    response = _client(monkeypatch, repository).post(
        "/api/companies/company-1/outcomes",
        headers={"Authorization": "Bearer t"},
        json={
            "outcome_type": "financing",
            "valence": "positive",
            "summary": "Raised a new financing round.",
            "verification_state": "unverified",
            "materiality": 3,
        },
    )
    assert response.status_code == 200
    assert response.json()["interpretation"]["causal_inference_supported"] is False
    assert repository.calls[0][1]["outcome"].user_id == "user-a"
