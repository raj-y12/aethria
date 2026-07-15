# Phase 0–1 Institutional Foundation Implementation Plan

> **Required sub-skill:** Use `superpowers:executing-plans` to implement this plan task by task. Use `superpowers:test-driven-development` for each behaviour change and `superpowers:verification-before-completion` before declaring the phase complete.

**Goal:** Make Aethria's current evaluation path institutionally traceable and safe, then replace process-local accepted-work queues with a transactional PostgreSQL job system without regressing the interactive lookup path.

**Architecture:** Phase 0 adds analysis-only Meta behaviour, explicit decision-code boundaries, an executable current-pipeline golden set, manifests, and cost/latency baselines. Phase 1 adds a direct-PostgreSQL `AgentJob` repository, worker, checkpoints, leases, outbox, and API integration. A lookup is one durable parent job and one continuous in-process stage chain; checkpoints are writes for recovery and observability, not inputs to the next stage. Existing `startups` rows remain authoritative during these phases.

**Tech stack:** Python 3, FastAPI, Pydantic v2, asyncpg, PostgreSQL/Supabase Postgres, Prometheus, pytest, existing Supabase service-role storage, existing React/TypeScript frontend contracts.

**Scope boundary:** This plan implements only the approved master design's preflight, Phase 0, and Phase 1. Canonical identity, the claim ledger, immutable evaluation records, rulings/actions, attention enrichment, Fund Intelligence, and channel expansion each require their own follow-on implementation plan and migration gate.

---

## Invariants and rollout rules

- Every durable job and checkpoint carries an explicit `user_id`; no repository method infers a tenant.
- The direct job repository requires `DATABASE_URL` or `SUPABASE_DB_URL`. When `USE_SUPABASE_STORAGE=1`, missing direct PostgreSQL configuration makes accepted-work endpoints fail closed with `503`; it never silently falls back to an in-memory production queue.
- With `USE_SUPABASE_STORAGE=0`, existing process-local queues remain available only as the development/test fallback because the product pipeline is already disabled without Supabase.
- Existing `startups` storage remains the current business-data authority in Phase 0–1.
- A job checkpoint never becomes the handoff mechanism between lookup stages. The typed `Startup` object returned/refreshed by the current stage is passed directly to the next engine.
- Job claim, lease, heartbeat, terminal transition, and outbox insert use direct PostgreSQL transactions.
- Meta may propose prompts, weights, or thresholds; none may self-activate. Prompt promotion remains an explicit existing operator action.
- Legacy `INVEST/PASS/MONITOR` and `YES/NO/MAYBE` remain supported at compatibility boundaries. Institutional recommendation and ruling values are separate.
- Existing user changes in frontend settings tests and untracked review documents are out of scope and must not be staged.

## Preflight — verify the remediated current product

### Task 1: Re-run the audit-remediation regression set

**Files:**
- Read: `backend/tests/test_lookup_rerun.py`
- Read: `backend/tests/test_company_resolver.py`
- Read: `backend/tests/test_portfolio_layer.py`
- Read: `supabase/migrations/20260714192632_agent_job_schedules.sql`
- Read: `supabase/migrations/20260714192642_startups_normalized_name_unique.sql`
- Read: `supabase/migrations/20260714192902_*.sql`

**Step 1: Run focused tests before changing code**

Run:

```bash
cd backend && pytest -q \
  tests/test_lookup_rerun.py \
  tests/test_company_resolver.py \
  tests/test_portfolio_layer.py \
  tests/test_job_schedule.py
```

Expected: all current regression tests pass (known optional integration tests may skip).

**Step 2: Record the preflight result**

Create `docs/institutional-foundation/preflight.md` with:

- exact test command and result;
- ordered migration filenames from `20260714192632` through `20260714192902`;
- normalized-name duplicate preflight command copied from the existing migration/remediation notes;
- statement that migration application is an environment deployment step, not something unit tests can prove;
- Dispatch compatibility path verified by the existing duplicate/rerun tests.

**Step 3: Commit the evidence-only preflight**

```bash
git add docs/institutional-foundation/preflight.md
git commit -m "docs: record institutional foundation preflight"
```

---

## Phase 0 — institutional guardrails

### Task 2: Formalize recommendation and human-ruling semantics

**Files:**
- Modify: `backend/utils/partner_codes.py`
- Test: `backend/tests/test_decision_codes.py`

**Step 1: Write failing mapping tests**

Cover these exact mappings:

