"""Publish transactional domain-outbox events through the existing event bus."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Mapping, Optional

import metrics
from event_bus import publish as event_publish


Publish = Callable[[str, str, dict], Awaitable[None]]
Project = Callable[[str, str, dict], Awaitable[None]]
Consumer = Callable[..., Awaitable[Any]]
logger = logging.getLogger("jobs.outbox")
_LOOP_ERROR_BACKOFF_MAX_SECONDS = 30.0
_LOOP_ERROR_BACKOFF_MAX_EXPONENT = 8


async def _publish_to_event_bus(user_id: str, event_type: str, payload: dict) -> None:
    event_publish(user_id, {"type": event_type, **payload})


async def _project_legacy_read_models(
    user_id: str, event_type: str, payload: dict
) -> None:
    """Compatibility hook retained for 5D; canonical policy events need no projection."""
    if event_type != "governed_policy_version.published":
        return
    return


class OutboxPublisher:
    def __init__(
        self,
        repository: Any,
        *,
        publish: Publish = _publish_to_event_bus,
        project: Project = _project_legacy_read_models,
        consumers: Mapping[str, Consumer] | None = None,
        poll_interval_seconds: float = 2.0,
    ):
        self.repository = repository
        self.publish = publish
        self.project = project
        self.consumers: dict[str, Consumer] = dict(consumers or {})
        if consumers is None and hasattr(repository, "pool"):
            self.consumers["authority"] = self._authority_consumer(repository)
        self.poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self._stopping = asyncio.Event()
        self._runner: Optional[asyncio.Task] = None

    @staticmethod
    def _authority_consumer(repository: Any) -> Consumer:
        """Build the canonical-to-legacy startup projector for durable outbox use."""
        from authority.projection import AuthorityProjectionConsumer
        from authority.repository import AuthorityRepository
        from authority.service import AuthorityService
        from identity.projection import StartupCompatibilityProjectionRepository

        consumer = AuthorityProjectionConsumer(
            StartupCompatibilityProjectionRepository(repository.pool),
            authority_service=AuthorityService(AuthorityRepository(repository.pool)),
        )

        async def apply(**event: Any) -> Any:
            return await consumer.apply(**event)

        return apply

    async def _consume(self, event: Any, payload: dict) -> None:
        """Run registered compatibility consumers without changing policy projection."""
        if not self.consumers:
            return
        from authority.projection import is_authority_projection_event

        event_data = {
            "user_id": event.user_id,
            "event_id": event.event_id,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "event_type": event.event_type,
            "payload": payload,
        }
        for name, consumer in self.consumers.items():
            if name == "authority":
                if not is_authority_projection_event(event.event_type):
                    continue
            elif name != event.event_type:
                continue
            result = await consumer(**event_data)
            if name == "authority" and result is None:
                from authority.projection import ProjectionDeferred
                raise ProjectionDeferred("authority projection deferred; event remains retryable")

    async def publish_once(self) -> int:
        events = await self.repository.claim_outbox_batch()
        published = 0
        for event in events:
            try:
                payload = event.payload
                projected_version_id = None
                if event.event_type == "governed_policy_version.published":
                    loader = getattr(
                        self.repository,
                        "get_current_governed_policy_projection",
                        None,
                    )
                    if not callable(loader):
                        raise RuntimeError(
                            "Outbox repository cannot resolve authoritative policy projection"
                        )
                    projection = await loader(user_id=event.user_id)
                    if projection is None:
                        raise RuntimeError(
                            "Published governed policy projection is unavailable"
                        )
                    payload = projection
                    projected_version_id = projection[
                        "governed_policy_version_id"
                    ]
                await self.project(event.user_id, event.event_type, payload)
                await self._consume(event, payload)
                if projected_version_id is not None:
                    current = await self.repository.get_current_governed_policy_projection(
                        user_id=event.user_id
                    )
                    if (
                        current is None
                        or current["governed_policy_version_id"]
                        != projected_version_id
                    ):
                        raise RuntimeError(
                            "Governed policy changed during legacy projection; retrying latest"
                        )
                await self.publish(event.user_id, event.event_type, payload)
            except Exception as exc:
                metrics.inc_outbox_publication(outcome="failed")
                await self.repository.mark_outbox_failed(
                    event_id=event.event_id, error=str(exc)
                )
                continue
            await self.repository.mark_outbox_published(event_id=event.event_id)
            metrics.inc_outbox_publication(outcome="published")
            published += 1
        return published

    async def _run(self) -> None:
        consecutive_failures = 0
        while not self._stopping.is_set():
            try:
                count = await self.publish_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                consecutive_failures += 1
                retry_seconds = min(
                    self.poll_interval_seconds
                    * (2 ** min(consecutive_failures - 1, _LOOP_ERROR_BACKOFF_MAX_EXPONENT)),
                    _LOOP_ERROR_BACKOFF_MAX_SECONDS,
                )
                logger.exception(
                    "Outbox publisher iteration failed; retrying in %.2fs",
                    retry_seconds,
                )
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=retry_seconds
                    )
                except asyncio.TimeoutError:
                    pass
                continue
            consecutive_failures = 0
            if count == 0:
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=self.poll_interval_seconds
                    )
                except asyncio.TimeoutError:
                    pass

    async def start(self) -> None:
        self._stopping.clear()
        self._runner = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._runner:
            await self._runner
            self._runner = None
