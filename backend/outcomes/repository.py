"""Repositories for idempotent channel imports and immutable outcome observations."""

from __future__ import annotations

import json
from typing import Any, Dict, Sequence
from uuid import uuid4

from identity.models import SourceChannel, SourceObservationInput
from identity.repository import IdentityRepository
from identity.service import IdentityService
from outcomes.models import ImportCandidate, ImportSource, OutcomeInput, OutcomeRecord
from outcomes.service import build_outcome_interpretation, validate_outcome
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


def _row(row: Any) -> Dict[str, Any]:
    payload = db_row(row)
    for key, default in (("field_mapping", {}),):
        if key in payload:
            payload[key] = _json(payload[key], default)
    return payload


_CHANNELS = {
    ImportSource.CSV: SourceChannel.IMPORT,
    ImportSource.CRM_CSV: SourceChannel.CRM_IMPORT,
    ImportSource.EVENT_CSV: SourceChannel.EVENT,
    ImportSource.REFERRAL_CSV: SourceChannel.REFERRAL,
}


class ImportPayloadConflict(RuntimeError):
    pass


class ChannelOutcomeRepository:
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
              event_id,user_id,aggregate_type,aggregate_id,event_type,event_version,
              payload,publication_attempts,next_attempt_at,created_at
            ) values ($1,$2,$3,$4,$5,1,$6::jsonb,0,now(),now())
            """,
            str(uuid4()), user_id, aggregate_type, aggregate_id, event_type, json.dumps(payload),
        )

    async def process_import(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        source: ImportSource | str,
        file_hash: str,
        field_mapping: Dict[str, Any],
        candidates: Sequence[ImportCandidate],
        actor_id: str,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="ChannelOutcomeRepository.process_import")
        source_type = ImportSource(source)
        batch_id = str(uuid4())
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                batch = await conn.fetchrow(
                    """
                    insert into public.import_batches (
                      import_batch_id,user_id,idempotency_key,source,file_hash,field_mapping,
                      status,row_count,created_by,created_at,updated_at
                    ) values ($1,$2,$3,$4,$5,$6::jsonb,'pending',$7,$8,now(),now())
                    on conflict (user_id,idempotency_key) do nothing returning *
                    """,
                    batch_id, uid, idempotency_key, source_type.value, file_hash,
                    json.dumps(field_mapping), len(candidates), actor_id,
                )
                if batch is None:
                    batch = await conn.fetchrow(
                        "select * from public.import_batches where user_id=$1 and idempotency_key=$2",
                        uid, idempotency_key,
                    )
                    if str(batch["file_hash"]) != file_hash or str(batch["source"]) != source_type.value:
                        raise ImportPayloadConflict("Idempotency key was already used for a different import")
                    if str(batch["status"]) in {"completed", "completed_with_errors"}:
                        rows = await conn.fetch(
                            "select * from public.import_rows where user_id=$1 and import_batch_id=$2 order by row_number",
                            uid, batch["import_batch_id"],
                        )
                        return {"batch": _row(batch), "rows": [_row(item) for item in rows], "idempotent_replay": True}
                    batch_id = str(batch["import_batch_id"])
                claimed = await conn.fetchrow(
                    """
                    update public.import_batches set status='processing',updated_at=now()
                    where user_id=$1 and import_batch_id=$2
                      and (status in ('pending','failed') or (status='processing' and updated_at < now() - interval '15 minutes'))
                    returning *
                    """,
                    uid, batch_id,
                )
                if claimed is None:
                    rows = await conn.fetch(
                        "select * from public.import_rows where user_id=$1 and import_batch_id=$2 order by row_number",
                        uid, batch_id,
                    )
                    return {"batch": _row(batch), "rows": [_row(item) for item in rows], "idempotent_replay": True}

        identity = IdentityService(IdentityRepository(self.pool))
        for candidate in candidates:
            try:
                admission = await identity.admit(
                    SourceObservationInput(
                        user_id=uid,
                        channel=_CHANNELS[source_type],
                        observed_name=candidate.observed_name,
                        observed_domain=candidate.observed_domain,
                        provider_identifiers=(
                            {"external": f"{source_type.value}:{candidate.external_id}"}
                            if candidate.external_id else {}
                        ),
                        external_event_key=f"import:{batch_id}:{candidate.row_key}",
                        source_metadata={
                            "source": source_type.value,
                            "import_batch_id": batch_id,
                            "row_number": candidate.row_number,
                            "operator_confirmed_identity": candidate.operator_confirmed_identity,
                            "raw_row_retained": False,
                        },
                    )
                )
                status = "resolved" if admission.company_id and admission.opportunity_id else "review_required"
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        insert into public.import_rows (
                          import_row_id,user_id,import_batch_id,row_number,row_key,
                          source_observation_id,company_id,opportunity_id,identity_case_id,status,created_at
                        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,now())
                        on conflict (user_id,import_batch_id,row_key) do nothing
                        """,
                        str(uuid4()), uid, batch_id, candidate.row_number, candidate.row_key,
                        admission.observation_id, admission.company_id, admission.opportunity_id,
                        admission.identity_case_id, status,
                    )
            except Exception as exc:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        insert into public.import_rows (
                          import_row_id,user_id,import_batch_id,row_number,row_key,status,error_code,created_at
                        ) values ($1,$2,$3,$4,$5,'error',$6,now())
                        on conflict (user_id,import_batch_id,row_key) do nothing
                        """,
                        str(uuid4()), uid, batch_id, candidate.row_number, candidate.row_key,
                        type(exc).__name__[:100],
                    )

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                counts = await conn.fetchrow(
                    """
                    select count(*) filter (where status='resolved') as resolved_count,
                           count(*) filter (where status='review_required') as review_count,
                           count(*) filter (where status='error') as error_count
                    from public.import_rows where user_id=$1 and import_batch_id=$2
                    """,
                    uid, batch_id,
                )
                final_status = "completed_with_errors" if int(counts["error_count"] or 0) else "completed"
                batch = await conn.fetchrow(
                    """
                    update public.import_batches set status=$3,resolved_count=$4,review_count=$5,
                      error_count=$6,completed_at=now(),updated_at=now()
                    where user_id=$1 and import_batch_id=$2 returning *
                    """,
                    uid, batch_id, final_status, int(counts["resolved_count"] or 0),
                    int(counts["review_count"] or 0), int(counts["error_count"] or 0),
                )
                rows = await conn.fetch(
                    "select * from public.import_rows where user_id=$1 and import_batch_id=$2 order by row_number",
                    uid, batch_id,
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="import_batch", aggregate_id=batch_id,
                    event_type="import_batch.completed",
                    payload={"import_batch_id": batch_id, "source": source_type.value, "row_count": len(candidates), "status": final_status},
                )
                return {"batch": _row(batch), "rows": [_row(item) for item in rows], "idempotent_replay": False}

    async def create_outcome(
        self, outcome: OutcomeInput, *, actor_id: str
    ) -> Dict[str, Any]:
        uid = require_user_id(outcome.user_id, context="ChannelOutcomeRepository.create_outcome")
        validate_outcome(outcome)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                company = await conn.fetchrow(
                    "select company_id from public.companies where user_id=$1 and company_id=$2",
                    uid, outcome.company_id,
                )
                if company is None:
                    raise LookupError("Company not found for tenant")
                if outcome.opportunity_id:
                    opportunity = await conn.fetchrow(
                        """
                        select opportunity_id from public.opportunities
                        where user_id=$1 and opportunity_id=$2 and company_id=$3
                        """,
                        uid, outcome.opportunity_id, outcome.company_id,
                    )
                    if opportunity is None:
                        raise LookupError("Opportunity does not belong to company")
                if outcome.supersedes_outcome_id:
                    prior = await conn.fetchrow(
                        """
                        select outcome_observation_id from public.outcome_observations
                        where user_id=$1 and outcome_observation_id=$2 and company_id=$3
                        """,
                        uid, outcome.supersedes_outcome_id, outcome.company_id,
                    )
                    if prior is None:
                        raise LookupError("Superseded outcome not found for company")
                if outcome.evidence_artifact_ids:
                    artifacts = await conn.fetch(
                        """
                        select artifact_id from public.evidence_artifacts
                        where user_id=$1 and artifact_id::text=any($2::text[])
                        """,
                        uid, outcome.evidence_artifact_ids,
                    )
                    if len(artifacts) != len(outcome.evidence_artifact_ids):
                        raise LookupError("One or more evidence artifacts were not found")
                outcome_id = str(uuid4())
                row = await conn.fetchrow(
                    """
                    insert into public.outcome_observations (
                      outcome_observation_id,user_id,company_id,opportunity_id,outcome_type,
                      valence,summary,verification_state,materiality,effective_at,observed_at,
                      recorded_by,supersedes_outcome_id,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,now()) returning *
                    """,
                    outcome_id, uid, outcome.company_id, outcome.opportunity_id,
                    outcome.outcome_type.value, outcome.valence.value, outcome.summary,
                    outcome.verification_state.value, outcome.materiality,
                    outcome.effective_at, outcome.observed_at, actor_id,
                    outcome.supersedes_outcome_id,
                )
                for artifact_id in outcome.evidence_artifact_ids:
                    await conn.execute(
                        """
                        insert into public.outcome_evidence_links (
                          outcome_evidence_link_id,user_id,outcome_observation_id,artifact_id,created_at
                        ) values ($1,$2,$3,$4,now())
                        """,
                        str(uuid4()), uid, outcome_id, artifact_id,
                    )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="outcome_observation", aggregate_id=outcome_id,
                    event_type="outcome_observation.created",
                    payload={"outcome_observation_id": outcome_id, "company_id": outcome.company_id, "verification_state": outcome.verification_state.value},
                )
                payload = db_row(row)
                payload["evidence_artifact_ids"] = list(outcome.evidence_artifact_ids)
                for key in ("outcome_observation_id", "company_id", "opportunity_id", "supersedes_outcome_id"):
                    if payload.get(key) is not None:
                        payload[key] = str(payload[key])
                record = OutcomeRecord.model_validate(payload)
                return {
                    "outcome": record.model_dump(mode="json"),
                    "interpretation": build_outcome_interpretation(outcome),
                }

    async def list_outcomes(
        self, *, user_id: str, company_id: str, limit: int = 100
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="ChannelOutcomeRepository.list_outcomes")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select o.*,coalesce(jsonb_agg(l.artifact_id) filter (where l.artifact_id is not null),'[]'::jsonb) as evidence_artifact_ids
                from public.outcome_observations o
                left join public.outcome_evidence_links l
                  on l.user_id=o.user_id and l.outcome_observation_id=o.outcome_observation_id
                where o.user_id=$1 and o.company_id=$2
                group by o.outcome_observation_id order by o.observed_at desc limit $3
                """,
                uid, company_id, max(1, min(int(limit), 200)),
            )
        outcomes = []
        for row in rows:
            payload = db_row(row)
            payload["evidence_artifact_ids"] = [str(item) for item in _json(payload["evidence_artifact_ids"], [])]
            for key in ("outcome_observation_id", "company_id", "opportunity_id", "supersedes_outcome_id"):
                if payload.get(key) is not None:
                    payload[key] = str(payload[key])
            record = OutcomeRecord.model_validate(payload)
            outcomes.append({
                "outcome": record.model_dump(mode="json"),
                "interpretation": build_outcome_interpretation(record),
            })
        return {"outcomes": outcomes}

    async def get_outcome_coverage(self, *, user_id: str) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="ChannelOutcomeRepository.get_outcome_coverage")
        async with self.pool.acquire() as conn:
            eligible = await conn.fetchval(
                """
                select count(*) from public.opportunities
                where user_id=$1 and decision_state in ('advance','monitor','pass','invested','archived')
                """,
                uid,
            )
            observed = await conn.fetchval(
                """
                select count(distinct opportunity_id) from public.outcome_observations
                where user_id=$1 and opportunity_id is not null
                """,
                uid,
            )
            valence = await conn.fetch(
                "select valence,count(*) as count from public.outcome_observations where user_id=$1 group by valence",
                uid,
            )
        denominator = int(eligible or 0)
        numerator = int(observed or 0)
        return {
            "eligible_opportunity_count": denominator,
            "observed_opportunity_count": numerator,
            "coverage_ratio": round(numerator / denominator, 4) if denominator else 0,
            "outcomes_by_valence": {str(row["valence"]): int(row["count"]) for row in valence},
            "causal_inference_supported": False,
            "limitations": [
                "Coverage includes only recorded observations and may be incomplete.",
                "Positive and negative observation balance must be reviewed before learning use.",
            ],
        }

    async def get_import(self, *, user_id: str, import_batch_id: str) -> Dict[str, Any] | None:
        uid = require_user_id(user_id, context="ChannelOutcomeRepository.get_import")
        async with self.pool.acquire() as conn:
            batch = await conn.fetchrow(
                "select * from public.import_batches where user_id=$1 and import_batch_id=$2",
                uid, import_batch_id,
            )
            if batch is None:
                return None
            rows = await conn.fetch(
                "select * from public.import_rows where user_id=$1 and import_batch_id=$2 order by row_number",
                uid, import_batch_id,
            )
        return {"batch": _row(batch), "rows": [_row(item) for item in rows]}
