from __future__ import annotations

from typing import Any, Iterable, Sequence
from uuid import uuid4

from identity.models import IdentityAdmission
from tenant_context import require_user_id
from triage.models import TriageAssessment, TriageDisposition


class TriageService:
    """Deterministic routing; never emits an investment recommendation."""

    def assess(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        admission: IdentityAdmission,
        prerequisites: Any,
        references: Sequence[dict[str, Any]] = (),
        trigger: str = "manual_lookup",
        observed_name: str = "",
    ) -> TriageAssessment:
        uid = require_user_id(user_id, context="TriageService.assess")
        prerequisites.require_tenant(uid, context="TriageService.assess")
        thesis = prerequisites.thesis_context if isinstance(prerequisites.thesis_context, dict) else {}
        policy_version = str(prerequisites.policy.policy_version_id)
        thesis_version = str(prerequisites.thesis_version_id)
        reasons: list[str] = []
        missing: list[str] = []
        verified = sum(1 for ref in references if ref.get("verified"))
        if admission.confidence < 0.5:
            return self._result(uid, opportunity_id, TriageDisposition.INSUFFICIENT_EVIDENCE,
                                ["identity_confidence_below_triage_floor"], ["verified_identity_reference"],
                                thesis_version, policy_version, trigger, 25, admission.confidence)
        exclusions = {str(item).strip().lower() for item in thesis.get("exclusions", []) if str(item).strip()}
        observed_name = str(observed_name or "").strip().lower()
        if observed_name and observed_name in exclusions:
            return self._result(uid, opportunity_id, TriageDisposition.OUT_OF_MANDATE,
                                ["explicit_thesis_exclusion"], [], thesis_version, policy_version, trigger, 5, min(admission.confidence, 0.8))
        if verified == 0:
            missing.append("verified_source_reference")
        if missing:
            reasons.append("evidence_coverage_below_deep_review_threshold")
            return self._result(uid, opportunity_id, TriageDisposition.LIGHT_MONITOR,
                                reasons, missing, thesis_version, policy_version, trigger, 35, min(admission.confidence, 0.6))
        reasons.append("identity_and_source_evidence_support_deep_review")
        return self._result(uid, opportunity_id, TriageDisposition.DEEP_REVIEW, reasons, [], thesis_version,
                            policy_version, trigger, 70, min(admission.confidence, 1.0))

    @staticmethod
    def _result(user_id, opportunity_id, disposition, reasons, missing, thesis_version, policy_version, trigger, priority, confidence):
        return TriageAssessment(
            assessment_id=str(uuid4()), user_id=user_id, opportunity_id=opportunity_id,
            disposition=disposition, reasons=reasons, missing_information=missing,
            thesis_version_id=thesis_version, policy_version_id=policy_version,
            trigger=trigger, priority=priority, confidence=confidence,
        )
