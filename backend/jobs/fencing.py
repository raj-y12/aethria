"""Cooperative lease-fencing shared by durable workers and job handlers."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from jobs.models import AgentJob, JobExecutionCancelled, JobLeaseLost, JobStatus


@dataclass
class LeaseFence:
    """A task-local signal that permanently closes after ownership is lost."""

    user_id: str
    job_id: str
    worker_id: str
    _reason: Optional[str] = None
    _lost: bool = field(default=False, init=False)

    @property
    def lost(self) -> bool:
        return self._lost

    @property
    def reason(self) -> str:
        return self._reason or "The durable job lease is no longer owned."

    def lose(self, reason: str) -> None:
        self._lost = True
        self._reason = str(reason or "").strip() or self.reason

    def ensure_owned(self) -> None:
        if self._lost:
            raise JobLeaseLost(self.reason)


_CURRENT_LEASE_FENCE: ContextVar[Optional[LeaseFence]] = ContextVar(
    "current_durable_job_lease_fence", default=None
)


def bind_lease_fence(fence: LeaseFence) -> Token:
    return _CURRENT_LEASE_FENCE.set(fence)


def reset_lease_fence(token: Token) -> None:
    _CURRENT_LEASE_FENCE.reset(token)


def current_lease_fence() -> Optional[LeaseFence]:
    return _CURRENT_LEASE_FENCE.get()


def mark_current_lease_lost(reason: str) -> None:
    fence = current_lease_fence()
    if fence is not None:
        fence.lose(reason)


async def assert_job_ownership(repository, job: AgentJob) -> None:
    """Fail closed when the shared signal or durable row rejects this owner."""

    fence = current_lease_fence()
    if fence is not None:
        if (
            fence.user_id != job.user_id
            or fence.job_id != job.job_id
            or fence.worker_id != str(job.lease_owner or "")
        ):
            fence.lose("The active lease fence does not match this job attempt.")
        fence.ensure_owned()

    getter = getattr(repository, "get_job", None)
    if getter is None:
        return
    current = await getter(user_id=job.user_id, job_id=job.job_id)
    if current is not None and current.status is JobStatus.CANCELLED:
        raise JobExecutionCancelled(f"Job {job.job_id} was cancelled")

    expected_owner = str(job.lease_owner or "").strip()
    current_owner = str(getattr(current, "lease_owner", None) or "").strip()
    lease_expiry = getattr(current, "lease_expires_at", None)
    expired = bool(
        lease_expiry is not None
        and lease_expiry <= datetime.now(timezone.utc)
    )
    if (
        current is None
        or current.status is not JobStatus.RUNNING
        or current_owner != expected_owner
        or expired
    ):
        reason = f"Durable job lease lost for {job.job_id}."
        if fence is not None:
            fence.lose(reason)
        raise JobLeaseLost(reason)

