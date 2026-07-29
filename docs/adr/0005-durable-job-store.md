# ADR-0005 — A durable PostgreSQL job store for accepted work

**Status:** Accepted

## Context

The system originally accepted work onto in-process `asyncio.Queue`s. A restart —
a deploy, an OOM kill, a host recycle — silently dropped every queued and
in-flight job. The user had seen a `202`; nothing would ever run. Pipeline cycles
and lookups are minutes long and cost real money in model calls, so "accepted"
had to mean something.

## Decision

When `USE_SUPABASE_STORAGE=1` (production), work is admitted only after
PostgreSQL commits a job row.

- `agent_jobs` holds the queue. Job types: `pipeline_cycle`, `company_lookup`,
  `evidence_refresh`.
- Status is an explicit state machine: `queued → running → succeeded` with
  `retry_wait`, `blocked`, `failed`, `dead_letter`, and `cancelled` as first-class
  terminal or waiting states.
- `DurableJobWorker` (`jobs/worker.py`) claims jobs under a **lease** with a
  **fencing token**, heartbeats while running, and applies bounded per-tenant and
  global concurrency. A worker that loses its lease cannot commit a stale write.
- Blocked jobs carry a `BlockCode` — `thesis_required`, `identity_review_required`,
  `evidence_required`, and so on — so a stalled job always names its reason.
- `jobs/outbox.py` publishes domain events transactionally with the write that
  produced them.
- `GET /api/jobs`, `/{id}/retry`, `/{id}/cancel` expose recovery to the operator
  rather than requiring a database console.
- Without Supabase (local dev), the original in-process queues remain, with no
  durability. This is the only supported difference between the two modes.

## Consequences

**Good.** A `202` survives a restart. Stuck work is visible and explains itself.
Concurrency limits are enforced centrally instead of per call site. Extracting a
standalone worker process later is now mostly a deployment change, because the
handoff is already a database table.

**Cost.** Two admission paths to keep behaviourally aligned, and dev/production
diverge on durability. Job claiming adds database round-trips per unit of work.
The polling interval (`DURABLE_JOB_POLL_SECONDS`) sets a floor on pickup latency.

## Alternatives considered

- **Celery / RQ / a broker.** Another service, another failure domain, for a
  workload already sized to a single instance with a database it must have anyway.
- **Postgres `LISTEN`/`NOTIFY` as the queue.** Not durable on its own — a
  notification delivered while no one is listening is simply gone. It is used for
  the event bus (ADR-0004), where loss is acceptable, not for work admission.
