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
    ) -> PipelineResult:
        uid = require_user_id(user_id, context="OpportunityPipeline.process")
        if observation.user_id != uid:
            raise ValueError("observation tenant does not match pipeline tenant")
        references = list(references)
        claims = list(claims)
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
                    access_class=AccessClass.PUBLIC, untrusted_input=True,
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

        # Claims are supplied by a bounded extractor; arbitrary model prose is
        # never converted into a decision implicitly.
        for raw in claims:
            linked_ids = raw.get("evidence_item_ids") or evidence_item_ids
            links = [ClaimEvidenceLinkInput(
                user_id=uid, evidence_item_id=str(item_id),
                relationship=EvidenceRelationship.SUPPORTS,
                support_strength=float(raw.get("support_strength") or 0),
            ) for item_id in linked_ids]
            await self.evidence_repository.create_claim(
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

        evaluation = await self.evaluation_repository.evaluate(
            user_id=uid, opportunity_id=admission.opportunity_id,
            actor_id=actor_id or uid, trigger_type=trigger,
            policy=prerequisites.policy,
            thesis_version_id=prerequisites.thesis_version_id,
        )
        return PipelineResult(
            status="completed", code="opportunity_evaluated", user_id=uid,
            opportunity_id=admission.opportunity_id, company_id=admission.company_id,
            observation_id=admission.observation_id, evaluation=evaluation,
            metadata={"artifact_ids": artifact_ids},
        )
