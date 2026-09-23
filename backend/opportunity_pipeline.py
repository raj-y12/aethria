"""Canonical application service for a manual lookup.

This is deliberately orchestration-only: identity, evidence, and evaluation
repositories remain the owners of their transactional writes.  The service makes
the ordering and fail-closed gates explicit so callers cannot accidentally run a
thesis-blind evaluation or evaluate an ambiguous company.
"""

from __future__ import annotations

import hashlib
from uuid import uuid4

from evaluation_v2.provenance import PipelineBinding
from investment_analysis.model_gateway import AnalysisBlocked
from pipeline_state import pipeline_stage_log
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional

from evidence.models import (
    AccessClass,
    ArtifactType,
    AssertionClass,
    ClaimEvidenceLinkInput,
    ClaimInput,
    EvidenceArtifactInput,
    EvidenceItemInput,
    EvidenceRelationship,
    TrustClass,
    VerificationState,
)
from evidence.service import detect_prompt_injection
from identity.models import IdentityAdmission, SourceObservationInput
from tenant_context import require_user_id
from triage.models import TriageDisposition
from context import (
    assemble_regulatory_context,
    deduplicate_references,
    derive_regulatory_claims,
    derive_scout_claims,
)


@dataclass(frozen=True)
class PipelineResult:
    status: str
    code: str
    user_id: str
    opportunity_id: Optional[str] = None
    company_id: Optional[str] = None
    observation_id: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    pipeline_run_id: Optional[str] = None
    pipeline_trace: list[Dict[str, Any]] = field(default_factory=list)


def _evaluation_response_metadata(evaluation: dict, regulatory_context: str = "") -> tuple[dict, dict]:
    """Preserve manual-lookup response fields without executing extra agents."""
    recommendation = evaluation.get("recommendation") or {}
    missing = [str(value) for value in recommendation.get("missing_information") or [] if str(value).strip()]
    scored = sum(item.get("score") is not None for item in evaluation.get("criteria") or [])
    drivers = [str(value) for value in recommendation.get("decision_drivers") or []]
    risks = [str(value) for value in recommendation.get("principal_risks") or []]
    confidence = float(recommendation.get("confidence") or 0)
    if not 0 <= confidence <= 1:
        raise ValueError("invalid recommendation confidence")
    review = {
        "evaluation_id": str(evaluation.get("evaluation_id") or ""),
        "recommendation_id": str(evaluation.get("recommendation_id") or ""),
        "evidence_coverage": "sufficient" if scored and not missing else "insufficient",
        "scored_criteria": scored, "missing_information": missing,
        "principal_risks": risks, "decision_drivers": drivers,
        "confidence": confidence, "regulatory_context": regulatory_context,
    }
    state = str(recommendation.get("state") or "insufficient_evidence")
    route = state if state in {"advance", "monitor", "pass", "insufficient_evidence"} else "insufficient_evidence"
    return review, {
        "recommendation_id": review["recommendation_id"], "route": route,
        "human_review_required": bool(recommendation.get("human_review_required", True)),
        "rationale": (drivers + risks)[:20],
    }


