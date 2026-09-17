"""Mega-cap detection must match whole words / exact aliases, never substrings.

Substring matching silently discarded valid venture-scale companies whose names
merely contain an incumbent token, and because `validate_scout_output` raises on a
mega-cap name, every such discovery was dropped outright.
"""
import pytest

from scout.schema import validate_scout_output
from research.reference_validation import is_megacap_company

# Real venture-scale names that the old substring matcher rejected.
_REGRESSION_NAMES = [
    "Metaview",
    "Metabase",
    "Intellia",
    "Intellia Therapeutics",
    "Sapient",
    "Sapient Industries",
    "Sapling",
    "Notional",
    "Canvas",
]

_OTHER_VALID_NAMES = [
    "Intelligencia AI",
    "Metabolic Health",
    "Applied Intuition",
    "Intuitive Surgical",
    "Stripes",
    "Wisely",
    "Elasticsearch Labs",
    "Squarespace",
    "Chimera Bio",
    "Visable",
    "Zoomcar",
]

_INCUMBENTS = [
    "Google",
    "Meta",
    "Stripe",
    "Intel",
    "SAP",
    "Notion",
    "Canva",
    "Nvidia",
    "Databricks",
    "Zoom",
    "MongoDB",
]


@pytest.mark.parametrize("name", _REGRESSION_NAMES)
def test_regression_names_are_not_megacaps(name):
    assert is_megacap_company(name) is False


@pytest.mark.parametrize("name", _OTHER_VALID_NAMES)
def test_other_valid_names_are_not_megacaps(name):
    assert is_megacap_company(name) is False


@pytest.mark.parametrize("name", _INCUMBENTS)
def test_incumbents_are_still_rejected(name):
    assert is_megacap_company(name) is True


@pytest.mark.parametrize(
    "name",
    ["Stripe, Inc.", "Stripe Inc", "Microsoft Corporation", "Elastic N.V.", "Klarna AB"],
)
def test_corporate_suffixes_do_not_hide_an_incumbent(name):
    assert is_megacap_company(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "Meta Platforms",
        "Alphabet Inc",
        "International Business Machines",
        "Block Inc",
        "X Corp",
    ],
)
def test_multiword_incumbent_aliases_are_rejected(name):
    assert is_megacap_company(name) is True


@pytest.mark.parametrize("name", ["", "   ", None, 42, []])
def test_non_string_and_empty_names_are_not_megacaps(name):
    assert is_megacap_company(name) is False


def _scout_payload(name: str) -> dict:
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "scout_type": "market_driven",
        "name": name,
        "one_line": "x",
        "sector": "x",
        "problem": "p",
        "solution": "s",
        "target_users": "t",
        "why_now": "w",
        "confidence": 0.7,
        "primary_thesis": "t",
        "key_assumptions": ["a", "b"],
        "biggest_unknown": "u",
        "references": [f"{name} — https://example-company.com/about"],
    }


@pytest.mark.parametrize("name", _REGRESSION_NAMES)
def test_schema_accepts_previously_rejected_startups(name):
    assert validate_scout_output(_scout_payload(name))["name"] == name


def test_schema_still_rejects_a_real_megacap():
    with pytest.raises(ValueError, match="large public|mega-scale|incumbents"):
        validate_scout_output(_scout_payload("Stripe"))