| Boundary | Input | Output |
|---|---|---|
| legacy partner recommendation → institutional recommendation | `INVEST` | `ADVANCE` |
| legacy partner recommendation → institutional recommendation | `MONITOR` | `MONITOR` |
| legacy partner recommendation → institutional recommendation | `PASS` | `PASS` |
| institutional recommendation → legacy partner recommendation | `ADVANCE` | `MONITOR` |
| institutional recommendation → legacy partner recommendation | `INSUFFICIENT_EVIDENCE` | `MONITOR` |
| legacy human ruling → institutional human ruling | `YES` | `INVEST` |
| legacy human ruling → institutional human ruling | `MAYBE` | `MONITOR` |
| legacy human ruling → institutional human ruling | `NO` | `PASS` |
| institutional human ruling → legacy human ruling | `ADVANCE` | `MAYBE` |
| institutional human ruling → legacy human ruling | `INVEST` | `YES` |

Also assert that projecting institutional `ADVANCE` returns compatibility metadata `{"compatibility_reason": "advance"}` and can never become legacy `YES`.

Run:

```bash
cd backend && pytest -q tests/test_decision_codes.py
```

Expected: fail because institutional enums and adapters do not exist.

**Step 2: Implement the single adapter**

Extend `backend/utils/partner_codes.py` with:

```python
class RecommendationCode(str, Enum):
    ADVANCE = "ADVANCE"
    MONITOR = "MONITOR"
    PASS = "PASS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class HumanRulingCode(str, Enum):
    ADVANCE = "ADVANCE"
    MONITOR = "MONITOR"
    PASS = "PASS"
    INVEST = "INVEST"


class LegacyProjection(BaseModel):
    value: str
    compatibility_reason: str | None = None
```

Add explicit functions:

- `institutional_recommendation_from_legacy_partner()`
- `legacy_partner_from_institutional_recommendation()`
- `institutional_ruling_from_legacy()`
- `legacy_ruling_from_institutional()`

Retain the existing `recommendation_from_legacy`, `legacy_from_recommendation`, and `normalize_recommendation` signatures unchanged for current callers.

**Step 3: Re-run mapping and existing decision tests**

```bash
cd backend && pytest -q tests/test_decision_codes.py tests/test_partner_decision.py tests/test_decision_endpoints.py
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/utils/partner_codes.py backend/tests/test_decision_codes.py
git commit -m "feat: formalize recommendation and ruling codes"
```

### Task 3: Make every Meta mutation proposal-only

**Files:**
- Modify: `backend/meta/agent.py`
- Modify: `backend/meta/mutator.py`
- Modify: `backend/meta/schema.py`
- Test: `backend/tests/test_meta_prompt_gating.py`
- Test: `backend/tests/test_meta_analysis_only.py`
- Verify: `backend/tests/test_job_schedule.py`

**Step 1: Replace the prompt auto-apply test with a failing fail-closed test**

Change the environment-true test so it asserts `_set_agent_prompt` is not called even when `META_AGENT_PROMPT_AUTO_APPLY=true`. Assert the returned proposal includes:

```python
{
    "type": "prompt_proposal",
    "promoted": False,
    "activation_status": "pending_operator_promotion",
}
```

Add tests that patch `ScoutReweighter.apply` and `ThresholdCalibrator.apply` and assert `MetaAgent._run_cycle_sync()` never calls them while still including their `decide()` outputs in the report.

Run:

```bash
cd backend && pytest -q tests/test_meta_prompt_gating.py tests/test_meta_analysis_only.py
```

Expected: fail on current auto-apply and `apply()` calls.

**Step 2: Enforce analysis-only behaviour**

- Make `PromptMutator` ignore the environment/settings auto-apply switch and always save a pending proposal.
- Keep the current explicit promotion path untouched.
- Remove `reweighter.apply(weight_updates)` and `calibrator.apply(calibrations)` calls from the automatic Meta cycle.
- Add `activation_status` to proposal schemas.
- Rename/report fields without breaking current readers:
  - `prompt_proposals`: pending prompt proposals;
  - `weight_proposals`: proposed weight changes;
  - `calibration_proposals`: proposed threshold changes;
  - keep `weight_updates` and `calibration_changes` as compatibility aliases containing the same proposal values;
  - `mutations_applied` must be an empty list for an automatic cycle.
- Add top-level `analysis_only: True` and `production_mutations_applied: 0`.

**Step 3: Verify schedule and mutation gates**

