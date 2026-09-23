"""Founder resolution is persisted on ScoutInfo without overwriting existing names."""
from typing import List

import pytest

from models import ScoutInfo
from resolver.founder_resolver import FounderCandidate, FounderResolution
from utils.founder_enrichment import (
    FOUNDER_PROVENANCE,
    accepted_founder_names,
    apply_founder_resolution_to_payload,
    is_founder_resolution_enabled,
    merge_founder_resolution_into_scout_info,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "FOUNDER_RESOLUTION_ENABLED",
        "FOUNDER_RESOLUTION_MIN_CONFIDENCE",
        "FOUNDER_RESOLUTION_MAX_NAMES",
    ):
        monkeypatch.delenv(key, raising=False)


def _scout_info(**kwargs) -> ScoutInfo:
    base = dict(
        startup_id="s1",
        name="Acme",
        one_line="AI",
        sector="Software",
        problem="p",
        solution="s",
        target_users="u",
        why_now="w",
        scout_type="market_driven",
        confidence_score=0.8,
        references=["https://acme.com/about"],
    )
    base.update(kwargs)
    return ScoutInfo(**base)


def _resolution(names_with_conf: List[tuple], **kwargs) -> FounderResolution:
    return FounderResolution(
        company="Acme",
        founders=[
            FounderCandidate(name=n, confidence=c, role="Founder") for n, c in names_with_conf
        ],
        resolution_status="FOUND",
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Toggles and thresholds
# --------------------------------------------------------------------------- #


def test_enabled_by_default():
    assert is_founder_resolution_enabled() is True


def test_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_ENABLED", "false")
    assert is_founder_resolution_enabled() is False


def test_low_confidence_candidates_are_not_promoted(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "0.5")
    resolution = _resolution([("Ada Byron", 0.9), ("Noisy Match", 0.2)])
    assert accepted_founder_names(resolution) == ["Ada Byron"]


def test_promoted_names_are_capped(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MAX_NAMES", "2")
    resolution = _resolution([("A One", 0.9), ("B Two", 0.8), ("C Three", 0.7)])
    assert accepted_founder_names(resolution) == ["A One", "B Two"]


def test_name_cap_never_exceeds_the_scout_info_limit(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MAX_NAMES", "50")
    resolution = _resolution([(f"Person {i}", 0.9) for i in range(12)])
    names = accepted_founder_names(resolution)
    assert len(names) == 8
    # ScoutInfo rejects more than 8 names, so the cap must hold at the model too.
    _scout_info(founder_names=names)


# --------------------------------------------------------------------------- #
# Payload application (lookup stage)
# --------------------------------------------------------------------------- #


def test_payload_gets_structured_resolution_and_names():
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme"}, _resolution([("Ada Byron", 0.8)])
    )
    assert payload["founder_names"] == ["Ada Byron"]
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"
    assert payload["field_provenance"]["founder_names"] == FOUNDER_PROVENANCE


def test_payload_names_are_never_overwritten():
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme", "founder_names": ["Grace Hopper"]},
        _resolution([("Ada Byron", 0.9)]),
    )
    assert payload["founder_names"] == ["Grace Hopper"]
    # The structured resolution is still attached for auditability.
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"
    assert "founder_names" not in (payload.get("field_provenance") or {})


def test_payload_is_unchanged_without_a_resolution():
    original = {"name": "Acme"}
    assert apply_founder_resolution_to_payload(original, None) == original


def test_structured_resolution_is_attached_even_when_no_name_clears_the_floor(monkeypatch):
    monkeypatch.setenv("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "0.9")
    payload = apply_founder_resolution_to_payload(
        {"name": "Acme"}, _resolution([("Ada Byron", 0.3)])
    )
    assert "founder_names" not in payload
    assert payload["founder_resolution"]["founders"][0]["name"] == "Ada Byron"


# --------------------------------------------------------------------------- #
# ScoutInfo persistence (reviewer stage)
# --------------------------------------------------------------------------- #


def test_scout_info_gains_founders_and_provenance():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(), _resolution([("Ada Byron", 0.8)])
    )
    assert merged.founder_names == ["Ada Byron"]
    assert merged.field_provenance["founder_names"] == FOUNDER_PROVENANCE
    assert merged.founder_resolution["resolution_status"] == "FOUND"


def test_scout_info_founders_are_never_overwritten():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(founder_names=["Grace Hopper"]), _resolution([("Ada Byron", 0.9)])
    )
    assert merged.founder_names == ["Grace Hopper"]
    assert merged.founder_resolution is not None


def test_existing_provenance_is_preserved():
    merged = merge_founder_resolution_into_scout_info(
        _scout_info(field_provenance={"est_tam": "reviewer_extraction"}),
        _resolution([("Ada Byron", 0.8)]),
    )
    assert merged.field_provenance["est_tam"] == "reviewer_extraction"
    assert merged.field_provenance["founder_names"] == FOUNDER_PROVENANCE


def test_scout_info_is_unchanged_without_a_resolution():
    original = _scout_info()
    assert merge_founder_resolution_into_scout_info(original, None) is original
