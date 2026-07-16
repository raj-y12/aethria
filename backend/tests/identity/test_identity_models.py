import pytest

from identity.models import (
    IdentityAdmission,
    IdentityCandidate,
    IdentityStatus,
    OpportunityState,
    SourceChannel,
    SourceObservationInput,
)


def test_observation_requires_explicit_tenant_and_channel():
    value = SourceObservationInput(
        user_id="fund-a",
        channel="manual_lookup",
        observed_name="  Acme  ",
    )

    assert value.user_id == "fund-a"
    assert value.channel is SourceChannel.MANUAL_LOOKUP
    assert value.observed_name == "Acme"
    with pytest.raises(ValueError):
        SourceObservationInput(
            user_id="", channel="manual_lookup", observed_name="Acme"
        )


def test_observation_rejects_blank_company_name():
    with pytest.raises(ValueError):
        SourceObservationInput(
            user_id="fund-a", channel="manual_lookup", observed_name=" "
        )


def test_identity_admission_preserves_explicit_blocking_semantics():
    admission = IdentityAdmission(
        user_id="fund-a",
        observation_id="observation-1",
        status=IdentityStatus.AMBIGUOUS,
        identity_case_id="case-1",
        confidence=0.72,
        blocks_evaluation=True,
        candidates=[
            IdentityCandidate(
                canonical_name="Acme",
                canonical_domain="acme.com",
                confidence=0.82,
                evidence_urls=["https://example.com/acme"],
            )
        ],
    )

    assert admission.company_id is None
    assert admission.opportunity_id is None
    assert admission.blocks_evaluation is True


def test_phase2_enum_vocabulary_is_stable():
    assert {value.value for value in SourceChannel} == {
        "manual_lookup",
        "autonomous_discovery",
        "inbound",
        "outbound",
        "referral",
        "event",
        "portfolio_intro",
        "import",
        "crm_import",
        "backfill",
    }
    assert {value.value for value in OpportunityState} == {
        "discovered",
        "identity_review",
        "active_review",
        "monitor",
        "advance",
        "pass",
        "invested",
        "archived",
    }
