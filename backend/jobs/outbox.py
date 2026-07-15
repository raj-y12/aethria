"""Publish transactional domain-outbox events through the existing event bus."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from event_bus import publish as event_publish


Publish = Callable[[str, str, dict], Awaitable[None]]


async def _publish_to_event_bus(user_id: str, event_type: str, payload: dict) -> None:
    event_publish(user_id, {"type": event_type, **payload})


class OutboxPublisher:
    def __init__(
        self,
        repository: Any,
        *,
        publish: Publish = _publish_to_event_bus,
        poll_interval_seconds: float = 2.0,
    ):
        self.repository = repository
        self.publish = publish
        self.poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self._stopping = asyncio.Event()
        self._runner: Optional[asyncio.Task] = None

    async def publish_once(self) -> int:
        events = await self.repository.claim_outbox_batch()
        published = 0
        for event in events:
            try:
                await self.publish(event.user_id, event.event_type, event.payload)
            except Exception as exc:
                await self.repository.mark_outbox_failed(
                    event_id=event.event_id, error=str(exc)
                )
                continue
            await self.repository.mark_outbox_published(event_id=event.event_id)
            published += 1
        return published

    async def _run(self) -> None:
        while not self._stopping.is_set():
            count = await self.publish_once()
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
