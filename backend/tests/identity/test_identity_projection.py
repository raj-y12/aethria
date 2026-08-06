import pytest

from identity.models import IdentityAdmission, IdentityStatus
from identity.projection import link_admission_projection


@pytest.mark.asyncio
async def test_projection_link_requires_resolved_opportunity_and_is_idempotent():
    calls = []

    class Repository:
        async def link_legacy_projection(self, **kwargs):
            calls.append(kwargs)
            return "linked"

    admission = IdentityAdmission(
        user_id="fund-a",
        observation_id="observation-1",
        status=IdentityStatus.RESOLVED,
        company_id="company-1",
        opportunity_id="opportunity-1",
        confidence=1,
    )

    assert await link_admission_projection(
        Repository(), admission=admission, legacy_startup_id="startup-1"
    ) == "linked"
    assert calls[0]["opportunity_id"] == "opportunity-1"
