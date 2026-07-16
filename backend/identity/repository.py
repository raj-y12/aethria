"""Transactional repository for tenant-scoped canonical company identity."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from identity.models import (
    CompanyRecord,
    IdentityAdmission,
    IdentityCandidate,
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
    def __init__(self, pool: Any):
        self.pool = pool

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
              service_level, first_observation_id, latest_observation_id,
              legacy_startup_id, created_at, updated_at
            ) values ($1, $2, $3, $4, 'discovered', 1, $5, $5, $6::uuid, now(), now())
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
                        "created": created,
                    },
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
