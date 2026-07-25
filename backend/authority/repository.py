"""Transactional, tenant-scoped authority rollout and workflow storage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Optional
from uuid import UUID, uuid4

from authority.models import (
    BlockCode,
    RolloutMode,
    RolloutRecord,
    WorkflowState,
    WorkflowStateRecord,
)
from tenant_context import require_user_id
from utils.db_rows import db_row


class AuthorityConflict(RuntimeError):
    """A tenant-scoped authority record changed before the requested write."""


class AuthorityTransitionError(ValueError):
    """The requested rollout or workflow transition is not permitted."""


class AuthorityBlocked(RuntimeError):
    """A kill switch prevents a canonical authority write."""


LEGAL_ROLLOUT_TRANSITIONS = {
    RolloutMode.LEGACY: {RolloutMode.SHADOW},
    RolloutMode.SHADOW: {RolloutMode.BACKFILL, RolloutMode.LEGACY},
    RolloutMode.BACKFILL: {
        RolloutMode.CANONICAL_WRITE,
        RolloutMode.SHADOW,
        RolloutMode.LEGACY,
    },
    RolloutMode.CANONICAL_WRITE: {
        RolloutMode.CANONICAL_READ,
        RolloutMode.BACKFILL,
        RolloutMode.LEGACY,
    },
    RolloutMode.CANONICAL_READ: {RolloutMode.CANONICAL_WRITE, RolloutMode.LEGACY},
}


class AuthorityRepository:
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
        payload: Mapping[str, Any],
    ) -> None:
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id,user_id,aggregate_type,aggregate_id,event_type,event_version,
              payload,publication_attempts,next_attempt_at,created_at
            ) values ($1,$2,$3,$4,$5,1,$6::jsonb,0,now(),now())
            """,
            str(uuid4()),
            user_id,
            aggregate_type,
            aggregate_id,
            event_type,
            json.dumps(payload, default=str),
        )

    @staticmethod
    def _rollout(row: Any, *, user_id: str) -> RolloutRecord:
        if row is None:
            raise AuthorityConflict("authority rollout was not found for tenant")
        payload = db_row(row)
        if payload.get("user_id") != user_id:
            raise AuthorityConflict("authority rollout tenant mismatch")
        return RolloutRecord.model_validate(payload)

    @staticmethod
    def _workflow(row: Any, *, user_id: str) -> WorkflowStateRecord:
        if row is None:
            raise AuthorityConflict("workflow state changed or was not found for tenant")
        payload = db_row(row)
        if payload.get("user_id") != user_id:
            raise AuthorityConflict("workflow state tenant mismatch")
        payload.pop("legacy_startup_id", None)
        payload["state"] = payload.pop("workflow_state")
        payload["version"] = payload.pop("workflow_version")
        return WorkflowStateRecord.model_validate(payload)

    @staticmethod
    async def _bootstrap_rollout(conn: Any, *, user_id: str) -> None:
        await conn.execute(
            """
            insert into public.tenant_authority_rollouts (user_id,mode,version,kill_switch)
            values ($1,'legacy',0,false)
            on conflict (user_id) do nothing
            """,
            user_id,
        )

    async def get_rollout(self, *, user_id: str) -> RolloutRecord:
        uid = require_user_id(user_id, context="AuthorityRepository.get_rollout")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._bootstrap_rollout(conn, user_id=uid)
                row = await conn.fetchrow(
                    """
                    select * from public.tenant_authority_rollouts
                    where user_id=$1
                    """,
                    uid,
                )
                return self._rollout(row, user_id=uid)

    async def transition_rollout(
        self,
        *,
        user_id: str,
        expected_version: int,
        target_mode: RolloutMode | str,
        actor_id: str,
        snapshot_id: Optional[str],
        kill_switch: bool = False,
        rollback_reason: Optional[str] = None,
    ) -> RolloutRecord:
        uid = require_user_id(user_id, context="AuthorityRepository.transition_rollout")
        actor = str(actor_id or "").strip()
        if not actor:
            raise ValueError("actor_id is required")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        target = RolloutMode(target_mode)
        if rollback_reason is not None and not str(rollback_reason).strip():
            raise ValueError("rollback_reason must be nonblank when supplied")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._bootstrap_rollout(conn, user_id=uid)
                current = self._rollout(
                    await conn.fetchrow(
                        """
                        select * from public.tenant_authority_rollouts
                        where user_id=$1 for update
                        """,
                        uid,
                    ),
                    user_id=uid,
                )
                if current.version != expected_version:
                    raise AuthorityConflict("stale authority rollout version")
                if current.kill_switch and not kill_switch:
                    raise AuthorityBlocked("authority kill switch is active")
                if target not in LEGAL_ROLLOUT_TRANSITIONS[current.mode]:
                    raise AuthorityTransitionError(
                        f"illegal authority rollout transition: {current.mode.value} -> {target.value}"
                    )
                if (
                    target is RolloutMode.CANONICAL_READ
                    and current.last_reconciliation_status != "green"
                ):
                    raise AuthorityTransitionError(
                        "canonical read requires green reconciliation"
                    )
                row = await conn.fetchrow(
                    """
                    update public.tenant_authority_rollouts
                    set mode=$3,version=version+1,activated_at=now(),activated_by=$4,
                        snapshot_id=$5,kill_switch=$6
                    where user_id=$1 and version=$2
                    returning *
                    """,
                    uid,
                    expected_version,
                    target.value,
                    actor,
                    snapshot_id,
                    bool(kill_switch),
                )
                updated = self._rollout(row, user_id=uid)
                event_type = (
                    "authority.rollback_requested"
                    if rollback_reason is not None
                    else "authority.rollout_transitioned"
                )
                payload = {
                    "user_id": uid,
                    "from_mode": current.mode.value,
                    "target_mode": target.value,
                    "version": updated.version,
                    "actor_id": actor,
                    "snapshot_id": snapshot_id,
                    "kill_switch": updated.kill_switch,
                }
                if rollback_reason is not None:
                    payload["reason"] = str(rollback_reason).strip()
                await self._outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="authority_rollout",
                    aggregate_id=uid,
                    event_type=event_type,
                    payload=payload,
                )
                return updated

    async def rearm_rollout(
        self,
        *,
        user_id: str,
        expected_version: int,
        actor_id: str,
        reason: str,
    ) -> RolloutRecord:
        """Explicitly clear a rollback kill switch after reconciliation succeeds."""
        uid = require_user_id(user_id, context="AuthorityRepository.rearm_rollout")
        actor = str(actor_id or "").strip()
        normalized_reason = str(reason or "").strip()
        if not actor:
            raise ValueError("actor_id is required")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        if not normalized_reason:
            raise ValueError("rearm reason is required")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._bootstrap_rollout(conn, user_id=uid)
                current = self._rollout(
                    await conn.fetchrow(
                        """
                        select * from public.tenant_authority_rollouts
                        where user_id=$1 for update
                        """,
                        uid,
                    ),
                    user_id=uid,
                )
                if current.version != expected_version:
                    raise AuthorityConflict("stale authority rollout version")
                if not current.kill_switch:
                    raise AuthorityTransitionError("authority kill switch is not active")
                if current.mode is not RolloutMode.LEGACY:
                    raise AuthorityTransitionError("authority re-arm requires legacy rollout mode")
                if current.last_reconciliation_status != "green":
                    raise AuthorityBlocked("authority re-arm requires green reconciliation")
                row = await conn.fetchrow(
                    """
                    update public.tenant_authority_rollouts
                    set kill_switch=false,version=version+1,activated_at=now(),activated_by=$3
                    where user_id=$1 and version=$2 and kill_switch=true
                    returning *
                    """,
                    uid,
                    expected_version,
                    actor,
                )
                updated = self._rollout(row, user_id=uid)
                await self._outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="authority_rollout",
                    aggregate_id=uid,
                    event_type="authority.kill_switch_cleared",
                    payload={
                        "user_id": uid,
                        "mode": updated.mode.value,
                        "version": updated.version,
                        "actor_id": actor,
                        "reason": normalized_reason,
                        "last_reconciliation_status": updated.last_reconciliation_status,
                    },
                )
                return updated

    @staticmethod
    def _block_values(
        *, target_state: WorkflowState, block: Optional[Mapping[str, Any]]
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if target_state is not WorkflowState.BLOCKED:
            if block is not None:
                raise ValueError("only blocked workflow states may carry block metadata")
            return None, None, None
        if not isinstance(block, Mapping):
            raise ValueError("blocked workflow state requires complete block metadata")
        code = block.get("code", block.get("block_code"))
        detail = block.get("detail", block.get("block_detail"))
        recovery = block.get("recovery", block.get("block_recovery"))
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("blocked workflow state requires block detail")
        if not isinstance(recovery, str) or not recovery.strip():
            raise ValueError("blocked workflow state requires block recovery")
        try:
            resolved_code = BlockCode(code)
        except (TypeError, ValueError) as exc:
            raise ValueError("blocked workflow state requires a valid block code") from exc
        return resolved_code.value, detail.strip(), recovery.strip()

    async def transition_workflow(
        self,
        *,
        user_id: str,
        opportunity_id: UUID | str,
        expected_version: int,
        target_state: WorkflowState | str,
        transition_id: UUID | str,
        block: Optional[Mapping[str, Any]] = None,
    ) -> WorkflowStateRecord:
        uid = require_user_id(user_id, context="AuthorityRepository.transition_workflow")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("expected_version must be a non-negative integer")
        target = WorkflowState(target_state)
        opportunity = UUID(str(opportunity_id))
        transition = UUID(str(transition_id))
        block_code, block_detail, block_recovery = self._block_values(
            target_state=target, block=block
        )

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await self._bootstrap_rollout(conn, user_id=uid)
                rollout = self._rollout(
                    await conn.fetchrow(
                        """
                        select * from public.tenant_authority_rollouts
                        where user_id=$1 for update
                        """,
                        uid,
                    ),
                    user_id=uid,
                )
                if rollout.kill_switch:
                    raise AuthorityBlocked("authority kill switch is active")
                row = await conn.fetchrow(
                    """
                    update public.opportunities
                    set workflow_state=$4,workflow_version=workflow_version+1,
                        block_code=$5,block_detail=$6,block_recovery=$7,
                        last_transition_id=$8,updated_at=now()
                    where user_id=$1 and opportunity_id=$2 and workflow_version=$3
                    returning user_id,opportunity_id,workflow_state,workflow_version,
                              block_code,block_detail,block_recovery,last_transition_id,
                              legacy_startup_id,updated_at
                    """,
                    uid,
                    str(opportunity),
                    expected_version,
                    target.value,
                    block_code,
                    block_detail,
                    block_recovery,
                    str(transition),
                )
                legacy_startup_id = (
                    str(row["legacy_startup_id"])
                    if row is not None and row.get("legacy_startup_id")
                    else None
                )
                record = self._workflow(row, user_id=uid)
                await self._outbox(
                    conn,
                    user_id=uid,
                    aggregate_type="opportunity",
                    aggregate_id=str(opportunity),
                    event_type="opportunity.workflow_changed",
                    payload={
                        "opportunity_id": str(opportunity),
                        "workflow_state": record.state.value,
                        "workflow_version": record.version,
                        "transition_id": str(transition),
                        "block_code": block_code,
                        "legacy_startup_id": legacy_startup_id,
                        "compatibility_reason": (
                            block_detail or f"workflow transitioned to {record.state.value}"
                        ),
                    },
                )
                return record
