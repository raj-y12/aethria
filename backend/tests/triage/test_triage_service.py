from types import SimpleNamespace

from identity.models import IdentityAdmission, IdentityStatus
from triage.models import TriageDisposition
from triage.service import TriageService


def _admission(confidence=1.0):
    return IdentityAdmission(
        user_id="fund-a", observation_id="obs-1", status=IdentityStatus.RESOLVED,
        company_id="co-1", opportunity_id="opp-1", confidence=confidence,
    )


def _prerequisites():
    return SimpleNamespace(
        thesis_context={}, thesis_version_id="thesis-1",
        policy=SimpleNamespace(policy_version_id="policy-1"),
        require_tenant=lambda *_args, **_kwargs: None,
    )


def test_every_resolved_opportunity_gets_visible_triage_disposition():
    assessment = TriageService().assess(
        user_id="fund-a", opportunity_id="opp-1", admission=_admission(),
        prerequisites=_prerequisites(), references=[],
    )
    assert assessment.disposition is TriageDisposition.LIGHT_MONITOR
    assert "verified_source_reference" in assessment.missing_information
    assert assessment.thesis_version_id == "thesis-1"


def test_verified_reference_routes_to_deep_review_without_investment_decision():
    assessment = TriageService().assess(
        user_id="fund-a", opportunity_id="opp-1", admission=_admission(),
        prerequisites=_prerequisites(), references=[{"verified": True}],
    )
    assert assessment.disposition is TriageDisposition.DEEP_REVIEW
    assert not hasattr(assessment, "recommendation")


def test_low_identity_confidence_stops_before_deep_review():
    assessment = TriageService().assess(
        user_id="fund-a", opportunity_id="opp-1", admission=_admission(0.3),
        prerequisites=_prerequisites(), references=[{"verified": True}],
    )
    assert assessment.disposition is TriageDisposition.INSUFFICIENT_EVIDENCE


def test_explicit_thesis_exclusion_is_visible_out_of_mandate():
    prerequisites = _prerequisites()
    prerequisites.thesis_context = {"exclusions": ["acme"]}
    assessment = TriageService().assess(
        user_id="fund-a", opportunity_id="opp-1", admission=_admission(),
        prerequisites=prerequisites, references=[{"verified": True}], observed_name="Acme",
    )
    assert assessment.disposition is TriageDisposition.OUT_OF_MANDATE
