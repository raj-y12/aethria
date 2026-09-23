from copy import deepcopy

import pytest

from evaluation_v2.service import snapshot_claims
from investment_analysis.mandate import check_sector_exclusions
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy


def sector_snapshot(*, verified=True, contradictory=False):
    claims, links, _ = _inputs("A_strong_verified")
    claim, link = deepcopy(claims[0]), deepcopy(links[0])
    claim.update(claim_type="company_sector", normalized_value={"sector": "Gambling"})
    if not verified:
        link["verification_state"] = "unverified"
    if contradictory:
        claim["status"] = "contradicted"
    return snapshot_claims([claim], [link], evaluation_at=CLOCK)[0]


@pytest.mark.parametrize("verified,contradictory,blocked,uncertain", [
    (True, False, True, False),
    (False, False, False, True),
    (True, True, False, True),
])
def test_explicit_exclusion_requires_eligible_uncontradicted_factual_sector(verified, contradictory, blocked, uncertain):
    conflicts, missing = check_sector_exclusions(
        snapshot=sector_snapshot(verified=verified, contradictory=contradictory),
        fund_config={"mandate": {"excludedSectorList": ["gambling"]}},
        policy=_policy(), evaluation_at=CLOCK,
    )
    assert bool(conflicts) is blocked
    assert bool(missing) is uncertain


def test_missing_sector_is_unknown_and_preferences_are_not_hard_exclusions():
    args = {"snapshot": [], "policy": _policy(), "evaluation_at": CLOCK}
    assert check_sector_exclusions(**args, fund_config={"mandate": {"preferredSectors": ["AI"], "preferredStages": ["Seed"]}}) == ([], [])
    conflicts, missing = check_sector_exclusions(**args, fund_config={"mandate": {"excludedSectorList": ["gambling"]}})
    assert conflicts == []
    assert missing


def test_exclusion_matches_exact_classification_without_guessing_from_prose():
    snapshot = sector_snapshot()
    snapshot[0]["normalized_value"] = {"sector": "Gaming infrastructure"}
    assert check_sector_exclusions(
        snapshot=snapshot, fund_config={"mandate": {"excludedSectorList": ["gambling"]}},
        policy=_policy(), evaluation_at=CLOCK,
    ) == ([], [])
