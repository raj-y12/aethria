import pytest

from identity.models import (
    IdentifierType,
    SourceObservationInput,
    VerificationStatus,
)
from identity.normalization import (
    extract_identifier_candidates,
    normalize_alias,
    normalize_domain,
    normalize_provider_identifier,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.Acme.com/about", "acme.com"),
        ("acme.co.uk", "acme.co.uk"),
        ("www.acme.ai/", "acme.ai"),
        ("https://linkedin.com/company/acme", None),
        ("https://techcrunch.com/acme", None),
        ("", None),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        (IdentifierType.LINKEDIN, "https://linkedin.com/company/Acme/", "acme"),
        (IdentifierType.CRUNCHBASE, "https://crunchbase.com/organization/Acme-Inc", "acme-inc"),
        (IdentifierType.YC, "https://www.ycombinator.com/companies/acme", "acme"),
        (IdentifierType.DEALROOM, "https://app.dealroom.co/companies/acme", "acme"),
        (IdentifierType.EXTERNAL, " Vendor:ABC-123 ", "vendor:abc-123"),
    ],
)
def test_provider_identifiers_are_provider_scoped(kind, raw, expected):
    assert normalize_provider_identifier(kind, raw) == expected


def test_alias_normalization_is_not_an_identity_key():
    assert normalize_alias("  The Acme, Inc. ") == "the acme inc"


def test_operator_confirmed_picker_domain_is_verified():
    observation = SourceObservationInput(
        user_id="fund-a",
        channel="manual_lookup",
        observed_name="Acme",
        observed_domain="https://acme.com/about",
        source_metadata={"operator_confirmed_identity": True},
        resolution_payload={
            "resolution_status": "FOUND",
            "confidence": 0.94,
            "website": "https://acme.com",
        },
    )

    identifiers = extract_identifier_candidates(observation)

    domain = next(item for item in identifiers if item.identifier_type is IdentifierType.DOMAIN)
    assert domain.normalized_value == "acme.com"
    assert domain.verification_status is VerificationStatus.VERIFIED
    assert domain.is_primary is True


def test_autonomous_domain_without_corroboration_remains_unverified():
    observation = SourceObservationInput(
        user_id="fund-a",
        channel="autonomous_discovery",
        observed_name="Acme",
        observed_domain="acme.com",
        resolution_payload={"resolution_status": "PARTIAL", "confidence": 0.7},
    )

    identifiers = extract_identifier_candidates(observation)

    assert identifiers[0].verification_status is VerificationStatus.UNVERIFIED
