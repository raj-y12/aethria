"""Transactional repository for tenant-scoped canonical company identity."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from identity.models import (
    CompanyRecord,
    IdentityAdmission,
    IdentityCandidate,
    IdentityCaseGroup,
    IdentityResolutionCaseRecord,
    IdentityStatus,
    NormalizedIdentifier,
    OpportunityRecord,
    SourceObservationInput,
    SourceObservationRecord,
    VerificationStatus,
)
from identity.normalization import normalize_alias, normalize_domain
from tenant_context import require_user_id
from utils.db_rows import db_row


class IdentityConflictError(RuntimeError):
    """A verified identifier is already owned by another canonical company."""


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _observation_from_row(row: Any) -> Optional[SourceObservationRecord]:
    if row is None:
        return None
    payload = db_row(row)
    payload["source_metadata"] = _json_value(payload.get("source_metadata"), {})
    payload["resolution_payload"] = _json_value(
        payload.get("resolution_payload"), None
    )
    # Provider identifiers are deliberately not exposed on the read model yet.
    payload.pop("provider_identifiers", None)
    return SourceObservationRecord.model_validate(payload)


def _company_from_row(row: Any) -> Optional[CompanyRecord]:
    if row is None:
        return None
    payload = db_row(row)
    payload["metadata"] = _json_value(payload.get("metadata"), {})
    payload.pop("merged_into_company_id", None)
    return CompanyRecord.model_validate(payload)


def _opportunity_from_row(row: Any) -> Optional[OpportunityRecord]:
    return OpportunityRecord.model_validate(db_row(row)) if row is not None else None


def _case_from_row(row: Any) -> Optional[IdentityResolutionCaseRecord]:
    if row is None:
        return None
    payload = db_row(row)
    payload["candidates"] = _json_value(payload.get("candidates"), [])
    return IdentityResolutionCaseRecord.model_validate(payload)


def _inserted(command_status: Any) -> bool:
    """Return whether asyncpg's ``INSERT 0 n`` status inserted a row.

    Test doubles and compatible drivers may not expose asyncpg's status string; in
    that case we preserve the happy path and let database constraints fail closed.
    """

    status = str(command_status or "").strip().split()
    return not status or not status[-1].isdigit() or int(status[-1]) > 0


class IdentityRepository:
    def __init__(self, pool: Any, *, authority_service: Any = None):
        self.pool = pool
        self.authority_service = authority_service

    async def _require_write_path(self, *, user_id: str, operation: str) -> None:
        if self.authority_service is not None:
            await self.authority_service.require_write_path(
                user_id=user_id, operation=operation
            )

    @staticmethod
    async def _insert_outbox(
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
            on conflict (event_id) do nothing
            """,
            str(uuid4()),
            user_id,
            aggregate_type,
            aggregate_id,
            event_type,
            json.dumps(payload),
        )

    async def record_observation(
        self, observation: SourceObservationInput
    ) -> SourceObservationRecord:
        uid = require_user_id(
            observation.user_id, context="IdentityRepository.record_observation"
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into public.source_observations (
                  observation_id, user_id, channel, external_event_key, lookup_id,
                  legacy_startup_id, observed_name, observed_domain,
                  provider_identifiers, source_metadata, resolution_payload,
                  identity_status, identity_confidence, observed_at, created_at, updated_at
                ) values (
                  $1, $2, $3, $4, $5, $6::uuid, $7, $8,
                  $9::jsonb, $10::jsonb, $11::jsonb, 'pending', 0, $12, now(), now()
                )
                on conflict (user_id, channel, external_event_key)
                  where external_event_key is not null
                do nothing
                returning *
                """,
                str(uuid4()),
                uid,
                observation.channel.value,
                observation.external_event_key,
                observation.lookup_id,
                observation.legacy_startup_id,
                observation.observed_name,
                normalize_domain(observation.observed_domain),
                json.dumps(observation.provider_identifiers),
                json.dumps(observation.source_metadata),
                (
                    json.dumps(observation.resolution_payload)
                    if observation.resolution_payload is not None
                    else None
                ),
                observation.observed_at,
            )
            if row is None and observation.external_event_key:
                row = await conn.fetchrow(
                    """
                    select * from public.source_observations
                    where user_id = $1 and channel = $2 and external_event_key = $3
                    """,
                    uid,
                    observation.channel.value,
                    observation.external_event_key,
                )
            if row is None:
                raise RuntimeError("Observation insert returned no row")
            return _observation_from_row(row)

    async def get_admission_for_observation(
        self, *, user_id: str, observation_id: str
    ) -> Optional[IdentityAdmission]:
        uid = require_user_id(
            user_id, context="IdentityRepository.get_admission_for_observation"
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select o.*, p.opportunity_id as linked_opportunity_id, c.identity_case_id,
                       c.candidates as identity_case_candidates
                from public.source_observations o
                left join public.opportunities p
                  on p.user_id = o.user_id
                 and p.opportunity_id = o.opportunity_id
                left join public.identity_resolution_cases c
                  on c.user_id = o.user_id and c.observation_id = o.observation_id
                where o.observation_id = $1 and o.user_id = $2
                order by c.created_at desc
                limit 1
                """,
                observation_id,
                uid,
            )
        if row is None:
            return None
        status = IdentityStatus(str(row["identity_status"]))
        if status is IdentityStatus.PENDING:
            return None
        candidates = _json_value(row.get("identity_case_candidates"), [])
        return IdentityAdmission(
            user_id=uid,
            observation_id=str(row["observation_id"]),
            status=status,
            company_id=str(row["company_id"]) if row.get("company_id") else None,
            opportunity_id=(
                str(row["linked_opportunity_id"])
                if row.get("linked_opportunity_id")
                else None
            ),
            identity_case_id=(
                str(row["identity_case_id"]) if row.get("identity_case_id") else None
            ),
            confidence=float(row.get("identity_confidence") or 0),
            blocks_evaluation=(
                status in {
                    IdentityStatus.AMBIGUOUS,
                    IdentityStatus.DEFERRED,
                    IdentityStatus.REJECTED,
                }
                or (
                    status is IdentityStatus.RESOLVED
                    and not row.get("linked_opportunity_id")
                )
            ),
            candidates=candidates,
            created=False,
        )

    async def find_companies_by_verified_identifiers(
        self, *, user_id: str, identifiers: Sequence[NormalizedIdentifier]
    ) -> List[Dict[str, Any]]:
        uid = require_user_id(
            user_id,
            context="IdentityRepository.find_companies_by_verified_identifiers",
        )
        pairs = [
            {
                "identifier_type": item.identifier_type.value,
                "normalized_value": item.normalized_value,
            }
            for item in identifiers
            if item.verification_status is VerificationStatus.VERIFIED
        ]
        if not pairs:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                with requested as (
                  select identifier_type, normalized_value
                  from jsonb_to_recordset($2::jsonb)
                    as x(identifier_type text, normalized_value text)
                )
                select c.company_id, c.canonical_name, c.canonical_domain,
                       max(ci.confidence) as confidence
                from public.company_identifiers ci
                join requested r
                  on r.identifier_type = ci.identifier_type
                 and r.normalized_value = ci.normalized_value
                join public.companies c
                  on c.user_id = ci.user_id and c.company_id = ci.company_id
                where ci.user_id = $1
                  and ci.verification_status = 'verified'
                  and c.status = 'active'
                group by c.company_id, c.canonical_name, c.canonical_domain
                order by max(ci.confidence) desc, c.company_id
                """,
                uid,
                json.dumps(pairs),
            )
        return [
            {
                "company_id": str(row["company_id"]),
                "canonical_name": str(row["canonical_name"]),
                "canonical_domain": row.get("canonical_domain"),
                "confidence": float(row.get("confidence") or 0),
            }
            for row in rows
        ]

    async def _store_identifiers(
        self,
        conn: Any,
        *,
        user_id: str,
        company_id: str,
        observation_id: str,
        identifiers: Iterable[NormalizedIdentifier],
    ) -> None:
        for identifier in identifiers:
            result = await conn.execute(
                """
                insert into public.company_identifiers (
                  identifier_id, user_id, company_id, identifier_type,
                  normalized_value, raw_value, verification_status, confidence,
                  is_primary, source_observation_id, created_at, updated_at
                ) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now(), now())
                on conflict do nothing
                """,
                str(uuid4()),
                user_id,
                company_id,
                identifier.identifier_type.value,
                identifier.normalized_value,
                identifier.raw_value,
                identifier.verification_status.value,
                identifier.confidence,
                identifier.is_primary,
                observation_id,
            )
            if (
                identifier.verification_status is VerificationStatus.VERIFIED
                and not _inserted(result)
            ):
                owner = await conn.fetchrow(
                    """
                    select company_id from public.company_identifiers
                    where user_id = $1 and identifier_type = $2
                      and normalized_value = $3
                      and verification_status = 'verified'
                    """,
                    user_id,
                    identifier.identifier_type.value,
                    identifier.normalized_value,
                )
                if owner is not None and str(owner["company_id"]) != company_id:
                    raise IdentityConflictError(
                        "Verified identifier belongs to another company"
                    )

    @staticmethod
    async def _store_alias(
        conn: Any,
        *,
        user_id: str,
        company_id: str,
        observation_id: str,
        alias: str,
    ) -> None:
        normalized = normalize_alias(alias)
        if not normalized:
            return
        await conn.execute(
            """
            insert into public.company_aliases (
              alias_id, user_id, company_id, alias, normalized_alias,
              alias_type, source_observation_id, created_at
            ) values ($1, $2, $3, $4, $5, 'observed', $6, now())
            on conflict (user_id, company_id, normalized_alias, alias_type) do nothing
            """,
            str(uuid4()),
            user_id,
            company_id,
            alias,
            normalized,
            observation_id,
        )

    @staticmethod
    async def _upsert_opportunity(
        conn: Any,
        *,
        user_id: str,
        company_id: str,
        context_key: str,
        observation_id: str,
        legacy_startup_id: Optional[str],
    ) -> OpportunityRecord:
        row = await conn.fetchrow(
            """
            insert into public.opportunities (
              opportunity_id, user_id, company_id, context_key, decision_state,
              workflow_state, workflow_version, block_code, block_detail, block_recovery,
              service_level, first_observation_id, latest_observation_id,
              legacy_startup_id, created_at, updated_at
            ) values ($1, $2, $3, $4, 'discovered', 'admitted', 0, null, null, null,
                      1, $5, $5, $6::uuid, now(), now())
            on conflict (user_id, company_id, context_key)
            do update set latest_observation_id = excluded.latest_observation_id,
                          legacy_startup_id = coalesce(
                            opportunities.legacy_startup_id,
                            excluded.legacy_startup_id
                          ),
                          updated_at = now()
            returning *
            """,
            str(uuid4()),
            user_id,
            company_id,
            context_key,
            observation_id,
            legacy_startup_id,
        )
        opportunity = _opportunity_from_row(row)
        if opportunity is None:
            raise RuntimeError("Opportunity upsert returned no row")
        await conn.execute(
            """
            update public.source_observations
            set opportunity_id = $3, updated_at = now()
            where observation_id = $1 and user_id = $2
            """,
            observation_id,
            user_id,
            opportunity.opportunity_id,
        )
        return opportunity

    async def create_company_admission(
        self,
        *,
        observation: SourceObservationInput,
        observation_id: str,
        identifiers: Sequence[NormalizedIdentifier],
        confidence: float,
        canonical_name: Optional[str] = None,
        canonical_domain: Optional[str] = None,
    ) -> IdentityAdmission:
        uid = require_user_id(
            observation.user_id,
            context="IdentityRepository.create_company_admission",
        )
        await self._require_write_path(user_id=uid, operation="identity linkage")
        primary_domain = next(
            (
                item.normalized_value
                for item in identifiers
                if item.identifier_type.value == "domain" and item.is_primary
            ),
            None,
        )
        domain = normalize_domain(canonical_domain or primary_domain)
        name = str(canonical_name or observation.observed_name).strip()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="identity linkage")
                row = await conn.fetchrow(
                    """
                    insert into public.companies (
                      company_id, user_id, canonical_name, canonical_domain,
                      identity_confidence, status, metadata, created_at, updated_at
                    ) values ($1, $2, $3, $4, $5, 'active', '{}'::jsonb, now(), now())
                    on conflict do nothing
                    returning *
                    """,
                    str(uuid4()),
                    uid,
                    name,
                    domain,
                    confidence,
                )
                created = row is not None
                if row is None and domain:
                    row = await conn.fetchrow(
                        """
                        select * from public.companies
                        where user_id = $1 and canonical_domain = $2 and status = 'active'
                        """,
                        uid,
                        domain,
                    )
                company = _company_from_row(row)
                if company is None:
                    raise RuntimeError("Canonical company insert returned no row")
                await self._store_identifiers(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    observation_id=observation_id,
                    identifiers=identifiers,
                )
                await self._store_alias(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    observation_id=observation_id,
                    alias=observation.observed_name,
                )
                await conn.execute(
                    """
                    update public.source_observations
                    set company_id = $3, identity_status = 'resolved',
                        identity_confidence = $4, updated_at = now()
                    where observation_id = $1 and user_id = $2
                    """,
                    observation_id,
                    uid,
                    company.company_id,
                    confidence,
                )
                opportunity = await self._upsert_opportunity(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    context_key=observation.opportunity_context_key,
                    observation_id=observation_id,
                    legacy_startup_id=observation.legacy_startup_id,
                )
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="source_observation",
                    aggregate_id=observation_id,
                    event_type="observation_resolved",
                    payload={
                        "observation_id": observation_id,
                        "company_id": company.company_id,
                        "opportunity_id": opportunity.opportunity_id,
                        "legacy_startup_id": (
                            str(opportunity.legacy_startup_id)
                            if opportunity.legacy_startup_id
                            else None
                        ),
                        "compatibility_reason": "canonical identity resolved",
                        "created": created,
                    },
                )
                if self.authority_service is not None and created and hasattr(getattr(self.authority_service, "repository", None), "transition_workflow_on_connection"):
                    await self.authority_service.repository.transition_workflow_on_connection(
                        conn,
                        user_id=uid, opportunity_id=opportunity.opportunity_id,
                        expected_version=0, target_state="admitted",
                        transition_id=uuid4(),
                    )
                return IdentityAdmission(
                    user_id=uid,
                    observation_id=observation_id,
                    status=IdentityStatus.RESOLVED,
                    company_id=company.company_id,
                    opportunity_id=opportunity.opportunity_id,
                    confidence=confidence,
                    created=created,
                )

    async def resolve_existing_admission(
        self,
        *,
        user_id: str,
        observation_id: str,
        company_id: str,
        context_key: str,
        matched_identifier: Optional[NormalizedIdentifier],
        identifiers: Sequence[NormalizedIdentifier],
        confidence: float,
    ) -> IdentityAdmission:
        uid = require_user_id(
            user_id, context="IdentityRepository.resolve_existing_admission"
        )
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                company_row = await conn.fetchrow(
                    """
                    select * from public.companies
                    where company_id = $1 and user_id = $2 and status = 'active'
                    for update
                    """,
                    company_id,
                    uid,
                )
                company = _company_from_row(company_row)
                if company is None:
                    raise LookupError("Canonical company not found for tenant")
                observation_row = await conn.fetchrow(
                    """
                    update public.source_observations
                    set company_id = $3, identity_status = 'resolved',
                        identity_confidence = $4, updated_at = now()
                    where observation_id = $1 and user_id = $2
                      and identity_status in ('pending', 'resolved')
                    returning observed_name, legacy_startup_id
                    """,
                    observation_id,
                    uid,
                    company_id,
                    confidence,
                )
                if observation_row is None:
                    raise LookupError("Pending observation not found for tenant")
                await self._store_identifiers(
                    conn,
                    user_id=uid,
                    company_id=company_id,
                    observation_id=observation_id,
                    identifiers=identifiers,
                )
                await self._store_alias(
                    conn,
                    user_id=uid,
                    company_id=company_id,
                    observation_id=observation_id,
                    alias=str(observation_row["observed_name"]),
                )
                opportunity = await self._upsert_opportunity(
                    conn,
                    user_id=uid,
                    company_id=company_id,
                    context_key=context_key,
                    observation_id=observation_id,
                    legacy_startup_id=(
                        str(observation_row["legacy_startup_id"])
                        if observation_row.get("legacy_startup_id")
                        else None
                    ),
                )
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="source_observation",
                    aggregate_id=observation_id,
                    event_type="observation_resolved",
                    payload={
                        "observation_id": observation_id,
                        "company_id": company_id,
                        "opportunity_id": opportunity.opportunity_id,
                        "legacy_startup_id": (
                            str(opportunity.legacy_startup_id)
                            if opportunity.legacy_startup_id
                            else None
                        ),
                        "compatibility_reason": "canonical identity resolved",
                        "created": False,
                    },
                )
                return IdentityAdmission(
                    user_id=uid,
                    observation_id=observation_id,
                    status=IdentityStatus.RESOLVED,
                    company_id=company_id,
                    opportunity_id=opportunity.opportunity_id,
                    confidence=confidence,
                    matched_identifier=matched_identifier,
                    created=False,
                )

    async def open_identity_case(
        self,
        *,
        observation: SourceObservationInput,
        observation_id: str,
        candidates: Sequence[IdentityCandidate],
        reason_code: str,
        confidence: float,
    ) -> IdentityAdmission:
        uid = require_user_id(
            observation.user_id, context="IdentityRepository.open_identity_case"
        )
        serialized = json.dumps(
            [candidate.model_dump(mode="json") for candidate in candidates]
        )
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    update public.source_observations
                    set identity_status = 'ambiguous', identity_confidence = $3,
                        company_id = null, updated_at = now()
                    where observation_id = $1 and user_id = $2
                      and identity_status in ('pending', 'ambiguous')
                    """,
                    observation_id,
                    uid,
                    confidence,
                )
                row = await conn.fetchrow(
                    """
                    insert into public.identity_resolution_cases (
                      identity_case_id, user_id, observation_id, status,
                      reason_code, candidates, created_at, updated_at
                    ) values ($1, $2, $3, 'open', $4, $5::jsonb, now(), now())
                    on conflict (user_id, observation_id) where status = 'open'
                    do update set reason_code = excluded.reason_code,
                                  candidates = excluded.candidates,
                                  updated_at = now()
                    returning *
                    """,
                    str(uuid4()),
                    uid,
                    observation_id,
                    reason_code,
                    serialized,
                )
                case = _case_from_row(row)
                if case is None:
                    raise RuntimeError("Identity resolution case upsert returned no row")
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="identity_resolution_case",
                    aggregate_id=case.identity_case_id,
                    event_type="identity_case.opened",
                    payload={
                        "identity_case_id": case.identity_case_id,
                        "observation_id": observation_id,
                        "reason_code": reason_code,
                    },
                )
                return IdentityAdmission(
                    user_id=uid,
                    observation_id=observation_id,
                    status=IdentityStatus.AMBIGUOUS,
                    identity_case_id=case.identity_case_id,
                    confidence=confidence,
                    blocks_evaluation=True,
                    candidates=list(candidates),
                    created=True,
                )

    async def resolve_case(
        self,
        *,
        user_id: str,
        identity_case_id: str,
        selected_company_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
        context_key: str = "primary",
        identifiers: Sequence[NormalizedIdentifier] = (),
        confidence: float = 1.0,
    ) -> IdentityAdmission:
        """Resolve an open ambiguity case onto an existing canonical company.

        Case, observation, opportunity, identifiers, alias, and outbox mutation are
        committed together. A company must already exist: creating a new canonical
        entity is a separate, explicit operator action and cannot be implied by a
        fuzzy candidate selection.
        """

        uid = require_user_id(user_id, context="IdentityRepository.resolve_case")
        await self._require_write_path(user_id=uid, operation="identity linkage")
        actor = str(resolved_by or "").strip()
        if not actor:
            raise ValueError("resolved_by is required")
        confidence = max(0.0, min(1.0, float(confidence)))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                case_row = await conn.fetchrow(
                    """
                    with locked as (
                      select identity_case_id
                      from public.identity_resolution_cases
                      where identity_case_id = $1 and user_id = $2 and status = 'open'
                      for update
                    )
                    update public.identity_resolution_cases c
                    set status = 'resolved', selected_company_id = $3,
                        resolution_note = $4, resolved_by = $5,
                        resolved_at = now(), updated_at = now()
                    from locked
                    where c.identity_case_id = locked.identity_case_id
                      and c.user_id = $2
                    returning c.*
                    """,
                    identity_case_id,
                    uid,
                    selected_company_id,
                    (str(resolution_note or "").strip() or None),
                    actor,
                )
                case = _case_from_row(case_row)
                if case is None:
                    raise LookupError("Open identity case not found for tenant")
                observation_row = await conn.fetchrow(
                    """
                    update public.source_observations
                    set company_id = $3, identity_status = 'resolved',
                        identity_confidence = $4, updated_at = now()
                    where observation_id = $1 and user_id = $2
                      and identity_status = 'ambiguous'
                    returning *
                    """,
                    case.observation_id,
                    uid,
                    selected_company_id,
                    confidence,
                )
                observation = _observation_from_row(observation_row)
                if observation is None:
                    raise LookupError("Ambiguous observation not found for tenant")
                company_row = await conn.fetchrow(
                    """
                    select * from public.companies
                    where company_id = $1 and user_id = $2 and status = 'active'
                    for update
                    """,
                    selected_company_id,
                    uid,
                )
                company = _company_from_row(company_row)
                if company is None:
                    raise LookupError("Selected company not found for tenant")
                await self._store_identifiers(
                    conn,
                    user_id=uid,
                    company_id=selected_company_id,
                    observation_id=case.observation_id,
                    identifiers=identifiers,
                )
                await self._store_alias(
                    conn,
                    user_id=uid,
                    company_id=selected_company_id,
                    observation_id=case.observation_id,
                    alias=observation.observed_name,
                )
                opportunity = await self._upsert_opportunity(
                    conn,
                    user_id=uid,
                    company_id=selected_company_id,
                    context_key=context_key,
                    observation_id=case.observation_id,
                    legacy_startup_id=observation.legacy_startup_id,
                )
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="identity_resolution_case",
                    aggregate_id=identity_case_id,
                    event_type="identity_case.resolved",
                    payload={
                        "identity_case_id": identity_case_id,
                        "observation_id": case.observation_id,
                        "company_id": selected_company_id,
                        "opportunity_id": opportunity.opportunity_id,
                        "legacy_startup_id": (
                            str(opportunity.legacy_startup_id)
                            if opportunity.legacy_startup_id
                            else None
                        ),
                        "compatibility_reason": "canonical identity resolved",
                        "resolved_by": actor,
                    },
                )
                return IdentityAdmission(
                    user_id=uid,
                    observation_id=case.observation_id,
                    status=IdentityStatus.RESOLVED,
                    company_id=selected_company_id,
                    opportunity_id=opportunity.opportunity_id,
                    identity_case_id=identity_case_id,
                    confidence=confidence,
                    created=False,
                )

    async def link_legacy_projection(
        self, *, user_id: str, opportunity_id: str, legacy_startup_id: str
    ) -> OpportunityRecord:
        uid = require_user_id(
            user_id, context="IdentityRepository.link_legacy_projection"
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.opportunities
                set legacy_startup_id = $3::uuid, updated_at = now()
                where opportunity_id = $1 and user_id = $2
                  and (legacy_startup_id is null or legacy_startup_id = $3::uuid)
                returning *
                """,
                opportunity_id,
                uid,
                legacy_startup_id,
            )
        opportunity = _opportunity_from_row(row)
        if opportunity is None:
            raise IdentityConflictError(
                "Opportunity projection is missing, cross-tenant, or already linked"
            )
        return opportunity

    async def get_company(
        self, *, user_id: str, company_id: str
    ) -> Optional[CompanyRecord]:
        uid = require_user_id(user_id, context="IdentityRepository.get_company")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.companies
                where company_id = $1 and user_id = $2
                """,
                company_id,
                uid,
            )
        return _company_from_row(row)

    async def get_opportunity(
        self, *, user_id: str, opportunity_id: str
    ) -> Optional[OpportunityRecord]:
        uid = require_user_id(user_id, context="IdentityRepository.get_opportunity")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.opportunities
                where opportunity_id = $1 and user_id = $2
                """,
                opportunity_id,
                uid,
            )
        return _opportunity_from_row(row)

    async def get_opportunity_by_legacy_projection(
        self, *, user_id: str, legacy_startup_id: str
    ) -> Optional[OpportunityRecord]:
        uid = require_user_id(
            user_id,
            context="IdentityRepository.get_opportunity_by_legacy_projection",
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.opportunities
                where legacy_startup_id = $1::uuid and user_id = $2
                order by updated_at desc
                limit 1
                """,
                legacy_startup_id,
                uid,
            )
        return _opportunity_from_row(row)

    async def list_opportunities(self, *, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Canonical queue projection; never falls back to ``startups``."""
        uid = require_user_id(user_id, context="IdentityRepository.list_opportunities")
        bounded = max(1, min(int(limit), 200))
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select o.*, c.canonical_name, c.canonical_domain,
                       r.recommended_state, r.confidence as recommendation_confidence,
                       hr.decision as current_ruling_decision,
                       hr.rationale as current_ruling_rationale,
                       hr.created_at as current_ruling_created_at
                from public.opportunities o
                join public.companies c on c.user_id=o.user_id and c.company_id=o.company_id
                left join public.recommendations r
                  on r.user_id=o.user_id and r.recommendation_id=o.current_recommendation_id
                left join public.human_rulings hr
                  on hr.user_id=o.user_id and hr.ruling_id=o.current_ruling_id
                where o.user_id=$1 and o.workflow_state <> 'archived'
                order by o.updated_at desc limit $2
                """, uid, bounded,
            )
        return [dict(row) for row in rows]

    async def get_decision_view(self, *, user_id: str, opportunity_id: str) -> Optional[Dict[str, Any]]:
        """Single canonical read model for queue, memo, and ruling handoff."""
        uid = require_user_id(user_id, context="IdentityRepository.get_decision_view")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select o.*, c.canonical_name, c.canonical_domain,
                       r.recommendation_id, r.recommended_state, r.attention_priority,
                       r.confidence as recommendation_confidence, r.decision_drivers,
                       r.principal_risks, r.missing_information, r.change_conditions,
                       e.evaluation_id, e.evidence_snapshot_hash, e.policy_version_id,
                       e.thesis_version_id,
                       hr.decision as current_ruling_decision,
                       hr.rationale as current_ruling_rationale,
                       hr.created_at as current_ruling_created_at,
                       (
                         select coalesce(json_agg(json_build_object(
                           'ruling_id', hri.ruling_id::text,
                           'recommendation_id', hri.recommendation_id::text,
                           'decision', hri.decision,
                           'rationale', hri.rationale,
                           'risk_acknowledgement', hri.risk_acknowledgement,
                           'mandate_exception', hri.mandate_exception,
                           'investor_confidence', hri.investor_confidence,
                           'actor_id', hri.actor_id,
                           'prior_ruling_id', hri.prior_ruling_id::text,
                           'created_at', hri.created_at
                         ) order by hri.created_at, hri.ruling_id), '[]'::json)
                         from public.human_rulings hri
                         where hri.user_id=o.user_id and hri.opportunity_id=o.opportunity_id
                       ) as ruling_history
                from public.opportunities o
                join public.companies c on c.user_id=o.user_id and c.company_id=o.company_id
                left join public.recommendations r
                  on r.user_id=o.user_id and r.recommendation_id=o.current_recommendation_id
                left join public.evaluation_runs e
                  on e.user_id=o.user_id and e.evaluation_id=o.current_evaluation_id
                left join public.human_rulings hr
                  on hr.user_id=o.user_id and hr.ruling_id=o.current_ruling_id
                where o.user_id=$1 and o.opportunity_id=$2
                """, uid, opportunity_id,
            )
        if row is None:
            return None
        payload = dict(row)
        for key in ("decision_drivers", "principal_risks", "missing_information", "change_conditions"):
            payload[key] = _json_value(payload.get(key), [])
        payload["ruling_history"] = _json_value(payload.get("ruling_history"), [])
        return payload

    async def get_decision_cases(
        self, *, user_id: str, opportunity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return one historically coherent case per completed evaluation episode."""
        uid = require_user_id(user_id, context="IdentityRepository.get_decision_cases")
        async with self.pool.acquire() as conn:
            opportunity_row = await conn.fetchrow(
                """
                select o.opportunity_id, o.company_id, o.context_key,
                       o.decision_state, o.service_level, o.current_evaluation_id,
                       o.current_recommendation_id, o.current_ruling_id,
                       o.updated_at, c.canonical_name, c.canonical_domain
                from public.opportunities o
                join public.companies c
                  on c.user_id=o.user_id and c.company_id=o.company_id
                where o.user_id=$1 and o.opportunity_id=$2
                """,
                uid,
                opportunity_id,
            )
            if opportunity_row is None:
                return None
            evaluations = await conn.fetch(
                """
                select evaluation_id, evidence_snapshot_hash, evidence_materiality_digest,
                       claim_snapshot, thesis_version_id, policy_version_id, policy_hash,
                       rubric_version, partner_rules_version, partner_rules_hash,
                       model_manifest, prompt_manifest, status, created_at, completed_at
                from public.evaluation_runs
                where user_id=$1 and opportunity_id=$2 and status='completed'
                order by coalesce(completed_at, created_at), created_at, evaluation_id
                """,
                uid,
                opportunity_id,
            )
            recommendations = await conn.fetch(
                """
                select recommendation_id, evaluation_id, recommended_state,
                       attention_priority, confidence as recommendation_confidence,
                       decision_drivers, principal_risks, mandate_conflicts,
                       missing_information, change_conditions, human_review_required,
                       change_explanation, created_at
                from public.recommendations
                where user_id=$1 and opportunity_id=$2
                order by created_at, recommendation_id
                """,
                uid,
                opportunity_id,
            )
            criteria = await conn.fetch(
                """
                select ca.evaluation_id, ca.criterion, ca.score, ca.confidence,
                       ca.evidence_sufficiency, ca.reasoning, ca.supporting_claim_ids,
                       ca.contradicting_claim_ids, ca.missing_evidence, ca.quality_flags,
                       ca.deterministic_adjustments
                from public.criterion_assessments ca
                join public.evaluation_runs e
                  on e.user_id=ca.user_id and e.evaluation_id=ca.evaluation_id
                where ca.user_id=$1 and e.opportunity_id=$2 and e.status='completed'
                order by ca.evaluation_id, ca.criterion
                """,
                uid,
                opportunity_id,
            )
            rulings = await conn.fetch(
                """
                select hr.ruling_id, hr.recommendation_id, hr.decision, hr.rationale,
                       hr.risk_acknowledgement, hr.mandate_exception,
                       hr.investor_confidence, hr.actor_id, hr.prior_ruling_id,
                       hr.created_at, os.override_signal_id, os.override_type,
                       os.note as override_note, os.recommendation_state,
                       os.ruling_decision
                from public.human_rulings hr
                left join public.override_signals os
                  on os.user_id=hr.user_id and os.ruling_id=hr.ruling_id
                where hr.user_id=$1 and hr.opportunity_id=$2
                order by hr.created_at, hr.ruling_id
                """,
                uid,
                opportunity_id,
            )
            interpretations = await conn.fetch(
                """
                select interpretation_id, ruling_id, opportunity_id, recommendation_id,
                       evaluation_id, version, source, status, rationale_sha256,
                       extraction_confidence, positive_factors, negative_factors,
                       accepted_risks, decisive_factors, overridden_criteria,
                       strategic_exception, agreement_with_aethria, human_confidence,
                       evidence_influence, provenance, correction_note,
                       supersedes_interpretation_id, created_at
                from public.ruling_interpretations
                where user_id=$1 and opportunity_id=$2
                order by ruling_id, version
                """,
                uid,
                opportunity_id,
            )
            outcomes = await conn.fetch(
                """
                select outcome_observation_id, company_id, opportunity_id,
                       outcome_type, valence, summary, verification_state,
                       materiality, effective_at, observed_at, supersedes_outcome_id
                from public.outcome_observations
                where user_id=$1 and opportunity_id=$2
                order by observed_at, outcome_observation_id
                """,
                uid,
                opportunity_id,
            )

        def normalize_json(
            item: Dict[str, Any], defaults: Dict[str, Any]
        ) -> Dict[str, Any]:
            normalized = dict(item)
            for key, default in defaults.items():
                normalized[key] = _json_value(normalized.get(key), default)
            return normalized

        evaluation_payloads = []
        for raw in evaluations:
            evaluation = normalize_json(
                dict(raw),
                {"claim_snapshot": [], "model_manifest": {}, "prompt_manifest": {}},
            )
            evaluation["decision_time"] = evaluation.get("completed_at") or evaluation.get("created_at")
            evaluation_payloads.append(evaluation)
        recommendation_by_evaluation = {}
        for raw in recommendations:
            recommendation = normalize_json(
                dict(raw),
                {
                    "decision_drivers": [], "principal_risks": [],
                    "mandate_conflicts": [], "missing_information": [],
                    "change_conditions": [],
                },
            )
            recommendation_by_evaluation[str(recommendation["evaluation_id"])] = recommendation
        criteria_by_evaluation: Dict[str, list[Dict[str, Any]]] = {}
        for raw in criteria:
            criterion = normalize_json(
                dict(raw),
                {
                    "supporting_claim_ids": [], "contradicting_claim_ids": [],
                    "missing_evidence": [], "quality_flags": [],
                    "deterministic_adjustments": {},
                },
            )
            evaluation_id = str(criterion.pop("evaluation_id"))
            criteria_by_evaluation.setdefault(evaluation_id, []).append(criterion)

        recommendation_ids = {
            str(item["recommendation_id"]): str(item["evaluation_id"])
            for item in recommendation_by_evaluation.values()
        }
        interpretations_by_ruling: Dict[str, list[Dict[str, Any]]] = {}
        for raw in interpretations:
            interpretation = normalize_json(
                dict(raw),
                {
                    "positive_factors": [], "negative_factors": [], "accepted_risks": [],
                    "decisive_factors": [], "overridden_criteria": [],
                    "evidence_influence": {"status": "unknown", "references": [], "limitations": []},
                    "provenance": {},
                },
            )
            interpretations_by_ruling.setdefault(
                str(interpretation["ruling_id"]), []
            ).append(interpretation)
        rulings_by_evaluation: Dict[str, list[Dict[str, Any]]] = {}
        unpaired_rulings = []
        for raw in rulings:
            ruling = dict(raw)
            history = interpretations_by_ruling.get(str(ruling.get("ruling_id")), [])
            ruling["interpretation"] = history[-1] if history else None
            ruling["interpretation_history"] = history
            recommendation_id = ruling.get("recommendation_id")
            evaluation_id = recommendation_ids.get(str(recommendation_id)) if recommendation_id else None
            if evaluation_id is None:
                unpaired_rulings.append(ruling)
            else:
                rulings_by_evaluation.setdefault(evaluation_id, []).append(ruling)

        cases = []
        for evaluation in evaluation_payloads:
            evaluation_id = str(evaluation["evaluation_id"])
            cases.append(
                {
                    "decision_time": evaluation["decision_time"],
                    "evaluation": evaluation,
                    "criteria": criteria_by_evaluation.get(evaluation_id, []),
                    "recommendation": recommendation_by_evaluation.get(evaluation_id),
                    "rulings": rulings_by_evaluation.get(evaluation_id, []),
                }
            )

        current = dict(opportunity_row)
        return {
            "opportunity": {
                "opportunity_id": current["opportunity_id"],
                "company_id": current["company_id"],
                "context_key": current["context_key"],
            },
            "current_identity": {
                "canonical_name": current["canonical_name"],
                "canonical_domain": current["canonical_domain"],
            },
            "current_lifecycle": {
                key: current[key]
                for key in (
                    "decision_state", "service_level", "current_evaluation_id",
                    "current_recommendation_id", "current_ruling_id", "updated_at",
                )
            },
            "cases": cases,
            "outcomes": [dict(item) for item in outcomes],
            "unpaired_rulings": unpaired_rulings,
        }

    async def get_precedents(
        self, *, user_id: str, evaluation_id: str, limit: int = 10
    ) -> Optional[Dict[str, Any]]:
        """Rank tenant-scoped historical evaluation episodes as explainable precedents."""
        from decisions.precedent import rank_precedents

        uid = require_user_id(user_id, context="IdentityRepository.get_precedents")
        bounded = max(1, min(int(limit), 50))
        async with self.pool.acquire() as conn:
            target_row = await conn.fetchrow(
                """
                select e.evaluation_id, e.opportunity_id, o.company_id, o.context_key,
                       e.claim_snapshot, e.thesis_version_id, e.policy_version_id,
                       e.created_at, e.completed_at
                from public.evaluation_runs e
                join public.opportunities o
                  on o.user_id=e.user_id and o.opportunity_id=e.opportunity_id
                where e.user_id=$1 and e.evaluation_id=$2 and e.status='completed'
                """,
                uid,
                evaluation_id,
            )
            if target_row is None:
                return None
            rows = await conn.fetch(
                """
                select e.evaluation_id, e.opportunity_id, o.company_id, o.context_key,
                       e.claim_snapshot, e.thesis_version_id, e.policy_version_id,
                       e.created_at, e.completed_at
                from public.evaluation_runs e
                join public.opportunities o
                  on o.user_id=e.user_id and o.opportunity_id=e.opportunity_id
                where e.user_id=$1 and e.status='completed' and e.evaluation_id<>$2
                order by coalesce(e.completed_at,e.created_at) desc, e.evaluation_id
                limit $3
                """,
                uid,
                evaluation_id,
                max(100, bounded * 20),
            )
            evaluation_rows = [dict(target_row), *[dict(row) for row in rows]]
            evaluation_ids = [str(row["evaluation_id"]) for row in evaluation_rows]
            recommendations = await conn.fetch(
                """
                select r.recommendation_id, r.opportunity_id, r.evaluation_id,
                       r.recommended_state, r.created_at
                from public.recommendations r
                where r.user_id=$1 and r.evaluation_id = any($2::uuid[])
                """,
                uid,
                evaluation_ids,
            )
            criteria = await conn.fetch(
                """
                select ca.evaluation_id, ca.criterion, ca.score, ca.confidence
                from public.criterion_assessments ca
                where ca.user_id=$1 and ca.evaluation_id = any($2::uuid[])
                order by ca.evaluation_id, ca.criterion
                """,
                uid,
                evaluation_ids,
            )
            rulings = await conn.fetch(
                """
                select hr.ruling_id, hr.opportunity_id, hr.recommendation_id,
                       hr.decision, hr.created_at, os.override_type
                from public.human_rulings hr
                left join public.override_signals os
                  on os.user_id=hr.user_id and os.ruling_id=hr.ruling_id
                where hr.user_id=$1
                order by hr.created_at desc
                limit 5000
                """,
                uid,
            )
            interpretations = await conn.fetch(
                """
                select ri.*
                from public.ruling_interpretations ri
                where ri.user_id=$1
                order by ri.ruling_id, ri.version desc
                limit 5000
                """,
                uid,
            )
            outcomes = await conn.fetch(
                """
                select outcome_observation_id, opportunity_id, outcome_type, valence,
                       verification_state, materiality, effective_at, observed_at
                from public.outcome_observations
                where user_id=$1
                order by observed_at desc
                limit 5000
                """,
                uid,
            )

        def json_value(value: Any, default: Any) -> Any:
            return _json_value(value, default)

        recommendation_by_evaluation = {
            str(row["evaluation_id"]): dict(row) for row in recommendations
        }
        criteria_by_evaluation: Dict[str, list[Dict[str, Any]]] = {}
        for row in criteria:
            criteria_by_evaluation.setdefault(str(row["evaluation_id"]), []).append(dict(row))
        interpretation_by_ruling: Dict[str, Dict[str, Any]] = {}
        for row in interpretations:
            ruling_id = str(row["ruling_id"])
            if ruling_id not in interpretation_by_ruling:
                interpretation_by_ruling[ruling_id] = dict(row)
        rulings_by_recommendation: Dict[str, list[Dict[str, Any]]] = {}
        unpaired_by_opportunity: Dict[str, list[Dict[str, Any]]] = {}
        recommendation_ids = {str(row["recommendation_id"]) for row in recommendations}
        for row in rulings:
            ruling = dict(row)
            recommendation_id = ruling.get("recommendation_id")
            if recommendation_id and str(recommendation_id) in recommendation_ids:
                rulings_by_recommendation.setdefault(str(recommendation_id), []).append(ruling)
            else:
                unpaired_by_opportunity.setdefault(str(ruling["opportunity_id"]), []).append(ruling)
        outcomes_by_opportunity: Dict[str, list[Dict[str, Any]]] = {}
        for row in outcomes:
            outcomes_by_opportunity.setdefault(str(row["opportunity_id"]), []).append(dict(row))

        def episode(row: Dict[str, Any]) -> Dict[str, Any]:
            eid = str(row["evaluation_id"])
            recommendation = recommendation_by_evaluation.get(eid)
            recommendation_id = str(recommendation["recommendation_id"]) if recommendation else None
            linked_rulings = []
            for ruling in rulings_by_recommendation.get(recommendation_id or "", []):
                normalized = dict(ruling)
                normalized["interpretation"] = interpretation_by_ruling.get(str(ruling["ruling_id"]))
                linked_rulings.append(normalized)
            evaluation = {
                "evaluation_id": eid,
                "thesis_version_id": row.get("thesis_version_id"),
                "policy_version_id": row.get("policy_version_id"),
                "claim_snapshot": json_value(row.get("claim_snapshot"), []),
            }
            return {
                "opportunity": {
                    "opportunity_id": row["opportunity_id"],
                    "company_id": row["company_id"],
                    "context_key": row["context_key"],
                },
                "cases": [{
                    "decision_time": row.get("completed_at") or row.get("created_at"),
                    "evaluation": evaluation,
                    "criteria": criteria_by_evaluation.get(eid, []),
                    "recommendation": recommendation,
                    "rulings": linked_rulings,
                }],
                "outcomes": outcomes_by_opportunity.get(str(row["opportunity_id"]), []),
                "unpaired_rulings": unpaired_by_opportunity.get(str(row["opportunity_id"]), []),
            }

        target = episode(dict(target_row))
        candidates = [episode(row) for row in evaluation_rows[1:]]
        return {
            "evaluation_id": evaluation_id,
            "precedents": rank_precedents(target, candidates, limit=bounded),
        }

    async def list_linked_legacy_startup_ids(self, *, user_id: str) -> List[str]:
        uid = require_user_id(
            user_id,
            context="IdentityRepository.list_linked_legacy_startup_ids",
        )
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select legacy_startup_id from public.opportunities
                where user_id=$1 and legacy_startup_id is not null
                order by updated_at desc
                """,
                uid,
            )
        return [str(row["legacy_startup_id"]) for row in rows]

    async def set_opportunity_state(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        decision_state: Any,
    ) -> OpportunityRecord:
        uid = require_user_id(
            user_id, context="IdentityRepository.set_opportunity_state"
        )
        state = getattr(decision_state, "value", decision_state)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.opportunities
                set decision_state = $3, updated_at = now()
                where opportunity_id = $1 and user_id = $2
                returning *
                """,
                opportunity_id,
                uid,
                str(state),
            )
        opportunity = _opportunity_from_row(row)
        if opportunity is None:
            raise LookupError("Opportunity not found for tenant")
        return opportunity

    async def list_cases(
        self, *, user_id: str, status: str = "open", limit: int = 100
    ) -> List[IdentityResolutionCaseRecord]:
        uid = require_user_id(user_id, context="IdentityRepository.list_cases")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.identity_resolution_cases
                where user_id = $1 and status = $2
                order by created_at desc
                limit $3
                """,
                uid,
                status,
                max(1, min(int(limit), 500)),
            )
        return [case for row in rows if (case := _case_from_row(row)) is not None]

    async def list_case_groups(
        self, *, user_id: str, status: str = "open", limit: int = 100
    ) -> List["IdentityCaseGroup"]:
        """Group cases by the canonical identity their observation names.

        Verified domain is the only signal treated as reliable enough to merge
        cases automatically (fix direction step 1/5 in known-issues.md): two
        observations that share a normalized domain are almost certainly the
        same company, so their cases are grouped into one review unit. A case
        whose observation has no domain is left in its own singleton group —
        matching only on company name is not confident enough to auto-merge,
        and stays separate until a human confirms it.
        """
        uid = require_user_id(user_id, context="IdentityRepository.list_case_groups")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select c.*, o.observed_domain, o.observed_name, o.channel
                from public.identity_resolution_cases c
                join public.source_observations o
                  on o.user_id = c.user_id and o.observation_id = c.observation_id
                where c.user_id = $1 and c.status = $2
                order by c.created_at desc
                limit $3
                """,
                uid,
                status,
                max(1, min(int(limit), 500)),
            )

        groups_by_domain: Dict[str, IdentityCaseGroup] = {}
        ordered_groups: List[IdentityCaseGroup] = []
        for row in rows:
            payload = db_row(row)
            observed_domain = payload.pop("observed_domain", None)
            observed_name = payload.pop("observed_name", None)
            channel = payload.pop("channel", None)
            payload["candidates"] = _json_value(payload.get("candidates"), [])
            case = IdentityResolutionCaseRecord.model_validate(payload)
            normalized_domain = normalize_domain(observed_domain)

            if normalized_domain is not None and normalized_domain in groups_by_domain:
                group = groups_by_domain[normalized_domain]
                group.cases.append(case)
                if observed_name and observed_name not in group.observed_names:
                    group.observed_names.append(observed_name)
                if channel and channel not in group.sources:
                    group.sources.append(channel)
                continue

            group = IdentityCaseGroup(
                group_key=normalized_domain or f"case:{case.identity_case_id}",
                canonical_domain=normalized_domain,
                cases=[case],
                observed_names=[observed_name] if observed_name else [],
                sources=[channel] if channel else [],
            )
            if normalized_domain is not None:
                groups_by_domain[normalized_domain] = group
            ordered_groups.append(group)

        return ordered_groups

    async def get_case(
        self, *, user_id: str, identity_case_id: str
    ) -> Optional[IdentityResolutionCaseRecord]:
        uid = require_user_id(user_id, context="IdentityRepository.get_case")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.identity_resolution_cases
                where identity_case_id = $1 and user_id = $2
                """,
                identity_case_id,
                uid,
            )
        return _case_from_row(row)

    async def list_observations(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SourceObservationRecord]:
        uid = require_user_id(user_id, context="IdentityRepository.list_observations")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.source_observations
                where user_id = $1
                  and ($2::text is null or identity_status = $2)
                order by observed_at desc, observation_id desc
                limit $3
                """,
                uid,
                status,
                max(1, min(int(limit), 500)),
            )
        return [
            observation
            for row in rows
            if (observation := _observation_from_row(row)) is not None
        ]

    async def _transition_case(
        self,
        *,
        user_id: str,
        identity_case_id: str,
        status: str,
        resolved_by: str,
        resolution_note: Optional[str],
    ) -> IdentityResolutionCaseRecord:
        uid = require_user_id(user_id, context="IdentityRepository.transition_case")
        if status not in {"deferred", "rejected"}:
            raise ValueError("Unsupported identity case transition")
        actor = str(resolved_by or "").strip()
        if not actor:
            raise ValueError("resolved_by is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.identity_resolution_cases
                    set status = $3, resolution_note = $4, resolved_by = $5,
                        resolved_at = now(), updated_at = now()
                    where identity_case_id = $1 and user_id = $2 and status = 'open'
                    returning *
                    """,
                    identity_case_id,
                    uid,
                    status,
                    (str(resolution_note or "").strip() or None),
                    actor,
                )
                case = _case_from_row(row)
                if case is None:
                    raise LookupError("Open identity case not found for tenant")
                observation_status = "deferred" if status == "deferred" else "rejected"
                await conn.execute(
                    """
                    update public.source_observations
                    set identity_status = $3, updated_at = now()
                    where observation_id = $1 and user_id = $2
                      and identity_status = 'ambiguous'
                    """,
                    case.observation_id,
                    uid,
                    observation_status,
                )
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="identity_resolution_case",
                    aggregate_id=identity_case_id,
                    event_type=f"identity_case.{status}",
                    payload={
                        "identity_case_id": identity_case_id,
                        "observation_id": case.observation_id,
                        "status": status,
                        "resolved_by": actor,
                    },
                )
                return case

    async def defer_case(self, **kwargs: Any) -> IdentityResolutionCaseRecord:
        return await self._transition_case(status="deferred", **kwargs)

    async def reject_case(self, **kwargs: Any) -> IdentityResolutionCaseRecord:
        return await self._transition_case(status="rejected", **kwargs)

    async def create_company_from_case(
        self,
        *,
        user_id: str,
        identity_case_id: str,
        canonical_name: str,
        canonical_domain: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
        context_key: str = "primary",
    ) -> IdentityAdmission:
        """Atomically create/converge a company and resolve an ambiguity case."""

        uid = require_user_id(
            user_id, context="IdentityRepository.create_company_from_case"
        )
        await self._require_write_path(user_id=uid, operation="identity linkage")
        name = str(canonical_name or "").strip()
        domain = normalize_domain(canonical_domain)
        actor = str(resolved_by or "").strip()
        if not name or not domain or not actor:
            raise ValueError("canonical name, domain, and resolved_by are required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                case_row = await conn.fetchrow(
                    """
                    select * from public.identity_resolution_cases
                    where identity_case_id = $1 and user_id = $2 and status = 'open'
                    for update
                    """,
                    identity_case_id,
                    uid,
                )
                case = _case_from_row(case_row)
                if case is None:
                    raise LookupError("Open identity case not found for tenant")
                observation_row = await conn.fetchrow(
                    """
                    select * from public.source_observations
                    where observation_id = $1 and user_id = $2
                      and identity_status = 'ambiguous'
                    for update
                    """,
                    case.observation_id,
                    uid,
                )
                observation = _observation_from_row(observation_row)
                if observation is None:
                    raise LookupError("Ambiguous observation not found for tenant")
                company_row = await conn.fetchrow(
                    """
                    insert into public.companies (
                      company_id, user_id, canonical_name, canonical_domain,
                      identity_confidence, status, metadata, created_at, updated_at
                    ) values ($1, $2, $3, $4, 1, 'active', '{}'::jsonb, now(), now())
                    on conflict do nothing
                    returning *
                    """,
                    str(uuid4()),
                    uid,
                    name,
                    domain,
                )
                created = company_row is not None
                if company_row is None:
                    company_row = await conn.fetchrow(
                        """
                        select * from public.companies
                        where user_id = $1 and canonical_domain = $2 and status = 'active'
                        for update
                        """,
                        uid,
                        domain,
                    )
                company = _company_from_row(company_row)
                if company is None:
                    raise RuntimeError("Canonical company create/converge returned no row")
                identifier = NormalizedIdentifier(
                    identifier_type="domain",
                    normalized_value=domain,
                    raw_value=canonical_domain,
                    verification_status=VerificationStatus.VERIFIED,
                    confidence=1,
                    is_primary=True,
                )
                await self._store_identifiers(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    observation_id=case.observation_id,
                    identifiers=[identifier],
                )
                await self._store_alias(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    observation_id=case.observation_id,
                    alias=observation.observed_name,
                )
                await conn.execute(
                    """
                    update public.source_observations
                    set company_id = $3, identity_status = 'resolved',
                        identity_confidence = 1, updated_at = now()
                    where observation_id = $1 and user_id = $2
                    """,
                    case.observation_id,
                    uid,
                    company.company_id,
                )
                opportunity = await self._upsert_opportunity(
                    conn,
                    user_id=uid,
                    company_id=company.company_id,
                    context_key=context_key,
                    observation_id=case.observation_id,
                    legacy_startup_id=observation.legacy_startup_id,
                )
                await conn.execute(
                    """
                    update public.identity_resolution_cases
                    set status = 'resolved', selected_company_id = $3,
                        resolution_note = $4, resolved_by = $5,
                        resolved_at = now(), updated_at = now()
                    where identity_case_id = $1 and user_id = $2
                    """,
                    identity_case_id,
                    uid,
                    company.company_id,
                    (str(resolution_note or "").strip() or None),
                    actor,
                )
                await self._insert_outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="identity_resolution_case",
                    aggregate_id=identity_case_id,
                    event_type="identity_case.resolved",
                    payload={
                        "identity_case_id": identity_case_id,
                        "observation_id": case.observation_id,
                        "company_id": company.company_id,
                        "opportunity_id": opportunity.opportunity_id,
                        "legacy_startup_id": (
                            str(opportunity.legacy_startup_id)
                            if opportunity.legacy_startup_id
                            else None
                        ),
                        "compatibility_reason": "canonical identity resolved",
                        "created": created,
                        "resolved_by": actor,
                    },
                )
                return IdentityAdmission(
                    user_id=uid,
                    observation_id=case.observation_id,
                    status=IdentityStatus.RESOLVED,
                    company_id=company.company_id,
                    opportunity_id=opportunity.opportunity_id,
                    identity_case_id=identity_case_id,
                    confidence=1,
                    created=created,
                )

    async def reconciliation_counts(self, *, user_id: str) -> Dict[str, int]:
        uid = require_user_id(
            user_id, context="IdentityRepository.reconciliation_counts"
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select
                  count(*) filter (where o.identity_status = 'pending') as pending,
                  count(*) filter (
                    where o.identity_status = 'resolved'
                      and (o.opportunity_id is null or p.opportunity_id is null)
                  ) as resolved_without_opportunity,
                  count(*) filter (
                    where o.legacy_startup_id is not null and p.legacy_startup_id is null
                  ) as missing_projection_link,
                  count(*) filter (
                    where o.identity_status = 'ambiguous' and c.identity_case_id is null
                  ) as ambiguous_without_case
                from public.source_observations o
                left join public.opportunities p
                  on p.user_id = o.user_id
                 and p.opportunity_id = o.opportunity_id
                left join public.identity_resolution_cases c
                  on c.user_id = o.user_id and c.observation_id = o.observation_id
                 and c.status = 'open'
                where o.user_id = $1
                """,
                uid,
            )
        return {
            key: int((row or {}).get(key) or 0)
            for key in (
                "pending",
                "resolved_without_opportunity",
                "missing_projection_link",
                "ambiguous_without_case",
            )
        }
