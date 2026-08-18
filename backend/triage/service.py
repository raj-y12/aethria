from __future__ import annotations

from typing import Any, Iterable, Sequence
from uuid import uuid4

from core.policy_resolver import get_triage_rules
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
        # Fixed 2026-08-18 (audit HIGH-H6): the identity-confidence floor and
        # every disposition's priority/confidence-cap used to be bare Python
        # literals -- a direct AGENTS.md invariant #3 violation, and the
        # identity-confidence floor in particular is the sole gate between
        # DEEP_REVIEW and a permanent drop. Now sourced from versioned config,
        # same pattern as partner_rules/reviewer_rules/evaluation_rubric.
        rules = get_triage_rules()
        dispositions = rules["dispositions"]
        if admission.confidence < rules["identity_confidence_floor"]:
            d = dispositions["insufficient_evidence"]
            return self._result(uid, opportunity_id, TriageDisposition.INSUFFICIENT_EVIDENCE,
                                ["identity_confidence_below_triage_floor"], ["verified_identity_reference"],
                                thesis_version, policy_version, trigger, d["priority"], admission.confidence)
        exclusions = {str(item).strip().lower() for item in thesis.get("exclusions", []) if str(item).strip()}
        observed_name = str(observed_name or "").strip().lower()
        if observed_name and observed_name in exclusions:
            d = dispositions["out_of_mandate"]
            return self._result(uid, opportunity_id, TriageDisposition.OUT_OF_MANDATE,
                                ["explicit_thesis_exclusion"], [], thesis_version, policy_version, trigger,
                                d["priority"], min(admission.confidence, d["confidence_cap"]))
        if verified == 0:
            missing.append("verified_source_reference")
        if missing:
            reasons.append("evidence_coverage_below_deep_review_threshold")
            d = dispositions["light_monitor"]
            return self._result(uid, opportunity_id, TriageDisposition.LIGHT_MONITOR,
                                reasons, missing, thesis_version, policy_version, trigger,
                                d["priority"], min(admission.confidence, d["confidence_cap"]))
        reasons.append("identity_and_source_evidence_support_deep_review")
        d = dispositions["deep_review"]
        return self._result(uid, opportunity_id, TriageDisposition.DEEP_REVIEW, reasons, [], thesis_version,
                            policy_version, trigger, d["priority"], min(admission.confidence, d["confidence_cap"]))

    @staticmethod
    def _result(user_id, opportunity_id, disposition, reasons, missing, thesis_version, policy_version, trigger, priority, confidence):
        return TriageAssessment(
            assessment_id=str(uuid4()), user_id=user_id, opportunity_id=opportunity_id,
            disposition=disposition, reasons=reasons, missing_information=missing,
            thesis_version_id=thesis_version, policy_version_id=policy_version,
            trigger=trigger, priority=priority, confidence=confidence,
        )
