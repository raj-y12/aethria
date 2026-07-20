import inspect

import pytest

from evaluation_v2 import compatibility
from utils import partner_codes


@pytest.mark.parametrize(
    ("legacy", "institutional"),
    [
        ("INVEST", "ADVANCE"),
        ("MONITOR", "MONITOR"),
        ("PASS", "PASS"),
    ],
)
def test_legacy_partner_recommendation_maps_to_institutional_recommendation(
    legacy, institutional
):
    assert (
        partner_codes.institutional_recommendation_from_legacy_partner(legacy)
        == institutional
    )


@pytest.mark.parametrize(
    ("institutional", "legacy", "reason"),
    [
        ("ADVANCE", "MONITOR", "advance"),
        ("MONITOR", "MONITOR", None),
        ("PASS", "PASS", None),
        ("INSUFFICIENT_EVIDENCE", "MONITOR", "insufficient_evidence"),
    ],
)
def test_institutional_recommendation_projects_to_legacy_partner_safely(
    institutional, legacy, reason
):
    projection = partner_codes.legacy_partner_from_institutional_recommendation(
        institutional
    )

    assert projection.value == legacy
    assert projection.compatibility_reason == reason


@pytest.mark.parametrize(
    ("legacy", "institutional"),
    [
        ("YES", "INVEST"),
        ("MAYBE", "MONITOR"),
        ("NO", "PASS"),
    ],
)
def test_legacy_human_ruling_maps_to_institutional_ruling(legacy, institutional):
    assert partner_codes.institutional_ruling_from_legacy(legacy) == institutional


@pytest.mark.parametrize(
    ("institutional", "legacy", "reason"),
    [
        ("ADVANCE", "MAYBE", "advance"),
        ("MONITOR", "MAYBE", None),
        ("PASS", "NO", None),
        ("INVEST", "YES", None),
    ],
)
def test_institutional_ruling_projects_to_legacy_human_ruling(
    institutional, legacy, reason
):
    projection = partner_codes.legacy_ruling_from_institutional(institutional)

    assert projection.value == legacy
    assert projection.compatibility_reason == reason


def test_advance_ruling_never_projects_to_legacy_yes():
    projection = partner_codes.legacy_ruling_from_institutional("advance")

    assert projection.value == "MAYBE"
    assert projection.compatibility_reason == "advance"


def test_evaluation_v2_compatibility_delegates_to_canonical_mapping():
    source = inspect.getsource(compatibility.recommendation_to_legacy)

    assert "legacy_partner_from_institutional_recommendation" in source
    assert "RecommendationState.ADVANCE" not in source
    assert "RecommendationState.MONITOR" not in source
    assert "RecommendationState.PASS" not in source


def test_insufficient_evidence_compatibility_requires_human_review():
    assert compatibility.recommendation_to_legacy("insufficient_evidence") == {
        "recommendation": "MONITOR",
        "human_review_required": True,
        "compatibility_reason": "insufficient_evidence",
    }


@pytest.mark.parametrize(
    "adapter,value",
    [
        ("institutional_recommendation_from_legacy_partner", "unknown"),
        ("institutional_ruling_from_legacy", "unknown"),
        ("legacy_partner_from_institutional_recommendation", "unknown"),
        ("legacy_ruling_from_institutional", "unknown"),
    ],
)
def test_institutional_decision_adapters_reject_unknown_codes(adapter, value):
    with pytest.raises(ValueError, match="Unknown"):
        getattr(partner_codes, adapter)(value)
