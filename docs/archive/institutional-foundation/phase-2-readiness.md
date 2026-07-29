# Phase 2 canonical identity readiness

Date: 2026-07-15

## Outcome

The code-level canonical identity foundation is implemented. It is deliberately **not production-ready in this local workspace** because no `DATABASE_URL`, `SUPABASE_DB_URL`, or `TEST_DATABASE_URL` is configured, so the migrations, transactional races, tenant backfill, and reconciliation cannot be certified against the target PostgreSQL instance.

This phase changes the system of record. `companies`, `source_observations`, `company_identifiers`, `opportunities`, and `identity_resolution_cases` are authoritative. `startups` remains a compatibility projection for the current frontend and downstream reviewer/partner code during the strangler migration.

## Implemented behavior

- Domain and verified provider identifiers are identity keys; normalized company names are never identity keys.
- Manual lookup, autonomous discovery, and backfill use the same `IdentityService` and transactional repository.
- Every source touch remains a tenant-scoped observation with its channel, while verified cross-channel matches converge on one company and one opportunity context.
- Multiple strong candidates and insufficient verification create explicit identity cases and block evaluation.
- Company, identifier, alias, observation resolution, opportunity, and outbox mutations commit atomically.
- Verified identifier races fail closed and cannot silently move an identifier to another company.
- Autonomous discoveries are admitted only after the mandatory reference prune. An ambiguous legacy projection is removed before Reviewer can consume it.
- Manual lookup jobs checkpoint institutional IDs and become `blocked` with `identity_review_required` rather than retrying an operator decision.
- Operator rulings support match, create/converge, defer, and reject. Actor identity comes from the authenticated request, not the request body.
- Legacy backfill is tenant-required, dry-run by default, bounded, cursor-restartable, and idempotent. Names alone never cause merges.
- Reconciliation emits counts only and fails on duplicate verified identifiers, tenant drift, or authoritative legacy-only rows created after activation.
- Golden set v2 runs all nine v1 decision cases plus eight Phase 2 identity cases.

## Migration order

Apply the complete Phase 0–2 chain in order:

1. `20260714192632_agent_job_schedules.sql`
2. `20260714192642_startups_normalized_name_unique.sql` after resolving preflight duplicates
3. `20260714192902_optimize_agent_job_schedule_rls.sql`
4. `20260715193000_durable_agent_jobs.sql`
5. `20260715210000_canonical_identity.sql`
6. `20260715220000_agent_job_block_details.sql`

Do not activate identity admission before steps 4–6 are present. Identity transactions publish to the Phase 1 outbox, and blocked execution depends on the structured job columns.

## Tenant rollout gate

Configure a direct PostgreSQL DSN and run the code gate:

```bash
cd backend
python3 scripts/run_golden_set.py --version v2 --json
python3 scripts/check_phase2_readiness.py --user-id=<clerk_user_id> --json
```

Run a full dry-run backfill until `complete=true`, carrying `next_cursor` forward:

```bash
python3 scripts/backfill_canonical_identity.py \
  --user-id=<clerk_user_id> --batch-size=100
python3 scripts/backfill_canonical_identity.py \
  --user-id=<clerk_user_id> --batch-size=100 --after=<next_cursor>
```

Review `would_require_identity_review` before applying. This is expected for name-only or weakly resolved legacy rows; it is not a reason to weaken matching.

Apply the same bounded sequence only after the dry-run counts are accepted:

```bash
python3 scripts/backfill_canonical_identity.py \
  --user-id=<clerk_user_id> --batch-size=100 --apply
```

Then reconcile with an activation timestamp:

```bash
python3 scripts/check_identity_reconciliation.py \
  --user-id=<clerk_user_id> \
  --activated-at=2026-07-15T00:00:00Z
```

The command must exit zero. Open cases and unlinked historical projections are operational counts; duplicate verified identifiers, tenant drift, and post-activation authoritative legacy-only rows are hard violations.

## Operational ownership

Before activation, assign one named operator for the identity queue. Their responsibilities are:

1. Review open cases by oldest/highest-impact opportunity.
2. Match only when evidence supports an existing canonical company.
3. Create only with an operator-confirmed canonical domain.
4. Defer when evidence can reasonably arrive later; reject when the observation is invalid.
5. Retry the blocked durable job after resolving its case.
6. Review reconciliation counts daily during rollout and weekly after stabilization.

No job, Meta proposal, or identity heuristic can self-approve an ambiguous match.

## Current local evidence

- Phase 2 golden set: 17 passed, 0 failed.
- Identity/job focused suite: passes; PostgreSQL-gated tests skip without `TEST_DATABASE_URL`.
- Direct database readiness: blocked by missing DSN.
- Target migration presence, RLS behavior, unique-index races, backfill counts, and reconciliation: not certified locally.

## Rollout and rollback

Rollout one tenant first. Apply migrations, run the entire dry run, resolve the initial case backlog, apply the backfill, enable durable identity admission, and observe blocked jobs/outbox/reconciliation before adding tenants.

Rollback stops new accepted work and identity admission but does not drop or rewrite canonical tables. Retain observations, cases, jobs, and outbox records as the recovery/audit trail. The current frontend can continue reading `startups`, but any legacy rows created during rollback must be reconciled before Phase 2 is re-enabled.
