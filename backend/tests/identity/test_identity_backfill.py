import json
from collections import deque

import pytest

from identity.backfill import (
    CanonicalIdentityBackfill,
    legacy_row_to_observation,
    legacy_state_to_opportunity_state,
)
from identity.models import IdentityAdmission, IdentityStatus, OpportunityState
from identity.normalization import extract_identifier_candidates


def _row(startup_id, *, name="Acme", domain="acme.com", decision="YES"):
    resolution = None
    if domain:
        resolution = {
            "website": f"https://{domain}",
            "confidence": 0.96,
            "resolution_status": "FOUND",
            "evidence_sources": [
                {"url": f"https://{domain}", "source_type": "official_site"}
            ],
        }
    return {
        "startup_id": startup_id,
        "user_id": "fund-a",
        "scout_info": json.dumps(
            {
                "name": name,
                "scout_type": "market_driven",
                "lookup_website": f"https://{domain}" if domain else None,
                "company_resolution": resolution,
            }
        ),
        "partner_info": json.dumps({"decision": decision}) if decision else None,
        "human_resolution": None,
        "created_at": "2026-01-02T00:00:00+00:00",
    }


def test_backfill_only_verifies_domain_with_resolver_evidence():
    verified = legacy_row_to_observation(user_id="fund-a", row=_row("startup-1"))
    unverified = legacy_row_to_observation(
        user_id="fund-a",
        row=_row("startup-2", domain=None),
    )

    assert any(
        item.verification_status.value == "verified"
        for item in extract_identifier_candidates(verified)
    )
    assert extract_identifier_candidates(unverified) == []
    assert verified.source_metadata["legacy_scout_payload"]["name"] == "Acme"
    assert verified.resolution_payload["website"] == "https://acme.com"


def test_name_only_rows_keep_distinct_idempotency_keys():
    first = legacy_row_to_observation(
        user_id="fund-a", row=_row("startup-1", domain=None)
    )
    second = legacy_row_to_observation(
        user_id="fund-a", row=_row("startup-2", domain=None)
    )

    assert first.observed_name == second.observed_name
    assert first.external_event_key != second.external_event_key
    assert first.observed_domain is None
    assert second.observed_domain is None


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("YES", OpportunityState.ADVANCE),
        ("INVEST", OpportunityState.ADVANCE),
        ("MAYBE", OpportunityState.MONITOR),
        ("MONITOR", OpportunityState.MONITOR),
        ("NO", OpportunityState.PASS),
        ("PASS", OpportunityState.PASS),
        (None, OpportunityState.DISCOVERED),
    ],
)
def test_legacy_decision_has_one_compatibility_mapping(decision, expected):
    assert legacy_state_to_opportunity_state(decision) is expected


class _Connection:
    def __init__(self, batches):
        self.batches = deque(batches)
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.batches.popleft() if self.batches else []


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


class _Repository:
    def __init__(self):
        self.states = []
        self.links = []

    async def set_opportunity_state(self, **kwargs):
        self.states.append(kwargs)

    async def link_legacy_projection(self, **kwargs):
        self.links.append(kwargs)


class _Service:
    def __init__(self):
        self.observations = []

    async def admit(self, observation):
        self.observations.append(observation)
        index = len(self.observations)
        return IdentityAdmission(
            user_id="fund-a",
            observation_id=f"observation-{index}",
            status=IdentityStatus.RESOLVED,
            company_id="company-1",
            opportunity_id="opportunity-1",
            confidence=1,
            created=index == 1,
        )


@pytest.mark.asyncio
async def test_dry_run_writes_nothing_and_reports_safe_counts():
    service = _Service()
    repository = _Repository()
    runner = CanonicalIdentityBackfill(
        _Pool(_Connection([[_row("startup-1")]])),
        repository=repository,
        service=service,
    )

    report = await runner.run_batch(user_id="fund-a", apply=False, batch_size=10)

    assert report.rows_processed == 1
    assert report.would_resolve == 1
    assert service.observations == []
    assert repository.states == []


@pytest.mark.asyncio
async def test_apply_is_restartable_and_same_verified_domain_converges():
    service = _Service()
    repository = _Repository()
    connection = _Connection(
        [
            [_row("startup-1"), _row("startup-2", decision="MAYBE")],
            [],
        ]
    )
    runner = CanonicalIdentityBackfill(
        _Pool(connection), repository=repository, service=service
    )

    first = await runner.run_batch(user_id="fund-a", apply=True, batch_size=2)
    second = await runner.run_batch(
        user_id="fund-a", apply=True, batch_size=2, after=first.next_cursor
    )

    assert first.next_cursor == "startup-2"
    assert second.complete is True
    assert len(service.observations) == 2
    assert {item.observed_domain for item in service.observations} == {"acme.com"}
    assert {item["opportunity_id"] for item in repository.links} == {"opportunity-1"}
    assert [item["decision_state"] for item in repository.states] == [
        OpportunityState.ADVANCE,
        OpportunityState.MONITOR,
    ]
