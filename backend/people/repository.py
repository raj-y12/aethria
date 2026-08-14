"""Tenant-safe persistence for the bounded founder people projection."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from evidence.models import (
    AccessClass, ArtifactType, AssertionClass, ClaimEvidenceLinkInput,
    ClaimInput, EvidenceArtifactInput, EvidenceItemInput, EvidenceRelationship,
    TrustClass,
)
from people.service import canonicalize_founder_resolution
from tenant_context import require_user_id


class PeopleRepository:
    def __init__(self, pool: Any, *, identity_repository: Any, evidence_repository: Any):
        self.pool = pool
        self.identity_repository = identity_repository
        self.evidence_repository = evidence_repository

    async def persist_founder_resolution(self, *, user_id: str, startup_id: str, resolution: Any) -> list[str]:
        uid = require_user_id(user_id, context="PeopleRepository.persist_founder_resolution")
        opportunity = await self.identity_repository.get_opportunity_by_legacy_projection(
            user_id=uid, legacy_startup_id=startup_id
        )
        if opportunity is None:
            return []
        drafts = canonicalize_founder_resolution(resolution, company_id=str(opportunity.company_id))
        persisted: list[str] = []
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for draft in drafts:
                    if not draft.persistable:
                        continue
                    person_id = await self._find_person(conn, uid, draft)
                    if person_id is None:
                        person_id = str(uuid4())
                        await conn.execute(
                            """insert into public.people
                            (person_id,user_id,canonical_name,normalized_name,identity_confidence)
                            values ($1,$2,$3,$4,$5)""",
                            person_id, uid, draft.canonical_name, draft.normalized_name,
                            draft.identity_confidence,
                        )
                    for identifier in draft.identifiers:
                        await conn.execute(
                            """insert into public.person_identifiers
                            (identifier_id,user_id,person_id,identifier_type,normalized_value,raw_value,confidence)
                            values ($1,$2,$3,$4,$5,$6,$7)
                            on conflict (identifier_id) do nothing""",
                            str(uuid4()), uid, person_id, identifier.identifier_type,
                            identifier.normalized_value, identifier.raw_value, draft.identity_confidence,
                        )
                    claim_ids = await self._claims_for_draft(
                        uid=uid, company_id=str(opportunity.company_id), opportunity_id=str(opportunity.opportunity_id),
                        person_id=person_id, draft=draft,
                    )
                    role_claim = claim_ids.get("founder_current_role") or claim_ids.get("founder_identity")
                    await conn.execute(
                        """insert into public.company_people
                        (relationship_id,user_id,company_id,person_id,relationship_type,role,source_claim_id)
                        select $1,$2,$3,$4,$5,$6,$7
                        where not exists (select 1 from public.company_people where user_id=$2 and company_id=$3 and person_id=$4 and relationship_type=$5 and coalesce(role,'')=coalesce($6,''))""",
                        str(uuid4()), uid, str(opportunity.company_id), person_id,
                        draft.relationship_type, draft.role, role_claim,
                    )
                    for history in draft.history:
                        await conn.execute(
                            """insert into public.person_history
                            (history_id,user_id,person_id,company_id,history_type,organization_name,role,state,source_claim_id)
                            select $1,$2,$3,$4,$5,$6,$7,$8,$9
                            where not exists (select 1 from public.person_history where user_id=$2 and person_id=$3 and history_type=$5 and organization_name=$6)""",
                            str(uuid4()), uid, person_id, str(opportunity.company_id),
                            history.history_type, history.organization_name, history.role,
                            "conflicting" if draft.conflict_fields else history.state,
                            claim_ids.get("founder_previous_role" if history.history_type == "worked_at_company" else "founder_education"),
                        )
                    persisted.append(person_id)
        return persisted

    async def _find_person(self, conn: Any, user_id: str, draft: Any) -> str | None:
        strong = next((item for item in draft.identifiers if item.identifier_type in {"linkedin", "github", "x"}), None)
        if strong:
            row = await conn.fetchrow(
                """select person_id from public.person_identifiers
                   where user_id=$1 and identifier_type=$2 and normalized_value=$3
                   order by case when verification_status='verified' then 0 else 1 end, created_at limit 1""",
                user_id, strong.identifier_type, strong.normalized_value,
            )
            if row:
                return str(row["person_id"])
        row = await conn.fetchrow(
            """select p.person_id from public.people p join public.company_people cp
               on cp.user_id=p.user_id and cp.person_id=p.person_id
               where p.user_id=$1 and p.normalized_name=$2 and cp.company_id=$3 limit 1""",
            user_id, draft.normalized_name, draft.company_id,
        )
        return str(row["person_id"]) if row else None

    async def _claims_for_draft(self, *, uid: str, company_id: str, opportunity_id: str, person_id: str, draft: Any) -> dict[str, str]:
        result: dict[str, str] = {}
        evidence = list(draft.evidence_urls)
        if not evidence:
            return result
        source_url = evidence[0]
        artifact, items = await self.evidence_repository.ingest_artifact(
            EvidenceArtifactInput(
                user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
                artifact_type=ArtifactType.WEB_PAGE, source_uri=source_url,
                content_hash=hashlib.sha256(source_url.encode()).hexdigest(),
                trust_class=TrustClass.UNKNOWN, access_class=AccessClass.PUBLIC,
            ),
            items=[EvidenceItemInput(user_id=uid, item_type="founder_identity", display_excerpt=f"Founder evidence for {draft.canonical_name}", source_locator=source_url, extraction_confidence=draft.identity_confidence)],
        )
        item = items[0]
        claims = [("founder_identity", {"person_id": person_id, "name": draft.canonical_name}, f"{draft.canonical_name} is identified in founder evidence.")]
        if draft.role:
            claims.append(("founder_current_role", {"person_id": person_id, "role": draft.role}, f"{draft.canonical_name} is listed as {draft.role}."))
        if draft.history:
            if any(h.history_type == "worked_at_company" for h in draft.history):
                claims.append(("founder_previous_role", {"person_id": person_id, "organizations": [h.organization_name for h in draft.history if h.history_type == "worked_at_company"]}, f"{draft.canonical_name} has prior employment history."))
            if any(h.history_type == "education" for h in draft.history):
                claims.append(("founder_education", {"person_id": person_id, "institutions": [h.organization_name for h in draft.history if h.history_type == "education"]}, f"{draft.canonical_name} has reported education history."))
        if draft.conflict_fields:
            claims.append(("founder_conflict", {"person_id": person_id, "fields": list(draft.conflict_fields)}, f"Founder evidence conflicts on: {', '.join(draft.conflict_fields)}."))
        for claim_type, value, text in claims:
            record = await self.evidence_repository.create_claim(
                ClaimInput(user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
                           claim_type=claim_type, normalized_value=value, display_text=text,
                           assertion_class=AssertionClass.CONFLICTED if claim_type == "founder_conflict" else AssertionClass.UNVERIFIED,
                           confidence=draft.identity_confidence),
                links=[ClaimEvidenceLinkInput(user_id=uid, evidence_item_id=item.evidence_item_id, relationship=EvidenceRelationship.SUPPORTS, support_strength=draft.identity_confidence)],
                created_by="founder_resolver",
            )
            result[claim_type] = str(record["claim_id"])
        return result