```bash
cd backend && pytest -q \
  tests/test_meta_prompt_gating.py \
  tests/test_meta_analysis_only.py \
  tests/test_job_schedule.py
```

Expected: pass; daily schedule claim remains the execution gate and production mutation count is zero.

**Step 4: Commit**

```bash
git add backend/meta/agent.py backend/meta/mutator.py backend/meta/schema.py \
  backend/tests/test_meta_prompt_gating.py backend/tests/test_meta_analysis_only.py
git commit -m "feat: make meta optimization analysis only"
```

### Task 4: Record complete current-pipeline evaluation manifests

**Files:**
- Create: `backend/evaluation/__init__.py`
- Create: `backend/evaluation/manifest.py`
- Modify: `backend/models.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/supabase_storage.py`
- Test: `backend/tests/test_evaluation_manifest.py`

**Step 1: Write failing manifest tests**

Define a Pydantic `EvaluationManifest` contract with:

```python
manifest_version: Literal["evaluation-manifest-v1"]
pipeline_run_id: str
evaluation_path: Literal["manual_lookup", "autonomous_discovery", "rerun"]
models: dict[str, str]
prompt_versions: dict[str, str]
policy_version_id: str | None
policy_hash: str | None
partner_rules_version: str
partner_rules_hash: str
created_at: datetime
```

Tests must assert:

- model names come from the instantiated engines/env;
- prompt versions are copied from ScoutInfo, each SingleReview, and PartnerInfo;
- policy metadata comes from structured scoring/policy resolver;
- partner rules use the versioned JSON file and a stable SHA-256 hash;
- missing optional prompt entries are represented explicitly as `"unknown"`, never omitted;
- `user_id` is not placed inside the portable manifest payload;
- serialization round-trips through Pydantic.

**Step 2: Implement manifest builder and storage helper**

- Add `EvaluationManifest` to `backend/models.py` as the source-of-truth data shape.
- Implement pure builder/hash helpers in `backend/evaluation/manifest.py`.
- Extend `_PipelineEngines` with the shared `cost_controller` and model metadata.
- Add `SupabaseStartupsStorage.record_evaluation_manifest(startup_id, manifest)` that merges `agent_trace["evaluation_manifest"]` through the existing partial-update/trace path and never overwrites other trace stages.
- After successful partner completion in a lookup, build and persist the manifest. For autonomous cycles, persist a manifest for each row newly partnered in that run using pipeline-run attribution.

**Step 3: Run tests**

```bash
cd backend && pytest -q tests/test_evaluation_manifest.py tests/test_agent_trace.py tests/test_supabase_storage.py
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/evaluation backend/models.py backend/pipeline_runner.py \
  backend/supabase_storage.py backend/tests/test_evaluation_manifest.py
git commit -m "feat: record evaluation manifests"
```

### Task 5: Add always-on usage measurement and cohort baselines

**Files:**
- Modify: `backend/portfolio/cost_control.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/metrics.py`
- Test: `backend/tests/test_cost_control.py`
- Test: `backend/tests/test_pipeline_cost_metrics.py`

**Step 1: Write failing tests**

Test that:

- `CostController(enforce_limits=False)` records calls/tokens/cost but never blocks for limit/cooldown reasons;
- `CostController(enforce_limits=True)` preserves current gates;
- `snapshot_usage()` returns total calls, tokens, and cost across agent types;
- lookup computes a before/after delta and records cohort `manual_lookup`;
- a periodic cycle records cohort `autonomous_discovery`;
- Prometheus labels contain cohort/stage/model/provider categories but never tenant IDs, startup IDs, or job IDs.

**Step 2: Implement measurement**

- Add `enforce_limits: bool = True` to `CostController`.
- Make `_build_pipeline_engines()` always instantiate one controller, passing the user setting as `enforce_limits`.
- Add `snapshot_usage()` and a pure non-negative delta helper.
- Add bounded-cardinality histograms/counters:
  - `aethria_decision_ready_cost_usd{cohort}`;
  - `aethria_decision_ready_tokens{cohort}`;
  - `aethria_evaluation_manifest_total{path,outcome}`.
- Observe a cost baseline only when an opportunity reaches a partner decision; incomplete work records usage but does not enter the decision-ready denominator.

**Step 3: Verify**

```bash
cd backend && pytest -q tests/test_cost_control.py tests/test_pipeline_cost_metrics.py tests/test_metrics.py
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/portfolio/cost_control.py backend/pipeline_runner.py backend/metrics.py \
  backend/tests/test_cost_control.py backend/tests/test_pipeline_cost_metrics.py
git commit -m "feat: measure evaluation cost baselines"
```

