"""Minimal durable job worker with leases, heartbeats, and bounded concurrency."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, Optional

from jobs.models import AgentJob, JobType
from jobs.postgres import database_dsn


logger = logging.getLogger("jobs.worker")
JobHandler = Callable[[AgentJob], Awaitable[None]]


class DurableJobWorker:
    def __init__(
        self,
        repository: Any,
        *,
        handlers: Dict[JobType, JobHandler],
        worker_id: str,
        poll_interval_seconds: float = 2.0,
        lease_seconds: int = 90,
        heartbeat_seconds: float = 20.0,
        global_concurrency: int = 2,
        per_tenant_concurrency: int = 1,
    ):
        self.repository = repository
        self.handlers = handlers
        self.worker_id = str(worker_id).strip()
        self.poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self.lease_seconds = max(1, int(lease_seconds))
        self.heartbeat_seconds = max(0.001, float(heartbeat_seconds))
        self._global = asyncio.Semaphore(max(1, int(global_concurrency)))
        self._tenant_limit = max(1, int(per_tenant_concurrency))
        self._tenants: Dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self._tenant_limit)
        )
        self._wake = asyncio.Event()
        self._stopping = asyncio.Event()
        self._runner: Optional[asyncio.Task] = None
        self._listener_conn: Any = None

    def notify(self) -> None:
        self._wake.set()

    async def wait_for_work(self) -> None:
        try:
            await asyncio.wait_for(
                self._wake.wait(), timeout=self.poll_interval_seconds
            )
        except asyncio.TimeoutError:
            pass
        finally:
            self._wake.clear()

    async def _heartbeat(self, job: AgentJob) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            alive = await self.repository.heartbeat(
                user_id=job.user_id,
                job_id=job.job_id,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if not alive:
                logger.warning("Lease heartbeat rejected for job %s", job.job_id)
                return

    async def execute(self, job: AgentJob) -> None:
        handler = self.handlers.get(job.job_type)
        if handler is None:
            await self.repository.retry(
                user_id=job.user_id,
                job_id=job.job_id,
                worker_id=self.worker_id,
                error=f"No handler registered for {job.job_type.value}",
            )
            return
        async with self._global:
            async with self._tenants[job.user_id]:
                heartbeat = asyncio.create_task(self._heartbeat(job))
                try:
                    await handler(job)
                    await self.repository.succeed(
                        user_id=job.user_id,
                        job_id=job.job_id,
                        worker_id=self.worker_id,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self.repository.retry(
                        user_id=job.user_id,
                        job_id=job.job_id,
                        worker_id=self.worker_id,
                        error=str(exc),
                    )
                finally:
                    heartbeat.cancel()
                    try:
                        await heartbeat
                    except asyncio.CancelledError:
                        pass

    async def process_one(self) -> bool:
        job = await self.repository.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False
        await self.execute(job)
        return True

    async def _run(self) -> None:
        while not self._stopping.is_set():
            processed = await self.process_one()
            if not processed:
                await self.wait_for_work()

    async def _start_listener(self) -> None:
        dsn = database_dsn()
        if not dsn:
            return
        import asyncpg

        self._listener_conn = await asyncpg.connect(dsn)

        def on_notification(*_args):
            self.notify()

        await self._listener_conn.add_listener("aethria_agent_jobs", on_notification)

    async def start(self) -> None:
        self._stopping.clear()
        await self._start_listener()
        self._runner = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        self.notify()
        if self._runner:
            await self._runner
            self._runner = None
        if self._listener_conn is not None:
            await self._listener_conn.close()
            self._listener_conn = None
