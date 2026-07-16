"""Bounded CSV/channel intake, confidential artifact registration, and outcomes."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from evidence.models import AccessClass, ArtifactType, EvidenceArtifactInput, TrustClass
from outcomes.models import (
    ImportSource,
    OutcomeInput,
    OutcomeType,
    OutcomeValence,
    OutcomeVerification,
)
from outcomes.repository import ImportPayloadConflict
from outcomes.service import ImportLimitError, parse_csv_candidates
from security.request_guards import require_authenticated_user, validate_route_id


router = APIRouter(tags=["channels", "outcomes"])


class CsvImportBody(BaseModel):
    source: ImportSource = ImportSource.CSV
    idempotency_key: str = Field(min_length=8, max_length=200)
    csv_text: str = Field(min_length=1, max_length=1_000_000)
    name_field: str = Field(default="company_name", min_length=1, max_length=100)
    domain_field: Optional[str] = Field(default="website", max_length=100)
    external_id_field: Optional[str] = Field(default=None, max_length=100)
    verify_domains: bool = False


class OutcomeBody(BaseModel):
    opportunity_id: Optional[str] = None
    outcome_type: OutcomeType
    valence: OutcomeValence
    summary: str = Field(min_length=3, max_length=2000)
    verification_state: OutcomeVerification = OutcomeVerification.UNVERIFIED
    materiality: int = Field(ge=1, le=5)
    effective_at: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    evidence_artifact_ids: List[str] = Field(default_factory=list, max_length=20)
    supersedes_outcome_id: Optional[str] = None


class ConfidentialArtifactBody(BaseModel):
    artifact_type: ArtifactType
    content_hash: str = Field(min_length=8, max_length=200)
    storage_reference: str = Field(min_length=3, max_length=2000)
    title: Optional[str] = Field(default=None, max_length=500)
    source_uri: Optional[str] = Field(default=None, max_length=2000)
    retention_policy: str = Field(min_length=3, max_length=100)
    published_at: Optional[datetime] = None
    effective_at: Optional[datetime] = None


def _repository(request: Request):
    repository = getattr(request.app.state, "channel_outcome_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Channel/outcome store unavailable")
    return repository


@router.post("/api/imports/csv")
async def import_csv(request: Request, body: CsvImportBody):
    user_id = require_authenticated_user(request)
    import_id = hashlib.sha256(f"{user_id}:{body.idempotency_key}".encode()).hexdigest()[:32]
    try:
        candidates = parse_csv_candidates(
            body.csv_text,
            source=body.source,
            import_id=import_id,
            name_field=body.name_field,
            domain_field=body.domain_field,
            external_id_field=body.external_id_field,
            verify_domains=body.verify_domains,
            max_rows=500,
        )
        return await _repository(request).process_import(
            user_id=user_id,
            idempotency_key=body.idempotency_key,
            source=body.source,
            file_hash=hashlib.sha256(body.csv_text.encode()).hexdigest(),
            field_mapping={
                "name_field": body.name_field,
                "domain_field": body.domain_field,
                "external_id_field": body.external_id_field,
                "verify_domains": body.verify_domains,
            },
            candidates=candidates,
            actor_id=user_id,
        )
    except (ImportLimitError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ImportPayloadConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/imports/{import_batch_id}")
async def get_import(request: Request, import_batch_id: str):
    validate_route_id(import_batch_id, field_name="import_batch_id")
    user_id = require_authenticated_user(request)
    result = await _repository(request).get_import(
        user_id=user_id, import_batch_id=import_batch_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return result


@router.post("/api/companies/{company_id}/outcomes")
async def create_outcome(request: Request, company_id: str, body: OutcomeBody):
    validate_route_id(company_id, field_name="company_id")
    if body.opportunity_id:
        validate_route_id(body.opportunity_id, field_name="opportunity_id")
    if body.supersedes_outcome_id:
        validate_route_id(body.supersedes_outcome_id, field_name="supersedes_outcome_id")
    for artifact_id in body.evidence_artifact_ids:
        validate_route_id(artifact_id, field_name="evidence_artifact_id")
    user_id = require_authenticated_user(request)
    try:
        values = body.model_dump(exclude={"observed_at"})
        if body.observed_at is not None:
            values["observed_at"] = body.observed_at
        return await _repository(request).create_outcome(
            OutcomeInput(user_id=user_id, company_id=company_id, **values),
            actor_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/companies/{company_id}/outcomes")
async def list_outcomes(
    request: Request, company_id: str, limit: int = Query(default=100, ge=1, le=200)
):
    validate_route_id(company_id, field_name="company_id")
    user_id = require_authenticated_user(request)
    return await _repository(request).list_outcomes(
        user_id=user_id, company_id=company_id, limit=limit
    )


@router.get("/api/outcomes/coverage")
async def get_outcome_coverage(request: Request):
    user_id = require_authenticated_user(request)
    return await _repository(request).get_outcome_coverage(user_id=user_id)


@router.post("/api/opportunities/{opportunity_id}/confidential-artifacts")
async def register_confidential_artifact(
    request: Request, opportunity_id: str, body: ConfidentialArtifactBody
):
    validate_route_id(opportunity_id, field_name="opportunity_id")
    if body.artifact_type not in {ArtifactType.PITCH_DECK, ArtifactType.EMAIL}:
        raise HTTPException(status_code=422, detail="Only pitch deck or email metadata is accepted")
    user_id = require_authenticated_user(request)
    repository = getattr(request.app.state, "evidence_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Evidence store unavailable")
    identity_repository = getattr(request.app.state, "identity_repository", None)
    if identity_repository is None:
        raise HTTPException(status_code=503, detail="Identity store unavailable")
    opportunity = await identity_repository.get_opportunity(
        user_id=user_id, opportunity_id=opportunity_id
    )
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    artifact, _ = await repository.ingest_artifact(
        EvidenceArtifactInput(
            user_id=user_id,
            opportunity_id=opportunity_id,
            artifact_type=body.artifact_type,
            source_uri=body.source_uri,
            title=body.title,
            content_hash=body.content_hash,
            storage_reference=body.storage_reference,
            trust_class=TrustClass.FOUNDER,
            access_class=AccessClass.TENANT_CONFIDENTIAL,
            retention_policy=body.retention_policy,
            untrusted_input=True,
            published_at=body.published_at,
            effective_at=body.effective_at,
        ),
        items=(),
    )
    return {
        "artifact_id": artifact.artifact_id,
        "opportunity_id": artifact.opportunity_id,
        "artifact_type": artifact.artifact_type.value,
        "access_class": artifact.access_class.value,
        "retention_policy": artifact.retention_policy,
        "untrusted_input": artifact.untrusted_input,
        "storage_reference_exposed": False,
        "created_at": artifact.created_at.isoformat(),
    }