### Task 6: Create and execute golden evaluation set v1

**Files:**
- Create: `resources/evaluation/golden_set/v1.json`
- Create: `backend/evaluation/golden_set.py`
- Create: `backend/scripts/run_golden_set.py`
- Test: `backend/tests/test_golden_set_v1.py`
- Create: `docs/institutional-foundation/golden-set-v1.md`

**Step 1: Write the failing harness tests**

The v1 fixture must contain redacted/synthetic snapshots for:

- strong fit/strong references;
- strong company outside mandate;
- weak company with polished narrative;
- sparse pre-seed evidence;
- conflicting founder/traction assertions represented in current fields;
- ambiguous resolver output;
- unsupported founder narrative;
- hard pass with human review;
- repeated unchanged snapshot.

For each case pin only current-pipeline invariants:

- resolver outcome;
- external reference validity state;
- dimension scores;
- legacy partner recommendation;
- partner confidence bounds or exact fixture value;
- `human_review_required`;
- evaluation-manifest completeness.

The harness performs no network or LLM calls. It validates frozen current-pipeline snapshots and returns a machine-readable result with corpus version and pass/fail counts.

**Step 2: Implement CLI and fixtures**

The CLI entrypoint accepts:

```bash
python scripts/run_golden_set.py --version v1 --json
```

and exits non-zero on invariant failure.

**Step 3: Execute and document**

```bash
cd backend && pytest -q tests/test_golden_set_v1.py
cd backend && python scripts/run_golden_set.py --version v1 --json
```

Document the corpus version, limits, exact run command, and current result in `docs/institutional-foundation/golden-set-v1.md`.

**Step 4: Run the Phase 0 regression gate**

```bash
cd backend && pytest -q \
  tests/test_decision_codes.py \
  tests/test_meta_prompt_gating.py \
  tests/test_meta_analysis_only.py \
  tests/test_job_schedule.py \
  tests/test_evaluation_manifest.py \
  tests/test_cost_control.py \
  tests/test_pipeline_cost_metrics.py \
  tests/test_golden_set_v1.py
```

Expected: pass.

**Step 5: Commit**

```bash
git add resources/evaluation/golden_set/v1.json backend/evaluation/golden_set.py \
  backend/scripts/run_golden_set.py backend/tests/test_golden_set_v1.py \
  docs/institutional-foundation/golden-set-v1.md
git commit -m "test: add current pipeline golden set v1"
```

---

## Phase 1 — durable execution foundation

### Task 7: Define AgentJob, checkpoint, and outbox contracts

**Files:**
- Create: `backend/jobs/__init__.py`
- Create: `backend/jobs/models.py`
- Test: `backend/tests/jobs/test_job_models.py`

**Step 1: Write failing Pydantic contract tests**

Create and validate:

- `JobType`: `pipeline_cycle`, `company_lookup`;
- `JobStatus`: `queued`, `running`, `retry_wait`, `blocked`, `succeeded`, `failed`, `dead_letter`, `cancelled`;
- `CheckpointStatus`: `started`, `succeeded`, `failed`, `cancelled`;
- `PipelineCyclePayload` with explicit `user_id`, `manual_one_shot`, and source;
- `CompanyLookupPayload` with the current lookup inputs plus serialized resolver result;
- `AgentJob` with idempotency key, priority, attempts, max attempts, lease owner/expiry, next attempt, timestamps, pipeline run ID, and last error;
- `JobCheckpoint` with job/user/pipeline/stage/attempt/status/output metadata;
- `DomainOutboxEvent` with aggregate/event IDs, type/version, payload, publication attempts, and timestamps.

Reject blank tenant IDs and payload tenant/job tenant mismatches.

**Step 2: Implement contracts**

Use `require_user_id()` validators/construction helpers and JSON-safe payloads. Resolver objects must serialize to dictionaries before enqueue.

**Step 3: Verify and commit**

```bash
cd backend && pytest -q tests/jobs/test_job_models.py
git add backend/jobs backend/tests/jobs/test_job_models.py
git commit -m "feat: define durable job contracts"
```

### Task 8: Add the transactional PostgreSQL schema

**Files:**
- Create: `supabase/migrations/20260715193000_durable_agent_jobs.sql`
- Test: `backend/tests/jobs/test_job_migration.py`

