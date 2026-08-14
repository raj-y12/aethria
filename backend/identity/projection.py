"""Idempotent compatibility projection linkage and replay."""

from __future__ import annotations

import json
from typing import Any

from authority.models import ProjectionReceipt
from identity.models import IdentityAdmission, IdentityStatus
from jobs.models import DomainOutboxEvent
from tenant_context import require_user_id
from utils.db_rows import db_row


async def link_admission_projection(
    repository: Any,
    *,
    admission: IdentityAdmission,
    legacy_startup_id: str,
) -> Any:
    if admission.status is not IdentityStatus.RESOLVED or not admission.opportunity_id:
        raise ValueError("Only a resolved opportunity can link a legacy projection")
    return await repository.link_legacy_projection(
        user_id=admission.user_id,
        opportunity_id=admission.opportunity_id,
        legacy_startup_id=legacy_startup_id,
    )


class StartupCompatibilityProjectionRepository:
    """Atomic service-role repository for legacy startup display projections.

    The patch surface is intentionally limited to the compatibility fields of the
    legacy ``startups`` row.  It has no access to canonical opportunity pointers,
    rulings, or evaluations; the receipt and patch live in one transaction.
    """

    _JSON_COLUMNS = frozenset(
        {"scout_info", "review_info", "partner_info", "human_resolution", "agent_trace"}
    )
    _SCALAR_COLUMNS = frozenset({"investment_memo_markdown"})

    def __init__(self, pool: Any):
        self.pool = pool

    @staticmethod
    def _receipt(row: Any) -> ProjectionReceipt:
        return ProjectionReceipt.model_validate(db_row(row))

    async def resolve_legacy_startup_id(
        self, *, user_id: str, opportunity_id: str
    ) -> str | None:
        """Resolve the compatibility row for a tenant-owned opportunity.

        Older authority outbox events may predate ``legacy_startup_id`` being
        included in their payload.  The canonical opportunity still owns that
        linkage, so resolve it there rather than dropping the projection.
        """
        uid = require_user_id(
            user_id,
            context="StartupCompatibilityProjectionRepository.resolve_legacy_startup_id",
        )
        opportunity = str(opportunity_id or "").strip()
        if not opportunity:
            return None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select legacy_startup_id
                from public.opportunities
                where user_id=$1 and opportunity_id=$2::uuid
                """,
                uid,
                opportunity,
            )
        if row is None or row.get("legacy_startup_id") is None:
            return None
        return str(row["legacy_startup_id"])

    async def get_projection_receipt(self, *, user_id: str, event_id: str, consumer: str):
        uid = require_user_id(user_id, context="StartupCompatibilityProjectionRepository.get_projection_receipt")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.authority_projection_receipts
                where user_id=$1 and event_id=$2::uuid and consumer=$3
                """,
                uid,
                event_id,
                consumer,
            )
        return self._receipt(row) if row is not None else None

    async def apply_legacy_projection(
        self,
        *,
        user_id: str,
        event_id: str,
        consumer: str,
        aggregate_type: str,
        aggregate_id: str,
        patch: Any,
        projection_hash: str | None = None,
    ) -> ProjectionReceipt:
        """Claim receipt and mutate only the legacy display row atomically."""
        uid = require_user_id(user_id, context="StartupCompatibilityProjectionRepository.apply_legacy_projection")
        startup_id = str(patch.startup_id).strip()
        if not startup_id:
            raise ValueError("legacy startup id is required")
        values = dict(patch.patch)
        invalid = set(values) - self._JSON_COLUMNS - self._SCALAR_COLUMNS
        if invalid:
            raise ValueError(f"unsupported legacy compatibility fields: {sorted(invalid)!r}")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                inserted = await conn.fetchrow(
                    """
                    insert into public.authority_projection_receipts (
                      receipt_id,user_id,event_id,consumer,aggregate_type,aggregate_id,
                      projection_hash,applied_at
                    ) values (gen_random_uuid(),$1,$2::uuid,$3,$4,$5::uuid,$6,now())
                    on conflict (user_id,event_id,consumer) do nothing
                    returning *
                    """,
                    uid,
                    event_id,
                    consumer,
                    aggregate_type,
                    aggregate_id,
                    projection_hash,
                )
                if inserted is None:
                    existing = await conn.fetchrow(
                        """
                        select * from public.authority_projection_receipts
                        where user_id=$1 and event_id=$2::uuid and consumer=$3
                        """,
                        uid,
                        event_id,
                        consumer,
                    )
                    if existing is None:  # pragma: no cover - defensive driver guard
                        raise RuntimeError("projection receipt conflict could not be resolved")
                    return self._receipt(existing)

                assignments: list[str] = []
                arguments: list[Any] = [uid, startup_id]
                parameter = 3
                for column in sorted(values):
                    value = values[column]
                    if column in self._JSON_COLUMNS:
                        assignments.append(
                            f"{column}=coalesce({column},'{{}}'::jsonb) || ${parameter}::jsonb"
                        )
                        arguments.append(json.dumps(value))
                    else:
                        assignments.append(f"{column}=${parameter}")
                        arguments.append(value)
                    parameter += 1
                assignments.append("updated_at=now()")
                row = await conn.fetchrow(
                    f"""
                    update public.startups
                    set {', '.join(assignments)}
                    where user_id=$1 and startup_id=$2
                    returning startup_id
                    """,
                    *arguments,
                )
                if row is None:
                    raise LookupError("legacy startup was not found for tenant")
                return self._receipt(inserted)

    async def get_outbox_event(self, *, user_id: str, event_id: str):
        uid = require_user_id(user_id, context="StartupCompatibilityProjectionRepository.get_outbox_event")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from public.domain_outbox where user_id=$1 and event_id=$2::uuid",
                uid,
                event_id,
            )
        return self._outbox_event(row)

    async def list_pending_authority_events(self, *, user_id: str, opportunity_id: str | None = None):
        uid = require_user_id(user_id, context="StartupCompatibilityProjectionRepository.list_pending_authority_events")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.domain_outbox
                where user_id=$1 and published_at is null
                  and ($2::uuid is null or aggregate_id=$2::uuid or payload->>'opportunity_id'=$2)
                order by created_at,event_id
                """,
                uid,
                opportunity_id,
            )
        return [event for row in rows if (event := self._outbox_event(row)) is not None]

    @staticmethod
    def _outbox_event(row: Any):
        if row is None:
            return None
        payload = db_row(row)
        raw_payload = payload.get("payload")
        if isinstance(raw_payload, str):
            payload["payload"] = json.loads(raw_payload)
        return DomainOutboxEvent.model_validate(payload)
