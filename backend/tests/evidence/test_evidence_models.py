import pytest
from pydantic import ValidationError

from evidence.models import (
    ArtifactType,
    AssertionClass,
    ClaimInput,
    EvidenceArtifactInput,
    EvidenceItemInput,
    TrustClass,
)
from evidence.service import EvidenceStandardError, validate_claim_standard


def test_artifact_and_item_contracts_are_tenant_scoped_and_bounded():
    artifact = EvidenceArtifactInput(
        user_id="fund-a",
        company_id="company-1",
        artifact_type=ArtifactType.WEB_PAGE,
        source_uri="https://acme.com/about",
        content_hash="sha256:abc",
        trust_class=TrustClass.OFFICIAL,
    )
    item = EvidenceItemInput(
        user_id="fund-a",
        item_type="founder_history",
        display_excerpt="Founder previously built and sold a workflow company.",
        source_locator="paragraph:4",
        extraction_confidence=0.9,
    )

    assert artifact.user_id == item.user_id == "fund-a"
    with pytest.raises(ValidationError):
        EvidenceItemInput(
            user_id="fund-a",
            item_type="x",
            display_excerpt="x" * 2001,
        )


def test_model_inferred_founder_personality_label_is_blocked():
    claim = ClaimInput(
        user_id="fund-a",
        company_id="company-1",
        claim_type="founder_trait",
        display_text="The founder is magnetic and obsessive.",
        assertion_class=AssertionClass.MODEL_INFERRED,
        confidence=0.8,
    )

    with pytest.raises(EvidenceStandardError, match="personality"):
        validate_claim_standard(claim, evidence_link_count=2)


def test_operator_founder_observation_requires_attribution():
    unattributed = ClaimInput(
        user_id="fund-a",
        company_id="company-1",
        claim_type="founder_observation",
        display_text="Founder answered customer questions with precise examples.",
        assertion_class=AssertionClass.OPERATOR_ASSERTED,
    )
    with pytest.raises(EvidenceStandardError, match="attribution"):
        validate_claim_standard(unattributed, evidence_link_count=0)

    attributed = unattributed.model_copy(update={"operator_attribution": "partner-interview-2026-07-15"})
    validate_claim_standard(attributed, evidence_link_count=0)


def test_externally_verified_material_claim_requires_evidence_link():
    claim = ClaimInput(
        user_id="fund-a",
        company_id="company-1",
        claim_type="customer_count",
        normalized_value={"value": 42},
        display_text="Acme has 42 paying customers.",
        assertion_class=AssertionClass.EXTERNALLY_VERIFIED,
        confidence=0.95,
        material=True,
    )

    with pytest.raises(EvidenceStandardError, match="evidence"):
        validate_claim_standard(claim, evidence_link_count=0)
    validate_claim_standard(claim, evidence_link_count=1)
