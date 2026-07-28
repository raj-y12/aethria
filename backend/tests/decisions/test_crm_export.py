import pytest

from decisions.crm_export import build_crm_export_payload


COMPANY = {"canonical_name": "Acme", "canonical_domain": "acme.ai"}
RULING = {
    "decision": "invest",
    "rationale": "Retention held through the pricing change.",
    "investor_confidence": 0.72,
    "created_at": "2026-07-20T12:00:00Z",
    "override_type": None,
    "mandate_exception": "Outside stated stage band.",
}


def test_payload_uses_canonical_domain_as_the_crm_dedupe_key():
    payload = build_crm_export_payload(company=COMPANY, ruling=RULING, position=None, outcomes=[])
    assert payload["dedupe_key"] == "acme.ai"
    assert payload["company_name"] == "Acme"
    assert payload["decision"] == "INVEST"


def test_payload_falls_back_to_normalized_name_when_no_domain_exists():
    payload = build_crm_export_payload(
        company={"canonical_name": "Beta Labs", "canonical_domain": None},
        ruling=RULING, position=None, outcomes=[],
    )
    assert payload["dedupe_key"] == "beta-labs"


def test_payload_never_claims_an_external_write_has_happened():
    payload = build_crm_export_payload(company=COMPANY, ruling=RULING, position=None, outcomes=[])
    assert payload["external_write_performed"] is False
    assert payload["requires_approval"] is True


def test_payload_carries_the_latest_outcome_and_a_count():
    payload = build_crm_export_payload(
        company=COMPANY, ruling=RULING, position=None,
        outcomes=[
            {"outcome_type": "financing", "valence": "positive", "summary": "Raised a seed round.", "observed_at": "2026-07-01T00:00:00Z"},
            {"outcome_type": "acquisition", "valence": "positive", "summary": "Acquired by a strategic.", "observed_at": "2026-07-25T00:00:00Z"},
        ],
    )
    assert payload["outcome_count"] == 2
    assert payload["latest_outcome"] == "acquisition: Acquired by a strategic."


def test_payload_reports_no_outcome_honestly_rather_than_guessing():
    payload = build_crm_export_payload(company=COMPANY, ruling=RULING, position=None, outcomes=[])
    assert payload["latest_outcome"] is None
    assert payload["outcome_count"] == 0


def test_payload_excludes_confidential_ruling_fields():
    payload = build_crm_export_payload(company=COMPANY, ruling=RULING, position=None, outcomes=[])
    assert "mandate_exception" not in payload
    assert "risk_acknowledgement" not in payload
    assert "override_note" not in payload


def test_payload_rejects_a_company_with_no_identity():
    with pytest.raises(ValueError):
        build_crm_export_payload(
            company={"canonical_name": "", "canonical_domain": None},
            ruling=RULING, position=None, outcomes=[],
        )


def test_payload_rejects_a_company_whose_name_slugs_to_nothing():
    """A name made entirely of symbols (e.g. '(TM)(C)(R)') normalizes to an
    empty slug. Without this guard, two unrelated companies with no domain
    would both get dedupe_key == "" and collapse into one CRM record."""
    with pytest.raises(ValueError):
        build_crm_export_payload(
            company={"canonical_name": "™©®", "canonical_domain": None},
            ruling=RULING, position=None, outcomes=[],
        )


def test_payload_refuses_to_fabricate_a_decision_when_no_ruling_exists():
    """An opportunity with no human_rulings row must not silently export as
    MONITOR with an empty rationale -- that fabricates a considered decision
    that was never made."""
    with pytest.raises(ValueError):
        build_crm_export_payload(company=COMPANY, ruling={}, position=None, outcomes=[])


def test_payload_reports_missing_confidence_as_none_not_zero():
    """A ruling with no recorded investor_confidence must export as None --
    a CRM reading 0.0 would misrepresent "not recorded" as "zero confidence"."""
    payload = build_crm_export_payload(
        company=COMPANY,
        ruling={**RULING, "investor_confidence": None},
        position=None, outcomes=[],
    )
    assert payload["investor_confidence"] is None


def test_payload_refuses_an_unrecognized_ruling_decision():
    """A decision string present but outside the known map (e.g. schema
    drift introducing a new ruling value) is refused rather than silently
    downgraded to MONITOR, which would misrepresent the actual decision."""
    with pytest.raises(ValueError):
        build_crm_export_payload(
            company=COMPANY,
            ruling={**RULING, "decision": "escalate"},
            position=None, outcomes=[],
        )