**Step 1: Write failing SQL contract tests**

Assert the migration contains:

- `agent_jobs`, `agent_job_checkpoints`, and `domain_outbox` tables;
- tenant foreign-key/index columns and no nullable `user_id`;
- unique `(user_id, idempotency_key)` for active/accepted job identity;
- constrained status/job type values;
- lease expiry, heartbeat, retry time, attempts/max attempts;
- checkpoint uniqueness for idempotent stage publication;
- outbox unique `event_id` and unpublished index;
- `updated_at` handling;
- RLS enabled and service-role policies/grants;
- no mutation of an existing migration.

**Step 2: Implement migration**

Use UUID keys and `jsonb` payloads. Add indexes matching claim order:

```sql
(status, next_attempt_at, priority desc, created_at)
```

and recovery:

```sql
(status, lease_expires_at)
```

Use partial unique indexes where terminal jobs must permit a later explicit re-run with a new idempotency key. `NOTIFY` is emitted by repository code inside the enqueue transaction, not by an unbounded trigger.

**Step 3: Verify**

```bash
cd backend && pytest -q tests/jobs/test_job_migration.py
```

If `TEST_DATABASE_URL` is available, apply the new migration to a disposable database and roll it back by dropping the disposable database, never by editing the migration.

**Step 4: Commit**

```bash
git add supabase/migrations/20260715193000_durable_agent_jobs.sql \
  backend/tests/jobs/test_job_migration.py
git commit -m "feat: add durable job schema"
```

### Task 9: Implement the direct asyncpg job repository

**Files:**
- Create: `backend/jobs/repository.py`
- Create: `backend/jobs/postgres.py`
- Test: `backend/tests/jobs/test_job_repository_unit.py`
- Test: `backend/tests/jobs/test_job_repository_postgres.py`

**Step 1: Write failing repository tests**

Unit tests with an asyncpg-style fake and optional real-PostgreSQL tests must cover:

- `create_pool()` uses `DATABASE_URL`, then `SUPABASE_DB_URL`, with bounded min/max sizes and command timeout;
- no DSN raises `DurableJobConfigurationError`;
- enqueue is tenant-scoped and idempotent;
- enqueue writes job + outbox event in one transaction and calls `pg_notify('aethria_agent_jobs', job_id)` before commit;
- claim uses one transaction and `SELECT ... FOR UPDATE SKIP LOCKED`;
- claim recovers expired `running` leases and increments attempts once;
- heartbeat succeeds only for current lease owner and running status;
- checkpoint upsert is idempotent and tenant/job scoped;
- `succeed()` writes terminal status and completion outbox exactly once;
- retry applies bounded exponential backoff and clears lease;
- exceeding max attempts becomes `dead_letter`;
- cancel is idempotent;
- two concurrent claimers cannot both receive one job;
- one expired lease can be recovered, but stale worker completion is rejected.

**Step 2: Implement repository**

Expose methods:

```python
enqueue(...)
claim_next(...)
heartbeat(...)
write_checkpoint(...)
retry(...)
succeed(...)
fail(...)
cancel(...)
get_job(...)
queue_depths(...)
claim_outbox_batch(...)
mark_outbox_published(...)
```

All methods take explicit `user_id` where they target one tenant. Global worker claims return the stored tenant rather than receiving an inferred tenant.

**Step 3: Run unit and integration tests**

```bash
cd backend && pytest -q tests/jobs/test_job_repository_unit.py
cd backend && pytest -q tests/jobs/test_job_repository_postgres.py
```

The PostgreSQL suite skips with an explicit reason only when `TEST_DATABASE_URL` is absent. In CI/deployment verification it is required.

**Step 4: Commit**

```bash
git add backend/jobs/repository.py backend/jobs/postgres.py \
  backend/tests/jobs/test_job_repository_unit.py \
  backend/tests/jobs/test_job_repository_postgres.py
git commit -m "feat: add transactional job repository"
```

### Task 10: Implement worker, wake-up, leases, and outbox publication

**Files:**
- Create: `backend/jobs/worker.py`
- Create: `backend/jobs/outbox.py`
- Modify: `backend/metrics.py`
- Test: `backend/tests/jobs/test_job_worker.py`
- Test: `backend/tests/jobs/test_outbox_publisher.py`

**Step 1: Write failing worker tests**

Cover:

