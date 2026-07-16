import pytest

from outcomes.models import ImportSource, OutcomeInput, OutcomeType, OutcomeValence, OutcomeVerification
from outcomes.service import ImportLimitError, build_outcome_interpretation, parse_csv_candidates, validate_outcome


def test_csv_candidates_are_bounded_and_keep_only_identity_fields():
    candidates = parse_csv_candidates(
        "company_name,website,crm_id,private_notes\nAcme,https://acme.com,crm-1,secret\n",
        source=ImportSource.CRM_CSV,
        import_id="import-1",
        name_field="company_name",
        domain_field="website",
        external_id_field="crm_id",
        max_rows=10,
    )
    assert len(candidates) == 1
    assert candidates[0].observed_name == "Acme"
    assert candidates[0].observed_domain == "acme.com"
    assert candidates[0].external_id == "crm-1"
    assert "secret" not in str(candidates[0].model_dump())


def test_csv_parser_rejects_unbounded_imports():
    with pytest.raises(ImportLimitError):
        parse_csv_candidates(
            "name\nA\nB\n",
            source=ImportSource.CSV,
            import_id="import-1",
            name_field="name",
            max_rows=1,
        )


def test_imported_domain_is_verified_only_when_operator_explicitly_confirms_mapping():
    default = parse_csv_candidates(
        "name,domain\nAcme,acme.com\n",
        source=ImportSource.CSV,
        import_id="import-1",
        name_field="name",
        domain_field="domain",
    )
    confirmed = parse_csv_candidates(
        "name,domain\nAcme,acme.com\n",
        source=ImportSource.CSV,
        import_id="import-2",
        name_field="name",
        domain_field="domain",
        verify_domains=True,
    )
    assert default[0].operator_confirmed_identity is False
    assert confirmed[0].operator_confirmed_identity is True


def test_verified_outcome_requires_evidence_and_never_claims_causality():
    outcome = OutcomeInput(
        user_id="user-a",
        company_id="company-1",
        opportunity_id="opportunity-1",
        outcome_type=OutcomeType.FINANCING,
        valence=OutcomeValence.POSITIVE,
        summary="Raised a Series A.",
        verification_state=OutcomeVerification.VERIFIED,
        materiality=4,
        evidence_artifact_ids=["artifact-1"],
    )
    validate_outcome(outcome)
    interpretation = build_outcome_interpretation(outcome)
    assert interpretation["causal_inference_supported"] is False
    assert interpretation["allowed_use"] == "context_and_monitoring"
    assert "mistake" not in interpretation["summary"].lower()


def test_verified_outcome_without_evidence_is_rejected():
    with pytest.raises(ValueError, match="evidence"):
        validate_outcome(
            OutcomeInput(
                user_id="user-a",
                company_id="company-1",
                outcome_type=OutcomeType.SHUTDOWN,
                valence=OutcomeValence.NEGATIVE,
                summary="Operations ceased.",
                verification_state=OutcomeVerification.VERIFIED,
                materiality=5,
            )
        )
