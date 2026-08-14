"""Canonical application service for a manual lookup.

This is deliberately orchestration-only: identity, evidence, and evaluation
repositories remain the owners of their transactional writes.  The service makes
the ordering and fail-closed gates explicit so callers cannot accidentally run a
thesis-blind evaluation or evaluate an ambiguous company.
"""

from __future__ import annotations

import hashlib
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
from agents.canonical import DeterministicPartner, EvidenceReviewer
from regulatory_context import (
    assemble_regulatory_context,
    deduplicate_references,
    derive_regulatory_claims,
)
from canonical_scout_claims import derive_scout_claims


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
        references = deduplicate_references(references)
        claims = list(claims)
        if scout_output is not None:
            existing_claim_types = {str(raw.get("claim_type") or "") for raw in claims}
            claims.extend(
                raw for raw in derive_scout_claims(scout_output)
                if raw.get("claim_type") not in existing_claim_types
            )
        admission: IdentityAdmission = await self.identity_service.admit(observation)
        if admission.blocks_evaluation or not admission.opportunity_id or not admission.company_id:
            return PipelineResult(
                status="blocked", code="identity_review_required", user_id=uid,
                observation_id=admission.observation_id,
                company_id=admission.company_id, metadata={"identity_case_id": admission.identity_case_id},
            )

        # Resolve all prerequisites before touching evaluation.  The loader is
        # intentionally injected to make the gate testable and tenant explicit.
        prerequisites = await self.prerequisites_loader(user_id=uid)
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
                return PipelineResult(
                    status="completed", code=f"triage_{assessment.disposition.value}",
                    user_id=uid, opportunity_id=admission.opportunity_id,
                    company_id=admission.company_id, observation_id=admission.observation_id,
                    metadata={"triage": assessment.model_dump(mode="json")},
                )

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
                    trust_class=TrustClass.OFFICIAL if ref.get("official") else TrustClass.UNKNOWN,
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
                    verification_state=VerificationState.VERIFIED if ref.get("verified") else VerificationState.UNVERIFIED,
                    source_quality=float(ref.get("source_quality") or 0),
                    extraction_confidence=float(ref.get("confidence") or 0),
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

        evaluation = await self.evaluation_repository.evaluate(
            user_id=uid, opportunity_id=admission.opportunity_id,
            actor_id=actor_id or uid, trigger_type=trigger,
            policy=prerequisites.policy,
            thesis_version_id=prerequisites.thesis_version_id,
            judgment_audit=judgment_audit,
        )
        regulatory_context = assemble_regulatory_context(
            claims=persisted_claims,
            evidence=persisted_links,
        )
        evidence_review = EvidenceReviewer().review(
            evaluation, regulatory_context=regulatory_context
        )
        partner_route = DeterministicPartner().route(evaluation, evidence_review)
        return PipelineResult(
            status="completed", code="opportunity_evaluated", user_id=uid,
            opportunity_id=admission.opportunity_id, company_id=admission.company_id,
            observation_id=admission.observation_id, evaluation=evaluation,
            metadata={
                "artifact_ids": artifact_ids,
                "evidence_review": evidence_review.model_dump(mode="json"),
                "partner_route": partner_route.model_dump(mode="json"),
                "regulatory_context": regulatory_context,
                "legacy_compatibility": True,
            },
        )
