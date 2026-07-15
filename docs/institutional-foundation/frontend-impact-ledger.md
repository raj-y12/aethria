# Frontend impact ledger — institutional foundation

Date: 2026-07-15

This ledger identifies frontend work created by the Phase 0–1 backend contracts. No frontend behavior was changed in this phase; the existing UI remains compatible enough to submit work, but it does not yet present the new institutional execution and governance states correctly.

## 1. Typed API contracts — update first

### `app-front-end/src/api/startups.ts`

Update `queueOnDemandLookup()` and `queueLookupRerun()` to return and validate:

- `status: 'accepted'` as distinct from `running` or legacy local `queued`;
- `jobId` from `job_id`;
- `acceptedAt` from `accepted_at`;
- `pipelineRunId` from `pipeline_run_id`;
- existing `lookupId`, which remains the stable company-lookup correlation ID.

Do not infer that a 202 response means execution has begun. It means the job transaction committed.

### Create `app-front-end/src/api/jobs.ts`

Add typed functions for:

- `GET /api/jobs/{job_id}`;
- `GET /api/jobs?status=...&limit=...`;
- `POST /api/jobs/{job_id}/retry`;
- `POST /api/jobs/{job_id}/cancel`.

Model the public states exactly: `accepted`, `running`, `retry_wait`, `blocked`, `succeeded`, `failed`, `dead_letter`, and `cancelled`. Keep backend safe error text opaque; do not expect raw exceptions.

### `app-front-end/src/api/agents.ts`

Extend `TriggerResult` with `job_id`, `accepted_at`, `pipeline_run_id`, and optional `loop_status`. Extend `AgentsStatus` with durable readiness and count fields. The app currently ignores most trigger output in `App.tsx`; that is acceptable for login-triggered background work, but Settings should use the richer status.

### Create `app-front-end/src/api/system.ts` or extend `api/analytics.ts`

Type `GET /api/system/status`, including `durable_jobs.required`, `ready`, safe `error`, and the `job_type:status`/`outbox:pending` count map.

### `app-front-end/src/api/meta.ts` and `app-front-end/src/types/startup.ts`

Make `MetaCycleReport` explicitly represent:

- `analysis_only`;
- `production_mutations_applied`;
- `prompt_proposals`;
- `weight_proposals`;
- `calibration_proposals`;
- compatibility aliases as proposals, not applied changes.

Add the evaluation-manifest shape to the startup/trace DTO once it is exposed in the desired memo/status payload.

## 2. Dispatch state and polling — highest-priority UI behavior

### `app-front-end/src/lib/dispatchLookupPersistence.ts`

Bump the persisted snapshot version and add `jobId`, `acceptedAt`, and last known durable status to `PersistedDispatchLookup`. Continue storing `lookupId`; do not replace it with `jobId` because they serve different purposes.

### `app-front-end/src/hooks/useDispatchLookup.ts`

Store the returned durable job metadata for new lookups and reruns. Poll `GET /api/jobs/{job_id}` as the authoritative execution state while retaining the existing lookup/startup/memo polls for domain output during transition.

Required behavior:

- show “Accepted” before “Scouting”/running;
- treat `retry_wait` as an automatic recovery state, not a final failure;
- keep `blocked` and `dead_letter` visible with Retry and Cancel actions;
- call the job retry endpoint using `jobId`;
- use job cancellation when available while retaining lookup cancellation for current domain cleanup;
- restore in-flight state after refresh from the versioned local snapshot;
- stop claiming progress merely because a startup row appeared.

### `app-front-end/src/components/DispatchCommandBar.tsx`

Add durable state presentation to the progress/failure view: accepted timestamp, current state, retry countdown/state, blocked/dead-letter explanation, and explicit Retry/Cancel controls. The current three visual phases can remain for domain progress, but they need an execution-state line above them.

### `app-front-end/src/components/AgentDispatch.tsx`

Update `LookupPhase`/message formatting if this embedded/drawer surface remains active. It currently translates “queued” language and only knows Scouting/Reviewing/Deciding.

### Supporting tests

Update/add:

- `app-front-end/src/api/__tests__/startupsLookup.test.ts`;
- `app-front-end/src/components/__tests__/DispatchCommandBar.test.tsx`;
- a new `api/__tests__/jobs.test.ts`;
- hook tests for accepted → running → retry_wait/dead_letter → retry → succeeded;
- persistence migration tests for the new snapshot version.

## 3. System and Settings surfaces

### `app-front-end/src/hooks/useSystemData.ts`

Add a TanStack Query for system execution status when the System panel is open. Invalidate/refetch it on job SSE events and on foreground return. Carry the typed result through `SystemData`.

### `app-front-end/src/components/SystemIntelligence.tsx`

Pass execution-plane health into the relevant tab. The best current placement is Calibration or Evolution for readiness and a compact execution block, not a new top-level navigation tab.

### `app-front-end/src/components/system/internals.tsx`

This file needs the most important governance correction. `MetaCommandTab` currently says the correction cycle “rewrites the instrument” and calculates “what changed” from compatibility aliases. Change it to:

- label automatic output as proposals;
- show `analysis_only` visibly;
- show production mutations applied as zero unless an operator promotion endpoint actually succeeded;
- render prompt/weight/calibration proposal counts separately;
- never describe weight or calibration proposals as applied changes;
- show durable queue/retry/dead-letter/outbox health and golden-set/readiness state when the backend exposes the deployment report operationally.

### `app-front-end/src/settings/SettingsPage.tsx`

Extend the existing “System state” section with:

- durable store ready/unavailable;
- accepted/running/retry/dead-letter counts;
- outbox backlog;
- a clear block reason when the direct DSN/migration is missing.

Keep saved agent toggles separate from execution readiness. A toggle being on is not proof that work can be accepted.

### `app-front-end/src/components/LiveIntelligenceFeed.tsx`

It currently describes Meta cycles using “mutations.” Change feed copy to “proposals” for analysis-only reports and only emit an “applied” event for an explicit operator promotion. Add bounded job recovery events only if they help the analyst; do not flood the feed with heartbeats.

### `app-front-end/src/components/SystemBar.tsx`

Optional but recommended: distinguish healthy, degraded (retry/outbox backlog), and blocked (durable store unavailable) rather than deriving system health solely from current startup data.

## 4. Memo and trace surfaces — follow-on once exposed

The backend records evaluation manifests, but the current frontend does not yet have a dedicated manifest/readiness API. Once exposed, update:

- `app-front-end/src/components/InvestmentMemoContent.tsx`;
- `app-front-end/src/components/memo/MemoEvidenceLedger.tsx`;
- `app-front-end/src/components/memo/MemoRulingSection.tsx`;
- `app-front-end/src/types/startup.ts`.

Show model/prompt/policy/rubric/rules versions as an audit disclosure. Do not crowd the primary recommendation; use a collapsible “Evaluation dependencies” section.

## Recommended frontend implementation order

1. API types and `api/jobs.ts`.
2. Dispatch persistence and `useDispatchLookup` authoritative job polling.
3. `DispatchCommandBar` recovery controls and tests.
4. Settings system-state block.
5. System Intelligence Meta proposal language and execution health.
6. Live feed wording.
7. Memo manifest disclosure after the backend exposes a stable presentation DTO.

This order first fixes correctness and recovery, then governance language, then deeper audit presentation.
