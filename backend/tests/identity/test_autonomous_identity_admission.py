import pytest

import pipeline_runner
from identity.acquisition import observation_from_scout_discovery
from identity.models import IdentityAdmission, IdentityStatus


def _discovery(startup_id, *, name="Acme", website="https://acme.com", scout_type="market_driven"):
    return {
        "id": startup_id,
        "persisted_startup_id": startup_id,
        "name": name,
        "scout_type": scout_type,
        "confidence": 0.94,
        "prompt_version": "prompt-v1",
        "references": [website, "https://techcrunch.com/acme-funding"],
    }


def test_scout_observation_preserves_channel_persona_and_verified_official_domain():
    observation = observation_from_scout_discovery(
        user_id="fund-a", discovery=_discovery("startup-1")
    )

    assert observation.channel.value == "autonomous_discovery"
    assert observation.observed_domain == "acme.com"
    assert observation.source_metadata["scout_type"] == "market_driven"
    assert observation.source_metadata["prompt_version"] == "prompt-v1"
    assert observation.resolution_payload["evidence_sources"][0]["source_type"] == "official_site"


def test_same_name_with_different_domains_remains_distinguishable():
    first = observation_from_scout_discovery(
        user_id="fund-a",
        discovery=_discovery("startup-1", name="Beacon", website="https://beacon.com"),
    )
    second = observation_from_scout_discovery(
        user_id="fund-a",
        discovery=_discovery("startup-2", name="Beacon", website="https://beacon.health"),
    )

    assert first.observed_name == second.observed_name
    assert first.observed_domain != second.observed_domain


class _Storage:
    def __init__(self, surviving):
        self.surviving = set(surviving)
        self.removed = []
        self.persisted = []

    def get_startup(self, startup_id):
        return object() if startup_id in self.surviving else None

    def remove_startup(self, startup_id):
        self.removed.append(startup_id)
        self.surviving.discard(startup_id)
        return True

    def add_discovery(self, discovery, *, pipeline_run_id=None):
        self.persisted.append((dict(discovery), pipeline_run_id))
        startup_id = str(discovery["id"])
        self.surviving.add(startup_id)
        return startup_id


class _Service:
    def __init__(self, admissions):
        self.admissions = iter(admissions)
        self.observations = []

    async def admit(self, observation):
        self.observations.append(observation)
        return next(self.admissions)


@pytest.mark.asyncio
async def test_two_personas_same_domain_keep_two_observations_one_opportunity():
    discoveries = [
        _discovery("startup-1", scout_type="market_driven"),
        _discovery("startup-2", scout_type="contrarian"),
    ]
    service = _Service(
        [
            IdentityAdmission(
                user_id="fund-a",
                observation_id="observation-1",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
            ),
            IdentityAdmission(
                user_id="fund-a",
                observation_id="observation-2",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
            ),
        ]
    )
    linked = []

    class Repository:
        async def link_legacy_projection(self, **kwargs):
            linked.append(kwargs)

    results = await pipeline_runner._admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=discoveries,
        storage=_Storage({"startup-1", "startup-2"}),
        identity_repository=Repository(),
        identity_service=service,
    )

    assert len(service.observations) == 2
    assert {item.source_metadata["scout_type"] for item in service.observations} == {
        "market_driven",
        "contrarian",
    }
    assert {item.opportunity_id for item in results} == {"opportunity-1"}
    assert len(linked) == 2


@pytest.mark.asyncio
async def test_pruned_discovery_never_creates_authoritative_observation():
    service = _Service([])

    results = await pipeline_runner._admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=[_discovery("pruned-startup")],
        storage=_Storage(set()),
        identity_repository=object(),
        identity_service=service,
    )

    assert results == []
    assert service.observations == []


@pytest.mark.asyncio
async def test_ambiguous_discovery_is_removed_from_legacy_review_queue():
    storage = _Storage({"startup-1"})
    service = _Service(
        [
            IdentityAdmission(
                user_id="fund-a",
                observation_id="observation-1",
                status=IdentityStatus.AMBIGUOUS,
                identity_case_id="case-1",
                confidence=0.7,
                blocks_evaluation=True,
            )
        ]
    )

    results = await pipeline_runner._admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=[_discovery("startup-1")],
        storage=storage,
        identity_repository=object(),
        identity_service=service,
    )

    assert results[0].blocks_evaluation is True
    assert storage.removed == ["startup-1"]


@pytest.mark.asyncio
async def test_new_discovery_is_admitted_before_legacy_persistence_and_linking():
    events = []
    storage = _Storage(set())

    class Service:
        async def admit(self, observation):
            events.append("identity")
            assert observation.legacy_startup_id is None
            return IdentityAdmission(
                user_id="fund-a",
                observation_id="observation-1",
                status=IdentityStatus.RESOLVED,
                company_id="company-1",
                opportunity_id="opportunity-1",
                confidence=1,
            )

    original_add = storage.add_discovery

    def add(discovery, *, pipeline_run_id=None):
        events.append("persist")
        return original_add(discovery, pipeline_run_id=pipeline_run_id)

    storage.add_discovery = add

    class Repository:
        async def link_legacy_projection(self, **kwargs):
            events.append("link")

    await pipeline_runner._admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=[_discovery("startup-1")],
        storage=storage,
        identity_repository=Repository(),
        identity_service=Service(),
        discoveries_are_persisted=False,
    )

    assert events == ["identity", "persist", "link"]
    assert storage.persisted[0][0]["persisted_startup_id"] == "startup-1"
