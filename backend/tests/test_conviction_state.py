from conviction_state import build_conviction_patch


def test_build_conviction_patch_appends_history_with_score_snapshot_and_config_version():
    existing = {
        "human_resolution": {"decision": "MAYBE", "notes": "Track until Series A.", "resolved_at": "2026-05-01T00:00:00+00:00"},
        "review_info": {
            "market_score": 8,
            "product_score": 7,
            "technical_score": 6,
            "execution_score": 5,
            "defensibility_score": 4,
            "overall_score": 6.2,
            "thesis_alignment_score": 0.78,
        },
        "partner_info": {"recommendation": "MONITOR", "confidence": 0.66, "risks": ["Revenue not verified"]},
        "conviction_state": {
            "current_ruling": {"decision": "MAYBE", "resolved_at": "2026-05-01T00:00:00+00:00"},
            "decision_history": [
                {
                    "company_id": "startup-1",
                    "previous_decision": None,
                    "new_decision": "MAYBE",
                    "timestamp": "2026-05-01T00:00:00+00:00",
                }
            ],
        },
    }

    patch = build_conviction_patch(
        "startup-1",
        existing,
        decision="YES",
        rationale="Partner call confirmed urgency.",
        resolved_at="2026-05-10T12:00:00+00:00",
        risk_acknowledged=True,
        config_version="Fund Thesis v3",
    )

    assert patch["human_resolution"]["decision"] == "YES"
    state = patch["conviction_state"]
    assert state["current_ruling"]["decision"] == "YES"
    assert state["current_ruling"]["rationale"] == "Partner call confirmed urgency."
    assert state["risk_acknowledgements"][0]["acknowledged"] is True
    assert len(state["decision_history"]) == 2
    latest = state["decision_history"][-1]
    assert latest["company_id"] == "startup-1"
    assert latest["previous_decision"] == "MAYBE"
    assert latest["new_decision"] == "YES"
    assert latest["rationale"] == "Partner call confirmed urgency."
    assert latest["confidence"] == 0.66
    assert latest["config_version"] == "Fund Thesis v3"
    assert latest["score_snapshot"]["overall_score"] == 6.2
    assert latest["score_snapshot"]["thesis_alignment_score"] == 0.78
    assert latest["risk_acknowledged"] is True


def test_build_conviction_patch_grants_mandate_exception_and_clears_hold():
    existing = {
        "partner_info": {
            "recommendation": "MONITOR",
            "human_review_required": True,
            "mandate_gate": "held",
            "mandate_override_required": True,
            "fund_fit": 1.5,
        },
    }
    patch = build_conviction_patch(
        "startup-x",
        existing,
        decision="YES",
        rationale="IC granted an explicit off-thesis exception.",
        resolved_at="2026-06-01T00:00:00+00:00",
        mandate_exception=True,
    )
    # Audit trail captures the exception across the ledger surfaces.
    assert patch["human_resolution"]["mandate_exception"] is True
    assert patch["conviction_state"]["current_ruling"]["mandate_exception"] is True
    assert patch["conviction_state"]["decision_history"][-1]["mandate_exception"] is True
    # Hold is cleared, recommendation flips to INVEST, fit read stays honest.
    pi = patch["partner_info"]
    assert pi["recommendation"] == "INVEST"
    assert pi["human_review_required"] is False
    assert pi["mandate_override_required"] is False
    assert pi["mandate_gate"] == "exception_granted"


def test_build_conviction_patch_no_mandate_exception_leaves_hold_untouched():
    existing = {
        "partner_info": {
            "recommendation": "MONITOR",
            "mandate_override_required": True,
            "mandate_gate": "held",
        },
    }
    patch = build_conviction_patch(
        "startup-y",
        existing,
        decision="MAYBE",
        rationale="Keep monitoring; not granting an exception.",
        resolved_at="2026-06-01T00:00:00+00:00",
    )
    assert "mandate_exception" not in patch["human_resolution"]
    # Without an exception, the hold flag is left as-is (not silently cleared).
    assert patch["partner_info"].get("mandate_override_required") is True
    assert patch["partner_info"].get("mandate_gate") == "held"


def test_build_conviction_patch_records_first_decision_without_existing_state():
    patch = build_conviction_patch(
        "startup-2",
        {"review_info": {}, "partner_info": {}},
        decision="NO",
        rationale="Outside mandate.",
        resolved_at="2026-05-10T12:00:00+00:00",
    )

    state = patch["conviction_state"]
    latest = state["decision_history"][-1]
    assert latest["previous_decision"] is None
    assert latest["new_decision"] == "NO"
    assert state["current_ruling"]["decision"] == "NO"
    assert state["score_changes"] == []
    assert state["confidence_changes"] == []
