from types import SimpleNamespace

import pytest

from identity.acquisition import observation_from_scout_discovery
from identity.models import IdentityAdmission, IdentityStatus, SourceChannel
from pipeline_runner import (
    _admit_autonomous_discoveries,
    _admit_named_lookup_before_review,
)


def _scout_output():
    return {
        "id": "startup-1",
        "persisted_startup_id": "startup-1",
        "origin_type": "on_demand_lookup",
        "lookup_id": "lookup-barespace",
        "lookup_website": "https://barespace.io",
        "name": "Barespace",
        "confidence": 0.9,
        "references": ["https://barespace.io", "https://tech.eu/barespace"],
        "source_evidence": [
            {
                "title": "Barespace funding",
                "url": "https://tech.eu/barespace",
                "snippet": "Barespace raised a seed round and sells salon software.",
                "supports": "funding and commercial model",
            }
        ],
        "founder_resolution": {
            "company": "Barespace",
            "founders": [
                {
                    "name": "Conor Moules",
                    "role": "Co-founder",
                    "confidence": 0.9,
                    "evidence": [
                        {
                            "url": "https://barespace.io/team",
                            "title": "Team",
                            "snippet": "Conor Moules is a co-founder.",
                        }
                    ],
                }
            ],
            "resolution_status": "FOUND",
        },
    }


def test_named_lookup_observation_uses_manual_channel_and_stable_lookup_identity():
    observation = observation_from_scout_discovery(
        user_id="fund-a",
        discovery=_scout_output(),
    )

    assert observation.channel is SourceChannel.MANUAL_LOOKUP
    assert observation.external_event_key == "lookup:lookup-barespace"
    assert observation.lookup_id == "lookup-barespace"
    assert observation.source_metadata["operator_confirmed_identity"] is True


def test_operator_confirmation_does_not_apply_to_a_same_named_different_domain():
    """Regression (audit CRITICAL-F1): operator_confirmed_identity used to be
    True whenever ANY lookup_website was supplied, regardless of whether it
    matched the domain this observation actually resolved to. Live-observed
    class of bug (Anthropic description theft, fixed separately) -- here the
    same anchor-skip could let a same-named different company's domain
    inherit the operator's confirmation and bypass identity/normalization.py's
    other verification checks entirely."""
    discovery = _scout_output()
    # The operator confirmed barespace.io, but the only reference the scout
    # actually found is a different, same-named domain (barespace.co) --
    # observed_domain resolves to that, not the operator's hint.
    discovery["lookup_website"] = "https://barespace.io"
    discovery["references"] = ["https://barespace.co", "https://tech.eu/barespace"]

    observation = observation_from_scout_discovery(
        user_id="fund-a",
        discovery=discovery,
    )

    assert observation.observed_domain == "barespace.co"
    assert observation.source_metadata["operator_confirmed_identity"] is False


@pytest.mark.asyncio
async def test_named_lookup_canonical_path_admits_then_persists_founders_before_review(
    monkeypatch,
):
    events = []
    admission = IdentityAdmission(
        user_id="fund-a",
        observation_id="observation-1",
        status=IdentityStatus.RESOLVED,
        company_id="company-1",
        opportunity_id="opportunity-1",
        confidence=1,
    )

    async def admit_discovery(**kwargs):
        events.append("canonical_admission_and_claims")
        assert kwargs["discoveries_are_persisted"] is True
        assert kwargs["discoveries"][0]["origin_type"] == "on_demand_lookup"
        return [admission]

    async def persist_founder(*, user_id, startup_id, resolution):
        events.append("canonical_people")
        assert user_id == "fund-a"
        assert startup_id == "startup-1"
        assert resolution.founders[0].name == "Conor Moules"

    monkeypatch.setattr(
        "pipeline_runner._admit_autonomous_discoveries", admit_discovery
    )

    result = await _admit_named_lookup_before_review(
        user_id="fund-a",
        startup_id="startup-1",
        scout_output=_scout_output(),
        storage=SimpleNamespace(),
        identity_repository=SimpleNamespace(),
        evidence_repository=SimpleNamespace(),
        founder_persister=persist_founder,
    )

    assert result is admission
    assert events == ["canonical_admission_and_claims", "canonical_people"]


@pytest.mark.asyncio
async def test_named_lookup_admission_accepts_fresh_startup_handoff_without_stale_snapshot():
    class Storage:
        def get_startup(self, _startup_id):
            return None

    class IdentityService:
        async def admit(self, _observation):
            return IdentityAdmission(
                user_id="fund-a",
                observation_id="observation-1",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
            )

    class IdentityRepository:
        async def link_legacy_projection(self, **_kwargs):
            return SimpleNamespace(opportunity_id="opportunity-1")

    admitted = await _admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=[_scout_output()],
        storage=Storage(),
        identity_repository=IdentityRepository(),
        identity_service=IdentityService(),
        discoveries_are_persisted=True,
        persisted_startup_ids={"startup-1"},
    )

    assert admitted[0].opportunity_id == "opportunity-1"
