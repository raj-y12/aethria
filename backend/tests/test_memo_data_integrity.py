"""Regressions for fabricated and mangled data reaching an IC pack.

Every case here was found in one live record (CameraMatics, 2026-07-31) whose
exported IC pack presented invented and misread values as fact.
"""
from __future__ import annotations

import re

import pytest

from partner.rationale import compose_decision_rationale
from resolver.founder_resolver import _is_person_name
from utils.adapters import scout_output_to_scout_info
from utils.traction_extraction import extract_traction_facts, render_traction_facts


def test_company_facts_do_not_come_from_founder_education_or_other_employers():
    payload = {"name": "Assiduous", "founder_resolution": {"founders": [{"evidence": [{"snippet":
        "Assiduous consulting ltd is a consulting company.\n"
        "Ahmadu Bello University has 1,000-2,000 employees, founded in 1962.\n"
        "Assiduous has 1-10 employees, founded in 2023."}]}]}}
    facts = extract_traction_facts(payload)
    assert facts == {"employees": "1-10", "founded": "2023"}


# --- the identifier is ours, never the model's -----------------------------


class _FakeScout:
    """`_normalize_scout_ids_inplace` reads only `scout_type` off self."""

    scout_type = "market_driven"


def _normalize(data: dict) -> dict:
    from scout.base import Scout

    Scout._normalize_scout_ids_inplace(_FakeScout(), data)
    return data


def test_model_supplied_id_is_discarded():
    """The live record's `startup_id` was a placeholder the model invented."""
    data = _normalize({"id": "a1b2c3d4-e5f6-4711-9abc-1234567890ab"})

    assert data["id"] != "a1b2c3d4-e5f6-4711-9abc-1234567890ab"
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", data["id"])


def test_id_is_minted_when_the_model_omits_it():
    assert _normalize({})["id"]


def test_two_discoveries_never_share_an_id():
    ids = {
        _normalize({"id": "a1b2c3d4-e5f6-4711-9abc-1234567890ab"})["id"]
        for _ in range(50)
    }
    assert len(ids) == 50


# --- a company is not a founder --------------------------------------------


@pytest.mark.parametrize("name", [
    "Blueprint Sales Solutions",   # the live case: resolved as a founder, role CEO
    "Acme Technologies",
    "Dark Horse Analytics",
    "Fleet Systems Group",
    "Northwind Consulting",
    "Vector Robotics",
])
def test_company_shaped_names_are_not_people(name):
    assert _is_person_name(name) is False


@pytest.mark.parametrize("name", [
    "Bob Burden",
    "Mervyn O'Callaghan",
    "Simon Murray",
    "Ada Lovelace",
    "Mary-Jane Watson",
    "Bruno Sales",   # 'Sales' is a real surname — the denylist must not eat it
    "Jane Global",
])
def test_real_people_are_still_people(name):
    assert _is_person_name(name) is True


# --- traction that was retrieved must not be reported as missing -----------


_LIVE_SNIPPET = (
    "CameraMatics is a company that provides fleet safety solutions. CameraMatics "
    "has 100-150 employees (+10% YoY) and has annual revenue in the $1M-$10M range, "
    "founded in 2016. Headquartered in Ireland, with 7 prior funding rounds."
)


def test_traction_is_recovered_from_founder_evidence():
    """This text was in the record while the reviewer flagged traction as missing."""
    payload = {
        "founder_resolution": {
            "founders": [{"evidence": [{"snippet": _LIVE_SNIPPET}]}]
        }
    }

    facts = extract_traction_facts(payload)

    assert facts == {
        "employees": "100-150",
        "headcount_growth": "+10% YoY",
        "revenue": "$1M-$10M",
        "founded": "2016",
        "funding_rounds": "7",
    }


def test_traction_is_recovered_from_source_evidence():
    payload = {"source_evidence": [{"snippet": _LIVE_SNIPPET}]}
    assert extract_traction_facts(payload)["revenue"] == "$1M-$10M"


def test_arr_phrasing_is_recognised():
    payload = {"source_evidence": [{"snippet": "The company reports $4.2M ARR."}]}
    assert extract_traction_facts(payload) == {"revenue": "$4.2M"}


@pytest.mark.parametrize("payload", [
    {},
    {"source_evidence": []},
    {"source_evidence": [{"snippet": "A fleet safety company based in Dublin."}]},
    {"founder_resolution": {"founders": []}},
])
def test_absent_traction_yields_none_never_a_guess(payload):
    assert extract_traction_facts(payload) is None


def test_scout_info_carries_traction_facts_through_the_adapter():
    info = scout_output_to_scout_info({
        "name": "CameraMatics",
        "source_evidence": [{"snippet": _LIVE_SNIPPET}],
    })
    assert info.traction_facts["employees"] == "100-150"


def test_render_is_empty_when_nothing_was_found():
    assert render_traction_facts(None) == ""
    assert "Employees: 100-150" in render_traction_facts({"employees": "100-150"})


# --- one document must not disagree with itself ----------------------------


def _rationale(**overrides):
    kwargs = dict(
        final_recommendation="PASS",
        tags=frozenset(),
        primary="risk",
        label="MEDIUM",
        avg_score=5.16,
        market_score=5.68,
        product_score=5.403333,
        technical_score=4.76,
        execution_score=4.8,
        min_avg_pass=4.0,
        min_avg_strong_yes=7.5,
        min_avg_medium_maybe=6.0,
        min_avg_borderline_low=5.0,
        max_avg_borderline_high=6.5,
        has_contradiction=False,
        reviewer_disagreement=True,
        sector_concentration_note=False,
    )
    kwargs.update(overrides)
    return compose_decision_rationale(**kwargs)[0]


def test_dimension_scores_are_rounded_not_truncated():
    """int(4.8) printed "4/10" beside a table showing 4.8 — same doc, two answers."""
    rationale = _rationale()

    assert "Market 5.7/10" in rationale
    assert "Execution 4.8/10" in rationale
    assert "Technical 4.8/10" in rationale
    assert "Market 5/10" not in rationale
    assert "Execution 4/10" not in rationale


def test_raw_float_never_reaches_the_rationale():
    assert "5.403333" not in _rationale()
