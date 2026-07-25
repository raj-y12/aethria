"""Mode-aware guards for tenant authority control."""

from __future__ import annotations

from dataclasses import dataclass

from authority.models import RolloutMode, RolloutRecord
from authority.repository import AuthorityBlocked, AuthorityRepository, AuthorityTransitionError
from tenant_context import require_user_id


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    user_id: str
    mode: RolloutMode
    version: int
    kill_switch: bool
    last_reconciliation_status: str | None

    @property
    def canonical_writes_allowed(self) -> bool:
        return not self.kill_switch and self.mode in {
            RolloutMode.SHADOW,
            RolloutMode.BACKFILL,
            RolloutMode.CANONICAL_WRITE,
        }

    @property
    def canonical_reads_allowed(self) -> bool:
        return (
            not self.kill_switch
            and self.mode is RolloutMode.CANONICAL_READ
            and (self.last_reconciliation_status or "").strip().lower() == "green"
        )

    @property
    def legacy_projection_allowed(self) -> bool:
        return not self.kill_switch and self.mode in {
            RolloutMode.LEGACY,
            RolloutMode.BACKFILL,
            RolloutMode.CANONICAL_WRITE,
        }


class AuthorityService:
    def __init__(self, repository: AuthorityRepository):
        self.repository = repository

    @staticmethod
    def _context(record: RolloutRecord) -> AuthorityContext:
        return AuthorityContext(
            user_id=record.user_id,
            mode=record.mode,
            version=record.version,
            kill_switch=record.kill_switch,
            last_reconciliation_status=record.last_reconciliation_status,
        )

    async def authority(self, *, user_id: str) -> AuthorityContext:
        uid = require_user_id(user_id, context="AuthorityService.authority")
        return self._context(await self.repository.get_rollout(user_id=uid))

    async def require_write_path(self, *, user_id: str, operation: str) -> AuthorityContext:
        uid = require_user_id(user_id, context="AuthorityService.require_write_path")
        operation_name = str(operation or "").strip()
        if not operation_name:
            raise ValueError("operation is required")
        context = await self.authority(user_id=uid)
        if context.kill_switch:
            raise AuthorityBlocked(
                f"{operation_name} blocked: authority kill switch is active"
            )
        if context.mode is RolloutMode.CANONICAL_READ:
            raise AuthorityBlocked(
                f"{operation_name} blocked: canonical read mode is read-only"
            )
        return context

    async def require_legacy_pipeline_path(self, *, user_id: str) -> AuthorityContext:
        """Reject legacy Scout/Reviewer/Partner writes once canonical authority owns them."""
        context = await self.authority(user_id=user_id)
        if context.kill_switch or context.mode in {RolloutMode.CANONICAL_WRITE, RolloutMode.CANONICAL_READ}:
            raise AuthorityBlocked("legacy pipeline is blocked by canonical authority")
        return context

    async def assert_write_path_on_connection(self, conn: object, *, user_id: str, operation: str):
        return await self.repository.assert_write_path_on_connection(conn, user_id=user_id, operation=operation)

    async def rollback(
        self,
        *,
        user_id: str,
        expected_version: int,
        actor_id: str,
        reason: str,
    ) -> RolloutRecord:
        uid = require_user_id(user_id, context="AuthorityService.rollback")
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValueError("rollback reason is required")
        context = await self.authority(user_id=uid)
        if context.mode not in {RolloutMode.CANONICAL_WRITE, RolloutMode.CANONICAL_READ}:
            raise AuthorityTransitionError("rollback requires a canonical rollout mode")
        return await self.repository.transition_rollout(
            user_id=uid,
            expected_version=expected_version,
            target_mode=RolloutMode.LEGACY,
            actor_id=actor_id,
            snapshot_id=None,
            kill_switch=True,
            rollback_reason=normalized_reason,
        )

    async def rearm(
        self,
        *,
        user_id: str,
        expected_version: int,
        actor_id: str,
        reason: str,
    ) -> RolloutRecord:
        """Clear a rollback kill switch only through the audited recovery path."""
        uid = require_user_id(user_id, context="AuthorityService.rearm")
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValueError("rearm reason is required")
        context = await self.authority(user_id=uid)
        if not context.kill_switch:
            raise AuthorityTransitionError("authority kill switch is not active")
        if context.last_reconciliation_status != "green":
            raise AuthorityBlocked("authority re-arm requires green reconciliation")
        return await self.repository.rearm_rollout(
            user_id=uid,
            expected_version=expected_version,
            actor_id=actor_id,
            reason=normalized_reason,
        )

    async def set_reconciliation_status(self, *, user_id: str, expected_version: int,
                                        actor_id: str, status: str) -> RolloutRecord:
        uid = require_user_id(user_id, context="AuthorityService.set_reconciliation_status")
        return await self.repository.set_reconciliation_status(
            user_id=uid, expected_version=expected_version, actor_id=actor_id, status=status
        )


__all__ = ["AuthorityBlocked", "AuthorityContext", "AuthorityService"]
