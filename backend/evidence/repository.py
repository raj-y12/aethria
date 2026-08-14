"""Transactional evidence/claim repository with tenant-safe read projections."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from evidence.models import (
    ClaimEvidenceLinkInput,
    ClaimInput,
    ClaimStatus,
    EvidenceArtifactInput,
    EvidenceArtifactRecord,
    EvidenceItemInput,
    EvidenceItemRecord,
    EvidencePlanRecord,
)
from evidence.service import validate_claim_standard
from tenant_context import require_user_id
from utils.db_rows import db_row


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


class EvidenceRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    @staticmethod
    async def _outbox(
        conn: Any,
        *,
        user_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id, user_id, aggregate_type, aggregate_id, event_type,
              event_version, payload, publication_attempts, next_attempt_at, created_at
            ) values ($1, $2, $3, $4, $5, 1, $6::jsonb, 0, now(), now())
            """,
            str(uuid4()), user_id, aggregate_type, aggregate_id, event_type, json.dumps(payload),
        )

    async def ingest_artifact(
        self,
        artifact: EvidenceArtifactInput,
        *,
        items: Sequence[EvidenceItemInput] = (),
    ) -> tuple[EvidenceArtifactRecord, List[EvidenceItemRecord]]:
        uid = require_user_id(artifact.user_id, context="EvidenceRepository.ingest_artifact")
        if any(item.user_id != uid for item in items):
            raise ValueError("Evidence item tenant does not match artifact tenant")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    insert into public.evidence_artifacts (
                      artifact_id, user_id, company_id, opportunity_id,
                      source_observation_id, artifact_type, source_uri, title,
                      content_hash, storage_reference, trust_class, access_class,
                      retention_policy, parser_version, untrusted_input,
                      prompt_injection_detected, published_at, effective_at,
                      retrieved_at, created_at
                    ) values (
                      $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,now()
                    )
                    on conflict (user_id, content_hash, access_class) do nothing
                    returning *
                    """,
                    str(uuid4()), uid, artifact.company_id, artifact.opportunity_id,
                    artifact.source_observation_id, artifact.artifact_type.value,
                    artifact.source_uri, artifact.title, artifact.content_hash,
                    artifact.storage_reference, artifact.trust_class.value,
                    artifact.access_class.value, artifact.retention_policy,
                    artifact.parser_version, artifact.untrusted_input,
                    artifact.prompt_injection_detected, artifact.published_at,
                    artifact.effective_at, artifact.retrieved_at,
                )
                if row is None:
                    row = await conn.fetchrow(
                        """
                        select * from public.evidence_artifacts
                        where user_id = $1 and content_hash = $2 and access_class = $3
                        """,
                        uid, artifact.content_hash, artifact.access_class.value,
                    )
                if row is None:
                    raise RuntimeError("Artifact insert returned no row")
                artifact_payload = db_row(row)
                stored_artifact = EvidenceArtifactRecord.model_validate(artifact_payload)
                stored_items: List[EvidenceItemRecord] = []
                for item in items:
                    item_row = await conn.fetchrow(
                        """
                        insert into public.evidence_items (
                          evidence_item_id, user_id, artifact_id, item_type,
                          normalized_value, display_excerpt, source_locator,
                          effective_at, expires_at, verification_state, source_quality,
                          extraction_confidence, extractor_version, operator_attribution,
                          created_at
                        ) values ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12,$13,$14,now())
                        returning *
                        """,
                        str(uuid4()), uid, stored_artifact.artifact_id, item.item_type,
                        json.dumps(item.normalized_value), item.display_excerpt,
                        item.source_locator, item.effective_at, item.expires_at,
                        item.verification_state.value, item.source_quality,
                        item.extraction_confidence, item.extractor_version,
                        item.operator_attribution,
                    )
                    payload = db_row(item_row)
                    payload["normalized_value"] = _json(payload.get("normalized_value"), {})
                    stored_items.append(EvidenceItemRecord.model_validate(payload))
                await self._outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="evidence_artifact",
                    aggregate_id=stored_artifact.artifact_id,
                    event_type="evidence_artifact.ingested",
                    payload={
                        "artifact_id": stored_artifact.artifact_id,
                        "opportunity_id": stored_artifact.opportunity_id,
                        "item_count": len(stored_items),
                        "prompt_injection_detected": stored_artifact.prompt_injection_detected,
                    },
                )
                return stored_artifact, stored_items

    async def create_claim(
        self,
        claim: ClaimInput,
        *,
        links: Sequence[ClaimEvidenceLinkInput],
        created_by: str,
    ) -> Dict[str, Any]:
        uid = require_user_id(claim.user_id, context="EvidenceRepository.create_claim")
        if any(link.user_id != uid for link in links):
            raise ValueError("Claim evidence link tenant mismatch")
        validate_claim_standard(claim, evidence_link_count=len(links))
        actor = str(created_by or "").strip()
        if not actor:
            raise ValueError("created_by is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    insert into public.claims (
                      claim_id, user_id, company_id, opportunity_id, claim_type,
                      normalized_value, unit, period, display_text, assertion_class,
                      status, confidence, material, operator_attribution,
                      supersedes_claim_id, created_by, created_at, updated_at
                    ) values ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,'current',$11,$12,$13,$14,$15,now(),now())
                    returning *
                    """,
                    str(uuid4()), uid, claim.company_id, claim.opportunity_id,
                    claim.claim_type, json.dumps(claim.normalized_value), claim.unit,
                    claim.period, claim.display_text, claim.assertion_class.value,
                    claim.confidence, claim.material, claim.operator_attribution,
                    claim.supersedes_claim_id, actor,
                )
                if row is None:
                    raise RuntimeError("Claim insert returned no row")
                claim_id = str(row["claim_id"])
                for link in links:
                    await conn.execute(
                        """
                        insert into public.claim_evidence_links (
                          link_id, user_id, claim_id, evidence_item_id,
                          relationship, support_strength, rationale, created_at
                        ) values ($1,$2,$3,$4,$5,$6,$7,now())
                        on conflict (user_id, claim_id, evidence_item_id, relationship)
                        do nothing
                        """,
                        str(uuid4()), uid, claim_id, link.evidence_item_id,
                        link.relationship.value, link.support_strength, link.rationale,
                    )
                if claim.supersedes_claim_id:
                    await conn.execute(
                        """
                        update public.claims set status = 'superseded', updated_at = now()
                        where claim_id = $1 and user_id = $2 and status = 'current'
                        """,
                        claim.supersedes_claim_id, uid,
                    )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="claim", aggregate_id=claim_id,
                    event_type="claim.created",
                    payload={"claim_id": claim_id, "opportunity_id": claim.opportunity_id},
                )
                payload = db_row(row)
                payload["normalized_value"] = _json(payload.get("normalized_value"), {})
                return payload

    async def correct_claim(
        self,
        *,
        user_id: str,
        claim_id: str,
        actor_id: str,
        action: str,
        rationale: str,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="EvidenceRepository.correct_claim")
        statuses = {
            "withdraw": ClaimStatus.WITHDRAWN,
            "contradict": ClaimStatus.CONTRADICTED,
            "mark_stale": ClaimStatus.STALE,
            "supersede": ClaimStatus.SUPERSEDED,
        }
        if action not in statuses or not str(rationale or "").strip():
            raise ValueError("Valid correction action and rationale are required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.claims set status = $3, updated_at = now()
                    where claim_id = $1 and user_id = $2 and status = 'current'
                    returning *
                    """,
                    claim_id, uid, statuses[action].value,
                )
                if row is None:
                    raise LookupError("Current claim not found for tenant")
                await conn.execute(
                    """
                    insert into public.claim_corrections (
                      correction_id, user_id, claim_id, actor_id, action, rationale, created_at
                    ) values ($1,$2,$3,$4,$5,$6,now())
                    """,
                    str(uuid4()), uid, claim_id, actor_id, action, str(rationale).strip(),
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="claim", aggregate_id=claim_id,
                    event_type="claim.corrected",
                    payload={"claim_id": claim_id, "action": action, "actor_id": actor_id},
                )
                payload = dict(row)
                payload["normalized_value"] = _json(payload.get("normalized_value"), {})
                return payload

    async def create_plan(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        trigger_type: str,
        missing_evidence: Sequence[str],
        search_questions: Sequence[str],
        max_artifacts: int = 5,
        budget_usd: float = 0.0,
    ) -> EvidencePlanRecord:
        uid = require_user_id(user_id, context="EvidenceRepository.create_plan")
        canonical = json.dumps(
            {
                "trigger_type": trigger_type,
                "missing_evidence": sorted(set(missing_evidence)),
                "search_questions": list(search_questions),
                "max_artifacts": max_artifacts,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        plan_hash = hashlib.sha256(canonical.encode()).hexdigest()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    insert into public.evidence_plans (
                      evidence_plan_id, user_id, opportunity_id, trigger_type, status,
                      missing_evidence, search_questions, max_artifacts, budget_usd,
                      plan_hash, created_at
                    ) values ($1,$2,$3,$4,'planned',$5::jsonb,$6::jsonb,$7,$8,$9,now())
                    on conflict (user_id, opportunity_id, plan_hash)
                    do update set plan_hash = excluded.plan_hash
                    returning *
                    """,
                    str(uuid4()), uid, opportunity_id, trigger_type,
                    json.dumps(sorted(set(missing_evidence))), json.dumps(list(search_questions)),
                    max(1, min(int(max_artifacts), 20)), max(0.0, float(budget_usd)), plan_hash,
                )
                payload = db_row(row)
                payload["missing_evidence"] = _json(payload.get("missing_evidence"), [])
                payload["search_questions"] = _json(payload.get("search_questions"), [])
                plan = EvidencePlanRecord.model_validate(payload)
                await self._outbox(
                    conn, user_id=uid, aggregate_type="evidence_plan",
                    aggregate_id=plan.evidence_plan_id,
                    event_type="evidence_plan.created",
                    payload={"evidence_plan_id": plan.evidence_plan_id, "opportunity_id": opportunity_id},
                )
                return plan

    async def get_ledger(self, *, user_id: str, opportunity_id: str) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="EvidenceRepository.get_ledger")
        async with self.pool.acquire() as conn:
            artifacts = await conn.fetch(
                "select * from public.evidence_artifacts where user_id = $1 and opportunity_id = $2 order by retrieved_at desc",
                uid, opportunity_id,
            )
            items = await conn.fetch(
                """
                select i.* from public.evidence_items i
                join public.evidence_artifacts a on a.user_id = i.user_id and a.artifact_id = i.artifact_id
                where i.user_id = $1 and a.opportunity_id = $2 order by i.created_at
                """,
                uid, opportunity_id,
            )
            claims = await conn.fetch(
                "select * from public.claims where user_id = $1 and opportunity_id = $2 order by created_at",
                uid, opportunity_id,
            )
            links = await conn.fetch(
                """
                select l.* from public.claim_evidence_links l
                join public.claims c on c.user_id = l.user_id and c.claim_id = l.claim_id
                where l.user_id = $1 and c.opportunity_id = $2 order by l.created_at
                """,
                uid, opportunity_id,
            )
            plans = await conn.fetch(
                "select * from public.evidence_plans where user_id = $1 and opportunity_id = $2 order by created_at desc",
                uid, opportunity_id,
            )
        def rows(values):
            output = []
            for value in values:
                item = dict(value)
                for key, default in (
                    ("normalized_value", {}), ("missing_evidence", []),
                    ("search_questions", []),
                ):
                    if key in item:
                        item[key] = _json(item[key], default)
                output.append(item)
            return output
        return {
            "artifacts": rows(artifacts), "evidence_items": rows(items),
            "claims": rows(claims), "claim_evidence_links": rows(links),
            "evidence_plans": rows(plans),
        }