class OpportunityPipeline:
    """Run one canonical manual lookup from observation to recommendation."""

    def __init__(
        self,
        *,
        identity_service: Any,
        evidence_repository: Any,
        evaluation_repository: Any,
        prerequisites_loader: Any,
        authority_service: Any = None,
        triage_service: Any = None,
        triage_repository: Any = None,
    ) -> None:
        self.identity_service = identity_service
        self.evidence_repository = evidence_repository
        self.evaluation_repository = evaluation_repository
        self.prerequisites_loader = prerequisites_loader
        self.authority_service = authority_service
        self.triage_service = triage_service
        self.triage_repository = triage_repository

    async def process(
        self,
        *,
        user_id: str,
        observation: SourceObservationInput,
        actor_id: Optional[str] = None,
        trigger: str = "manual_lookup",
        references: Iterable[Dict[str, Any]] = (),
        claims: Iterable[Dict[str, Any]] = (),
        scout_output: Optional[Dict[str, Any]] = None,
        judgment_audit: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        uid = require_user_id(user_id, context="OpportunityPipeline.process")
        if observation.user_id != uid:
            raise ValueError("observation tenant does not match pipeline tenant")
        pipeline_run_id = str(uuid4())
        trace: list[Dict[str, Any]] = []

        def record(stage: str, status: str, **metadata: Any) -> None:
            trace.append({"stage": stage, "status": status, **metadata})
            pipeline_stage_log(
                pipeline_run_id, startup_id="", user_id=uid, stage=stage, phase=status,
            )

        async def observe(stage: str, awaitable: Any) -> Any:
            record(stage, "STARTED")
            try:
                value = await awaitable
            except AnalysisBlocked as exc:
                record(stage, "BLOCKED", code=exc.code)
                raise
            except Exception:
                record(stage, "FAILED")
                raise
            record(stage, "DONE")
            return value

        references = deduplicate_references(references)
        # Fixed 2026-08-18 (audit HIGH-H8): claims arriving through this
        # parameter come straight from an HTTP request body (the only real
        # caller is the manual-lookup router) with a fully client-controlled
        # assertion_class that defaulted to EXTERNALLY_VERIFIED -- the
        # highest trust tier -- when simply omitted. Force every claim
        # entering here to operator_asserted before it's merged with the
        # server-derived scout/regulatory claims below, which set their own
        # assertion_class deterministically and are left untouched.
        claims = [{**raw, "assertion_class": "operator_asserted"} for raw in claims]
        if scout_output is not None:
            existing_claim_types = {str(raw.get("claim_type") or "") for raw in claims}
            claims.extend(
                raw for raw in derive_scout_claims(scout_output)
                if raw.get("claim_type") not in existing_claim_types
            )
        admission: IdentityAdmission = await observe("identity", self.identity_service.admit(observation))
        if admission.blocks_evaluation or not admission.opportunity_id or not admission.company_id:
            record("identity", "BLOCKED")
            return PipelineResult(
                pipeline_run_id=pipeline_run_id, pipeline_trace=trace,
                status="blocked", code="identity_review_required", user_id=uid,
                observation_id=admission.observation_id,
                company_id=admission.company_id, metadata={"identity_case_id": admission.identity_case_id},
            )

        # Resolve all prerequisites before touching evaluation.  The loader is
        # intentionally injected to make the gate testable and tenant explicit.
        prerequisites = await observe("prerequisites", self.prerequisites_loader(user_id=uid))
        if hasattr(prerequisites, "require_tenant"):
            prerequisites.require_tenant(uid, context="OpportunityPipeline.process")

        if self.triage_service is not None:
            assessment = self.triage_service.assess(
                user_id=uid, opportunity_id=admission.opportunity_id,
                admission=admission, prerequisites=prerequisites,
                references=list(references), trigger=trigger,
                observed_name=observation.observed_name,
            ).model_copy(update={"observation_ids": [admission.observation_id]})
            if self.triage_repository is not None:
                await self.triage_repository.create(assessment)
            if assessment.disposition is not TriageDisposition.DEEP_REVIEW:
                record("evaluation", "SKIPPED", reason=assessment.disposition.value)
                return PipelineResult(
                    pipeline_run_id=pipeline_run_id, pipeline_trace=trace,
                    status="completed", code=f"triage_{assessment.disposition.value}",
                    user_id=uid, opportunity_id=admission.opportunity_id,
                    company_id=admission.company_id, observation_id=admission.observation_id,
                    metadata={"triage": assessment.model_dump(mode="json")},
                )

        record("evidence", "STARTED")
        artifact_ids: list[str] = []
        evidence_item_ids: list[str] = []
        reference_items: list[list[Any]] = []
        for ref in references:
            uri = str(ref.get("url") or ref.get("source_uri") or "").strip()
            if not uri:
                continue
            content = str(ref.get("content") or ref.get("excerpt") or uri)
            artifact, items = await self.evidence_repository.ingest_artifact(
                EvidenceArtifactInput(
                    user_id=uid, company_id=admission.company_id,
                    opportunity_id=admission.opportunity_id,
                    source_observation_id=admission.observation_id,
                    artifact_type=ArtifactType.WEB_PAGE,
                    source_uri=uri, title=ref.get("title"),
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    # Fixed 2026-08-18 (audit HIGH-H8): trust_class/verification_state
                    # used to be client-settable booleans (ref.get("official")/
                    # ref.get("verified")) forwarded straight into the evidence
                    # feeding evaluate() -- any authenticated user could mark
                    # their own submitted reference "official"/"verified" and
                    # have the decision engine treat it as externally verified
                    # fact. Both are now server-derived, matching the same
                    # TrustClass.OPERATOR/VerificationState.VERIFIED... except
                    # here UNVERIFIED, since -- unlike the confidential-evidence
                    # endpoint's single operator-authored note -- this accepts
                    # bulk, self-graded, structured data at conviction-bearing
                    # volume with no way to verify it server-side. Leaving it
                    # UNVERIFIED means the existing require_verified_evidence
                    # policy gate (evaluation_v2/service.py) correctly excludes
                    # it from automated scoring eligibility, the same mechanism
                    # already governing every other evidence path.
                    trust_class=TrustClass.OPERATOR,
                    access_class=AccessClass(str(ref.get("access_class") or AccessClass.PUBLIC.value)),
                    untrusted_input=True,
                    prompt_injection_detected=detect_prompt_injection(content),
                    effective_at=ref.get("effective_at"),
                ),
                items=[EvidenceItemInput(
                    user_id=uid, item_type=str(ref.get("item_type") or "source_excerpt"),
                    normalized_value=dict(ref.get("normalized_value") or {}),
                    display_excerpt=content[:2000], source_locator=uri,
                    effective_at=ref.get("effective_at"),
                    verification_state=VerificationState.UNVERIFIED,
                    source_quality=float(ref.get("source_quality") or 0),
                    extraction_confidence=float(ref.get("confidence") or 0),
                    operator_attribution=actor_id or uid,
                )],
            )
            artifact_ids.append(artifact.artifact_id)
            evidence_item_ids.extend(
                str(item.evidence_item_id) for item in items
                if getattr(item, "evidence_item_id", None)
            )
            reference_items.append(list(items))

        # Claims are supplied by a bounded extractor; arbitrary model prose is
        # never converted into a decision implicitly.
        existing_claim_types = {str(raw.get("claim_type") or "") for raw in claims}
        regulatory_claims = [
            raw for raw in derive_regulatory_claims(references)
            if raw.get("claim_type") not in existing_claim_types
        ]
        pending_claims = claims + regulatory_claims
        persisted_claims: list[dict[str, Any]] = []
        persisted_links: list[dict[str, Any]] = []
        evidence_details = {
            str(item.evidence_item_id): {
                "display_excerpt": getattr(item, "display_excerpt", ""),
                "source_locator": getattr(item, "source_locator", ""),
            }
            for items in reference_items
            for item in items
            if getattr(item, "evidence_item_id", None)
        }
        for raw in pending_claims:
            supporting_ids = [
                str(item.evidence_item_id)
                for index in raw.get("_supporting_indexes", [])
                if 0 <= index < len(reference_items)
                for item in reference_items[index]
                if getattr(item, "evidence_item_id", None)
            ]
            contradicting_ids = [
                str(item.evidence_item_id)
                for index in raw.get("_contradicting_indexes", [])
                if 0 <= index < len(reference_items)
                for item in reference_items[index]
                if getattr(item, "evidence_item_id", None)
            ]
            linked_ids = raw.get("evidence_item_ids") or supporting_ids or evidence_item_ids
            links = [ClaimEvidenceLinkInput(
                user_id=uid, evidence_item_id=str(item_id),
                relationship=EvidenceRelationship.SUPPORTS,
                support_strength=float(raw.get("support_strength") or 0),
            ) for item_id in linked_ids]
            links.extend(ClaimEvidenceLinkInput(
                user_id=uid, evidence_item_id=item_id,
                relationship=EvidenceRelationship.CONTRADICTS,
                support_strength=float(raw.get("support_strength") or 0),
                rationale="Decision-time regulatory evidence conflicts with this claim.",
            ) for item_id in contradicting_ids if item_id not in linked_ids)
            persisted = await self.evidence_repository.create_claim(
                ClaimInput(
                    user_id=uid, company_id=admission.company_id,
                    opportunity_id=admission.opportunity_id,
                    claim_type=str(raw.get("claim_type") or "unknown"),
                    normalized_value=dict(raw.get("normalized_value") or {}),
                    display_text=str(raw.get("display_text") or "").strip(),
                    assertion_class=AssertionClass(str(raw.get("assertion_class") or AssertionClass.EXTERNALLY_VERIFIED.value)),
                    confidence=float(raw.get("confidence") or 0),
                    material=bool(raw.get("material", True)),
                ),
                links=links, created_by=actor_id or uid,
            )
            claim_id = str(persisted.get("claim_id") or "")
            persisted_claims.append({**persisted, "claim_id": claim_id})
            persisted_links.extend(
                {
                    "claim_id": claim_id,
                    **link.model_dump(mode="json"),
                    **evidence_details.get(link.evidence_item_id, {}),
                }
                for link in links
            )

        record("evidence", "DONE", artifact_ids=artifact_ids, claim_ids=[item["claim_id"] for item in persisted_claims])
        evaluation = await observe("canonical_evaluation", self.evaluation_repository.evaluate(
            user_id=uid, opportunity_id=admission.opportunity_id,
            actor_id=actor_id or uid, trigger_type=trigger,
            policy=prerequisites.policy,
            thesis_version_id=prerequisites.thesis_version_id,
            judgment_audit=judgment_audit,
            pipeline_binding=PipelineBinding(
                user_id=uid, pipeline_run_id=pipeline_run_id,
                pipeline_entry_type="opportunity_manual_lookup", company_id=admission.company_id,
            ),
        ))
        regulatory_context = assemble_regulatory_context(
            claims=persisted_claims,
            evidence=persisted_links,
        )
        evidence_review, partner_route = _evaluation_response_metadata(evaluation, regulatory_context)
        analysis = (evaluation.get("judgment_audit") or {}).get("investment_analysis")
        return PipelineResult(
            pipeline_run_id=pipeline_run_id, pipeline_trace=trace,
            status="completed", code="opportunity_evaluated", user_id=uid,
            opportunity_id=admission.opportunity_id, company_id=admission.company_id,
            observation_id=admission.observation_id, evaluation=evaluation,
            metadata={
                "artifact_ids": artifact_ids,
                "evidence_review": evidence_review,
                "partner_route": partner_route,
                "regulatory_context": regulatory_context,
                "legacy_compatibility": True,
                "investment_analysis_trace": (analysis or {}).get("trace", []),
            },
        )
