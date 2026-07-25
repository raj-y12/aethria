import pytest

from identity.models import IdentityAdmission, IdentityStatus
from ingest import service


@pytest.mark.asyncio
async def test_import_rows_create_observations_and_preserve_blocked_identity(monkeypatch):
    class FakeIdentity:
        def __init__(self, _repository):
            pass

        async def admit(self, observation):
            return IdentityAdmission(
                user_id=observation.user_id, observation_id=observation.external_event_key,
                status=IdentityStatus.AMBIGUOUS, identity_case_id="case-1", blocks_evaluation=True,
            )

    monkeypatch.setattr(service, "IdentityService", FakeIdentity)
    result = await service.CompanyImportService(object()).ingest_rows(
        user_id="fund-a", import_id="csv-1", rows=[{"company_name": "Acme"}],
    )
    assert result["rows_processed"] == 1
    assert result["blocked"] == 1
    assert result["observations"][0]["status"] == "ambiguous"


@pytest.mark.asyncio
async def test_import_rejects_malformed_row_before_partial_processing(monkeypatch):
    class FakeIdentity:
        def __init__(self, _repository):
            self.calls = 0

        async def admit(self, observation):
            self.calls += 1
            return IdentityAdmission(user_id=observation.user_id, observation_id="obs", status=IdentityStatus.RESOLVED)

    monkeypatch.setattr(service, "IdentityService", FakeIdentity)
    with pytest.raises(service.ImportRowError):
        await service.CompanyImportService(object()).ingest_rows(
            user_id="fund-a", import_id="csv-1", rows=[{"company_name": "Acme"}, {}],
        )
