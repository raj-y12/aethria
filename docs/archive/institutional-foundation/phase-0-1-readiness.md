# Phase 0–1 institutional foundation readiness

Date: 2026-07-15

## Outcome

The code-level Phase 0–1 foundation is implemented. Production activation is intentionally **not ready in this local environment** because neither `DATABASE_URL` nor `SUPABASE_DB_URL` is configured here, so the target database migration and recovery scenarios cannot be certified from this workspace.

This is a deployment gate, not an in-memory fallback condition. With `USE_SUPABASE_STORAGE=1`, Aethria now refuses to accept cycle or lookup work when the durable PostgreSQL repository is unavailable.

## Implemented controls

- Recommendation and human-ruling semantics are separate. `ADVANCE` never silently becomes a portfolio investment.
- Automatic Meta cycles are analysis-only. They can create proposals but cannot apply production prompt, weight, or calibration changes.
- Every current-pipeline decision can record an evaluation manifest with model, prompt, policy, rubric, and partner-rule dependencies.
- Cost and token measurements are recorded even when budget enforcement is disabled.
- Golden set v1 pins nine current-pipeline institutional invariants.
- Accepted pipeline and lookup work is transactional in `agent_jobs`; stage state is recorded in `agent_job_checkpoints`; domain notification uses `domain_outbox`.
- Workers use PostgreSQL leases, heartbeats, bounded retries, dead-lettering, `SKIP LOCKED`, LISTEN/NOTIFY, and a timed polling backstop.
- Expired final-attempt leases are swept to dead-letter rather than remaining permanently `running`.
- Lookup stage handoffs remain in memory while durable checkpoints record IDs and stage outcomes only.
- Supabase-mode API dispatch returns `status=accepted`, `job_id`, `accepted_at`, and `pipeline_run_id` only after the job transaction commits.
- Tenant-scoped job status, retry, and cancellation controls are available at `/api/jobs`.
- `/api/system/status`, `/api/agents/status`, and Prometheus metrics expose durable state without tenant/job labels or raw database errors.

## Required target-environment gate

Apply and verify these migrations in order:

1. `20260714192632_agent_job_schedules.sql`
2. `20260714192642_startups_normalized_name_unique.sql` after resolving duplicate groups described in `preflight.md`
3. `20260714192902_optimize_agent_job_schedule_rls.sql`
4. `20260715193000_durable_agent_jobs.sql`

Configure one direct PostgreSQL DSN:

```text
DATABASE_URL=...
# or
SUPABASE_DB_URL=...
```

Then run:

```bash
cd backend
python3 scripts/check_phase1_readiness.py --json
TEST_DATABASE_URL="$DATABASE_URL" pytest -q tests/jobs/test_phase1_acceptance.py
```

The readiness command must return `ready=true`. The database-gated acceptance test must prove repository recreation, single authoritative claim, checkpoint persistence, expired-lease recovery, stale-worker rejection, idempotent enqueue, tenant isolation, and one accepted/succeeded outbox sequence.

## Current local evidence

- Golden set v1: 9 passed, 0 failed.
- Meta analysis-only smoke: passed.
- Required institutional metrics: registered.
- Direct database readiness: blocked by missing direct DSN.
- Target PostgreSQL acceptance: skipped when `TEST_DATABASE_URL` is absent.

No database URL, service key, raw worker exception, or tenant identifier is emitted by the readiness report.

## Rollout and rollback

Rollout:

1. Apply migrations and run the normalized-name duplicate preflight.
2. Configure the direct DSN and conservative worker concurrency (`2` global, `1` per tenant by default; use `1` global on the smallest instance if needed).
3. Run the readiness and target-database acceptance gates.
4. Deploy one instance, confirm `/api/system/status` and outbox backlog, then expand capacity.
5. Update the frontend according to `frontend-impact-ledger.md` before presenting retry/dead-letter controls to users.

Rollback:

- Stop accepting new work by removing/invalidating the direct DSN or disabling the application deployment; Supabase-mode endpoints fail closed.
- Allow current leases to expire or stop workers gracefully. Accepted rows remain recoverable.
- Do not drop the durable tables during rollback. They are the audit/recovery record for already accepted work.
- Revert application traffic to the prior build only after confirming it will not accept parallel process-local production work.
