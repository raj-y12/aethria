"""Regression coverage (audit LOW): ManualLookupBody.references/.claims are
freeform dicts with a list-length cap but no per-field string-length cap --
inconsistent with company_name/website/lookup_id, which all use max_length.
50 claims each carrying a multi-megabyte string field is still "50 items"."""

import pytest
from pydantic import ValidationError

from routers.opportunities import ManualLookupBody


def test_manual_lookup_body_accepts_normal_sized_reference_and_claim_fields():
    body = ManualLookupBody(
        company_name="Acme",
        references=[{"url": "https://acme.com", "title": "About Acme"}],
        claims=[{"text": "Acme raised a Series A."}],
    )
    assert body.references[0]["url"] == "https://acme.com"


def test_manual_lookup_body_rejects_an_oversized_string_value_in_a_claim():
    with pytest.raises(ValidationError, match="exceeds"):
        ManualLookupBody(
            company_name="Acme",
            claims=[{"text": "x" * 10_001}],
        )


def test_manual_lookup_body_rejects_an_oversized_string_value_in_a_reference():
    with pytest.raises(ValidationError, match="exceeds"):
        ManualLookupBody(
            company_name="Acme",
            references=[{"title": "x" * 10_001}],
        )