- listener wake-up plus timed polling backstop;
- one job claim wait per parent job;
- heartbeat task starts during handler execution and stops on terminal transition;
- handler exception schedules retry/dead letter;
- cancellation is observed between checkpoints;
- graceful shutdown stops claiming but lets a bounded in-flight job checkpoint before lease expiry;
- global and per-tenant concurrency limits are both enforced;
- outbox publisher publishes current domain events through `event_bus.publish` and marks them published only afterward;
- publish failure leaves event retryable.

**Step 2: Implement services**

- `DurableJobWorker` owns a bounded handler semaphore and per-tenant semaphore registry.
- A dedicated asyncpg listener connection listens on `aethria_agent_jobs`.
- `poll_interval_seconds` defaults to 2 seconds and is only a recovery backstop.
- Lease duration and heartbeat interval come from validated env settings.
- `OutboxPublisher` claims unpublished events with `SKIP LOCKED` and delegates to the existing event bus.

**Step 3: Add bounded metrics**

Add:

- jobs accepted/claimed/completed/retried/dead-lettered by job type;
- job wait and run histograms by job type/outcome;
- heartbeat failures;
- outbox backlog/publish outcomes;
- queue depth snapshots by job type/status.

No tenant/job labels.

**Step 4: Verify and commit**

```bash
cd backend && pytest -q tests/jobs/test_job_worker.py tests/jobs/test_outbox_publisher.py tests/test_metrics.py
git add backend/jobs/worker.py backend/jobs/outbox.py backend/metrics.py \
  backend/tests/jobs/test_job_worker.py backend/tests/jobs/test_outbox_publisher.py
git commit -m "feat: run durable jobs with leases and outbox"
```

### Task 11: Add in-memory engine handoffs and durable lookup checkpoints

**Files:**
- Modify: `backend/reviewer/engine.py`
- Modify: `backend/partner/engine.py`
- Modify: `backend/pipeline_runner.py`
- Test: `backend/tests/test_lookup_in_memory_handoff.py`
- Test: `backend/tests/test_lookup_checkpoints.py`

**Step 1: Write failing handoff tests**

Assert that:

- `ReviewerEngine.run_startup(..., startup=<Startup>)` does not call `storage.get_startup`;
- after `storage.add_review`, Reviewer returns or refreshes the typed Startup with `review_info` populated for the next stage;
- `PartnerEngine.run_startup(..., startup=<Startup>)` does not call `storage.get_startup`;
- a successful lookup makes no `asyncio.sleep` handoff retries;
- the serialized resolver result from the job payload is reused rather than resolved again;
- checkpoints are written after `accepted`, `scout`, `reviewer`, `partner`, and `completed` transitions;
- checkpoint output contains IDs/status/manifest references only, not mutable full startup records;
- checkpoint write failure fails/retries the job but a checkpoint read is never required for the next stage.

**Step 2: Extend engines compatibly**

Add optional keyword-only typed inputs and result methods while preserving boolean callers:

```python
ReviewerEngine.run_startup(..., startup: Startup | None = None) -> bool
PartnerEngine.run_startup(..., startup: Startup | None = None) -> bool
```

For the lookup handler, explicitly update the in-memory Pydantic object after each successful storage write using the already-built `ReviewInfo`/`PartnerInfo`. Do not re-read the row except the existing rerun memo path, where the final persisted row is intentionally loaded for complete memo regeneration.

**Step 3: Add a checkpoint callback to pipeline runner**

`run_on_demand_lookup()` accepts an optional async callback:

```python
checkpoint(stage: str, status: str, metadata: dict[str, Any]) -> Awaitable[None]
```

Current direct callers may omit it. The durable lookup job handler supplies it.

Remove storage-visibility sleep loops. A genuine provider/LLM retry remains inside the owning stage and is not a stage handoff retry.

**Step 4: Verify**

```bash
cd backend && pytest -q \
  tests/test_lookup_in_memory_handoff.py \
  tests/test_lookup_checkpoints.py \
  tests/test_on_demand_lookup_independent.py \
  tests/test_lookup_rerun.py
```

**Step 5: Commit**

```bash
git add backend/reviewer/engine.py backend/partner/engine.py backend/pipeline_runner.py \
  backend/tests/test_lookup_in_memory_handoff.py backend/tests/test_lookup_checkpoints.py
git commit -m "perf: keep lookup stage handoffs in memory"
```

### Task 12: Route cycle and lookup work through durable handlers

