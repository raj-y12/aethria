from types import SimpleNamespace

import pytest

import pipeline_runner
from identity.acquisition import observation_from_scout_discovery
from identity.models import IdentityAdmission, IdentityStatus
from identity.repository import IdentityConflictError


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


def test_autonomous_discovery_dedup_key_is_stable_per_company_not_per_call():
    """Regression (live-verified 2026-08-18): external_event_key used to be
    keyed on the discovery's random per-LLM-call id (persist_discoveries=False
    in the periodic pipeline means there's no persisted row id to key off of
    instead), so the same real company got a fresh dedup key -- and a fresh
    identity_resolution_case -- every time Scout rediscovered it. Live: one
    company had 45 open cases, another 24, for 4 distinct companies total in
    80 open cases. The key must be stable across different startup_ids AND
    different scout_type personas discovering the same company name."""
    same_company_by_two_personas = [
        observation_from_scout_discovery(
            user_id="fund-a",
            discovery=_discovery("startup-1", name="Shiplog", scout_type="market_driven"),
        ),
        observation_from_scout_discovery(
            user_id="fund-a",
            discovery=_discovery("startup-2", name="Shiplog", scout_type="contrarian"),
        ),
    ]
    assert (
        same_company_by_two_personas[0].external_event_key
        == same_company_by_two_personas[1].external_event_key
    )

    different_company = observation_from_scout_discovery(
        user_id="fund-a",
        discovery=_discovery("startup-3", name="Zerolook", scout_type="market_driven"),
    )
    assert different_company.external_event_key != same_company_by_two_personas[0].external_event_key


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


@pytest.mark.asyncio
async def test_periodic_admissions_evaluate_each_opportunity_once(monkeypatch):
    """Several Scout observations must not create competing evaluations."""
    calls = []

    class EvaluationRepository:
        def __init__(self, pool):
            assert pool is pool_marker

        async def evaluate(self, **kwargs):
            calls.append(kwargs)
            return {}

    class Prerequisites:
        policy = object()
        thesis_version_id = "thesis-v1"

    pool_marker = object()
    monkeypatch.setattr(pipeline_runner, "EvaluationRepository", EvaluationRepository)

    count = await pipeline_runner._evaluate_admitted_periodic_discoveries(
        user_id="fund-a",
        admissions=[
            SimpleNamespace(opportunity_id="opportunity-1", blocks_evaluation=False),
            SimpleNamespace(opportunity_id="opportunity-1", blocks_evaluation=False),
            SimpleNamespace(opportunity_id="opportunity-2", blocks_evaluation=True),
        ],
        evaluation_prerequisites=Prerequisites(),
        postgres_pool=pool_marker,
    )

    assert count == 1
    assert calls == [{
        "user_id": "fund-a",
        "opportunity_id": "opportunity-1",
        "actor_id": "fund-a",
        "trigger_type": "periodic_discovery",
        "policy": Prerequisites.policy,
        "thesis_version_id": "thesis-v1",
    }]


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

    # Regression (audit CRITICAL-F2): the previous mock's link_legacy_projection
    # was a no-op that always succeeded, unlike the real DB guard in
    # identity/repository.py -- which rejects a second link with a DIFFERENT
    # legacy_startup_id for the same opportunity. That gap is exactly why the
    # production crash went undetected. This mock faithfully reproduces the
    # guard so the test proves _admit_autonomous_discoveries survives it.
    class Repository:
        def __init__(self):
            self._legacy_by_opportunity: dict[str, str] = {}

        async def get_opportunity(self, *, user_id, opportunity_id):
            return None

        async def link_legacy_projection(self, *, user_id, opportunity_id, legacy_startup_id):
            existing = self._legacy_by_opportunity.get(opportunity_id)
            if existing is not None and existing != legacy_startup_id:
                raise IdentityConflictError(
                    "Opportunity projection is missing, cross-tenant, or already linked"
                )
            self._legacy_by_opportunity[opportunity_id] = legacy_startup_id
            linked.append({"opportunity_id": opportunity_id, "legacy_startup_id": legacy_startup_id})

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
    # Both admissions succeed and are returned -- the conflicting second link
    # is caught and skipped, it does not crash the whole cycle.
    assert len(results) == 2
    assert {item.opportunity_id for item in results} == {"opportunity-1"}
    # Only one legacy startup id can ever occupy the opportunity's single
    # legacy_startup_id column; the second persona's link legitimately loses.
    assert len(linked) == 1


@pytest.mark.asyncio
async def test_unpersisted_second_persona_reuses_existing_legacy_row_instead_of_duplicating():
    """Regression (audit CRITICAL-F2), the not-yet-persisted (autonomous
    discovery) path: a second persona's discovery resolving to an opportunity
    that already has a linked legacy startup row must reuse it instead of
    calling storage.add_discovery again, which used to create a duplicate,
    permanently orphaned startups row every time this fired."""
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
    storage = _Storage(set())

    class Repository:
        def __init__(self):
            self._legacy_by_opportunity: dict[str, str] = {}

        async def get_opportunity(self, *, user_id, opportunity_id):
            legacy = self._legacy_by_opportunity.get(opportunity_id)
            if legacy is None:
                return None
            return SimpleNamespace(legacy_startup_id=legacy)

        async def link_legacy_projection(self, *, user_id, opportunity_id, legacy_startup_id):
            self._legacy_by_opportunity[opportunity_id] = legacy_startup_id

    results = await pipeline_runner._admit_autonomous_discoveries(
        user_id="fund-a",
        discoveries=discoveries,
        storage=storage,
        identity_repository=Repository(),
        identity_service=service,
        discoveries_are_persisted=False,
    )

    assert len(results) == 2
    # Only the first persona's discovery created a legacy row -- the second
    # reused it instead of duplicating.
    assert len(storage.persisted) == 1


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
        async def get_opportunity(self, *, user_id, opportunity_id):
            return None

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
