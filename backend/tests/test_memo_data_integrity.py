"""Regressions for fabricated and mangled data reaching an IC pack.

Every case here was found in one live record (CameraMatics, 2026-07-31) whose
exported IC pack presented invented and misread values as fact.
"""
from __future__ import annotations

import re

import pytest

from resolver.founder_resolver import _is_person_name
from utils.adapters import scout_output_to_scout_info
from utils.traction_extraction import extract_traction_facts, render_traction_facts


def test_memo_api_hides_stale_total_funding_but_keeps_other_financials():
    from api import _backend_to_frontend

    result = _backend_to_frontend({
        "startup_id": "protex-test",
        "scout_info": {"name": "Protex AI", "funding_stage": "Series B"},
        "financials": {"funding_history": "$18M total raised (seed/Series A)", "traction_metrics": "64% fewer events"},
    })
    assert result["financials"]["funding_history"] is None
    assert result["financials"]["funding_missing"] is True
    assert result["financials"]["traction_metrics"] == "64% fewer events"


def test_memo_drops_partner_score_claim_that_conflicts_with_validation():
    from api import _backend_to_frontend

    bad_line = "Validated assessments indicate Market(7), Execution(5), Product(7)."
    result = _backend_to_frontend({
        "startup_id": "openvolt-test",
        "partner_info": {"decision_rationale": bad_line},
        "current_analysis": {
            "evaluation_id": "evaluation-current",
            "opportunity_id": "opportunity-current",
            "validation": {"assessments": [
                {"dimension": "MARKET", "validated_score": 7},
                {"dimension": "EXECUTION", "validated_score": None},
                {"dimension": "PRODUCT", "validated_score": 7},
            ]},
            "partner": {"judgment": {"action": "MORE_DILIGENCE", "rationale": [bad_line, "Customer adoption needs verification."],
                                     "confidence": 0.5, "investment_case": "An energy data platform."},
                        "operational_action": "MORE_DILIGENCE", "constraints": [], "human_review_required": True},
        },
    })
    assert "Execution(5)" not in result["partner"]["decision_rationale"]
    assert result["partner"]["decision_rationale"] == "Customer adoption needs verification."


def test_current_evaluation_read_drops_old_unsupported_partner_score_claim():
    from investment_analysis.repository import _validated_recommendation_drivers

    drivers = ["Openvolt has a credible product.", "Validated assessments indicate Execution(5)."]
    audit = {"investment_analysis": {"validation": {"assessments": [
        {"dimension": "EXECUTION", "validated_score": None},
    ]}}}
    assert _validated_recommendation_drivers(drivers, audit) == ["Openvolt has a credible product."]


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