**Files:**
- Create: `backend/jobs/handlers.py`
- Modify: `backend/api.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/env_config.py`
- Test: `backend/tests/jobs/test_job_handlers.py`
- Test: `backend/tests/test_lookup_dispatch.py`
- Test: `backend/tests/test_lookup_additional_context.py`
- Test: `backend/tests/test_lookup_worker_concurrency.py`
- Test: `backend/tests/test_security_api.py`

**Step 1: Write failing handler/API tests**

Cover:

- `/api/agents/trigger` creates a durable `pipeline_cycle` job and returns `job_id`, `status=accepted`, and `accepted_at`;
- `/api/startups/lookup` creates a durable `company_lookup` job with the same current rate/security lock semantics and returns the existing `lookup_id` plus `job_id`;
- a reused resolution token is serialized into the payload before the API returns;
- persistent user loops enqueue idempotent cycle jobs instead of executing cycles directly;
- accepted work survives repository/worker recreation;
- `GET /api/system/status` reports durable queued/running/retry/dead-letter counts;
- current development tests with `USE_SUPABASE_STORAGE=0` retain the process-local queue seam;
- with `USE_SUPABASE_STORAGE=1` and no DSN, accepted-work endpoints return `503 durable_job_store_unavailable` and release security locks;
- lookup cancellation maps to durable job cancellation as well as current lookup status;
- handlers always pass `job.user_id` to pipeline functions.

**Step 2: Implement handlers**

- `pipeline_cycle` handler calls `run_one_pipeline_cycle(user_id, manual_one_shot=...)` and checkpoints the pipeline run.
- `company_lookup` handler reconstructs validated resolver data, calls `run_on_demand_lookup`, and writes stage checkpoints through the callback.
- Both handlers use the job's stable `pipeline_run_id` rather than allocating an unrelated execution ID inside the pipeline runner.

**Step 3: Integrate FastAPI lifespan**

- Create the asyncpg pool, repository, worker, and outbox publisher after schema/backplane checks.
- Start durable services when Supabase execution is enabled.
- Preserve local queues only in non-Supabase development mode.
- Shut services down gracefully before closing the pool/backplane.
- Replace queue-size health metrics with repository depth snapshots where durable jobs are active.
- Keep current response fields used by the frontend and add the new fields; do not remove current `status`, `user_id`, or `lookup_id` values.

**Step 4: Verify compatibility**

```bash
cd backend && pytest -q \
  tests/jobs/test_job_handlers.py \
  tests/test_lookup_dispatch.py \
  tests/test_lookup_additional_context.py \
  tests/test_lookup_worker_concurrency.py \
  tests/test_security_api.py \
  tests/test_on_demand_lookup_independent.py
```

**Step 5: Commit**

```bash
git add backend/jobs/handlers.py backend/api.py backend/pipeline_runner.py \
  backend/env_config.py backend/tests/jobs/test_job_handlers.py \
  backend/tests/test_lookup_dispatch.py backend/tests/test_lookup_additional_context.py \
  backend/tests/test_lookup_worker_concurrency.py backend/tests/test_security_api.py
git commit -m "feat: migrate pipeline work to durable jobs"
```

### Task 13: Add recovery/status API and operator-safe controls

**Files:**
- Create: `backend/routers/jobs.py`
- Modify: `backend/api.py`
- Test: `backend/tests/jobs/test_job_endpoints.py`

**Step 1: Write failing endpoint tests**

Add tenant-scoped endpoints:

```text
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/retry
POST /api/jobs/{job_id}/cancel
GET  /api/jobs?status=retry_wait,blocked,dead_letter&limit=...
```

Assert:

- cross-tenant access returns 404;
- only retryable terminal/blocked states can retry;
- retry creates a new attempt on the same accepted job when safe, without duplicating succeeded work;
- cancel is idempotent;
- response distinguishes `accepted`, `running`, `retry_wait`, `blocked`, `dead_letter`, and `succeeded`;
- errors expose safe operator messages, not DSNs or raw exception payloads.

**Step 2: Implement router**

Use existing Clerk auth dependency style and repository methods. Mount the router from `backend/api.py` without adding direct `fetch` concerns to the frontend yet.

**Step 3: Verify and commit**

```bash
cd backend && pytest -q tests/jobs/test_job_endpoints.py tests/test_security_api.py
git add backend/routers/jobs.py backend/api.py backend/tests/jobs/test_job_endpoints.py
git commit -m "feat: expose durable job recovery controls"
```

### Task 14: Run Phase 1 acceptance, latency, and migration verification

**Files:**
- Create: `backend/tests/jobs/test_phase1_acceptance.py`
- Create: `backend/scripts/check_phase1_readiness.py`
- Create: `docs/institutional-foundation/phase-0-1-readiness.md`
- Create: `docs/institutional-foundation/frontend-impact-ledger.md`

**Step 1: Add acceptance scenarios**

Against `TEST_DATABASE_URL`, prove:

- enqueue, destroy repository/worker, recreate, then execute accepted job;
- two workers and one job yield one authoritative success/outbox completion;
- worker death after checkpoint and lease expiry recovers;
- stale lease owner cannot publish success;
- duplicate idempotency key does not duplicate output;
- lookup records exactly one claim wait and continuous scout/reviewer/partner stage execution;
- checkpoint recovery never reads the checkpoint to populate the next engine;
- manual lookup median/p90 measurement fields exist and can be compared with the Phase 0 cohort baseline;
- all new tables isolate tenants.

**Step 2: Add readiness script**

The script checks, without exposing secrets:

- direct DB DSN configured;
- migration table contains `20260715193000`;
- existing schedule migrations are present;
- durable job tables/required indexes exist;
- golden set v1 passes;
- Meta analysis-only smoke check passes;
- queue/outbox depths and dead-letter count;
- current cost/latency histograms are registered.

**Step 3: Record frontend impact for Phase 0–1**

In `frontend-impact-ledger.md`, list backend contracts and the minimum later frontend work:

- Settings/System Intelligence: Meta `analysis_only`, proposal counts, prompt promotion gate state, manifests, golden-set/readiness status.
- Dispatch: use `accepted` separately from `running`; retain `lookup_id`; store/display `job_id`; support retry/cancel for failed/blocked jobs.
- System status: durable queued/running/retry/dead-letter/outbox state.
- Typed API work expected under `app-front-end/src/api/`, TanStack Query hooks, and affected current components, with exact filenames discovered before final handoff.

Do not modify the frontend in this phase unless a current test requires compatibility; the user requested a consolidated component list after implementation.

**Step 4: Run the complete verification set**

```bash
cd backend && pytest -q tests/jobs tests/test_decision_codes.py \
  tests/test_meta_prompt_gating.py tests/test_meta_analysis_only.py \
  tests/test_job_schedule.py tests/test_evaluation_manifest.py \
  tests/test_cost_control.py tests/test_pipeline_cost_metrics.py \
  tests/test_golden_set_v1.py tests/test_lookup_rerun.py \
  tests/test_company_resolver.py tests/test_portfolio_layer.py
cd backend && python scripts/run_golden_set.py --version v1 --json
cd backend && python scripts/check_phase1_readiness.py --json
```

Then run the broader backend suite:

```bash
cd backend && pytest -q
```

Run frontend compatibility checks without modifying the user's unrelated test edits:

```bash
cd app-front-end && npm test -- --run
cd app-front-end && npm run build
```

**Step 5: Self-review against exit criteria**

Confirm each Phase 0 and Phase 1 exit criterion from `docs/superpowers/specs/2026-07-15-evidence-decision-platform-design.md` in `phase-0-1-readiness.md`. Any item requiring a real target PostgreSQL run remains explicitly not complete until that run succeeds; do not claim completion from skipped integration tests.

**Step 6: Commit**

```bash
git add backend/tests/jobs/test_phase1_acceptance.py backend/scripts/check_phase1_readiness.py \
  docs/institutional-foundation/phase-0-1-readiness.md \
  docs/institutional-foundation/frontend-impact-ledger.md
git commit -m "test: verify institutional foundation readiness"
```

---

## Completion gate

Phase 0–1 is complete only when:

1. Meta automatic cycles apply zero production prompt/weight/threshold mutations.
2. Golden set v1 passes and records its version.
3. New completed evaluations carry complete manifest metadata.
4. Current manual-lookup and autonomous-discovery cost cohorts are measurable.
5. Accepted production work is committed to PostgreSQL before an API returns `202`.
6. Claims, leases, heartbeats, terminal transitions, and outbox work pass target-PostgreSQL tests.
7. Interactive lookup has one job claim and no storage-visibility handoff sleeps.
8. Existing cycle/lookup/rerun/security compatibility tests pass.
9. Full backend tests and frontend build pass, or unrelated pre-existing failures are documented with evidence.
10. The frontend impact ledger is exact enough to drive the next frontend implementation plan.

After this gate, write the Phase 2 canonical identity/source-observation plan. Do not mix Phase 2 tables into this migration.
