# Frontend impact ledger — institutional foundation (Phases 0–2)

Date: 2026-07-15

This ledger identifies frontend work created by the Phase 0–2 backend contracts. No frontend source was changed in the backend implementation stream. The existing UI can still submit work and read the legacy startup projection, but it does not yet present durable execution, canonical identity, source provenance, or operator resolution correctly.

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

For blocked jobs, also type `block_code` and `recovery_action`. `block_detail` is intentionally not exposed. Route `identity_review_required` to the identity case workflow; do not present it as an infrastructure failure.

### Create `app-front-end/src/api/identity.ts`

Add typed functions for:

- `GET /api/companies/{company_id}`;
- `GET /api/opportunities/{opportunity_id}`;
- `GET /api/observations?status=...&limit=...`;
- `GET /api/identity-cases?status=...&limit=...`;
- `POST /api/identity-cases/{identity_case_id}/resolve` with `match | create | defer | reject`;
- the dedicated `/defer` and `/reject` aliases if the UI uses one-action forms.

Create exact DTOs for `Company`, `Opportunity`, `SourceObservation`, `IdentityCandidate`, `IdentityResolutionCase`, and `IdentityAdmission`. Do not add client-supplied `user_id` or `resolved_by`; both come from Clerk authentication. Do not expect raw provider metadata or private source payloads from list endpoints.

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

When `block_code === 'identity_review_required'`, show “Identity review required” and open the matching case in the resolution drawer. Keep Retry disabled until the case is resolved; after resolution, retry the same durable job rather than submitting a second lookup.

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

Add bounded queries for open identity cases and, on selected opportunity detail, its company/source observations. Do not fetch every observation globally on the primary deal-flow render.

### `app-front-end/src/components/SystemIntelligence.tsx`

Pass execution-plane health into the relevant tab. The best current placement is Calibration or Evolution for readiness and a compact execution block, not a new top-level navigation tab.

Add an “Identity review” work queue with open-case count and oldest-case age. This is operational work, not Meta intelligence, so keep it distinct from proposal/calibration language.

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

## 4. Canonical deal-flow and identity resolution

### `app-front-end/src/components/WorkGrid.tsx`

Move the card identity key from legacy `startup_id` toward `opportunity_id`. During transition, retain `legacy_startup_id` only as a compatibility navigation key. One canonical opportunity should render once even when inbound, outbound, referral, event, and Scout observations all exist.

Show a compact source-channel summary such as “3 sources · referral + outbound + Scout.” Do not flatten those observations into duplicate cards.

### Create `app-front-end/src/components/identity/IdentityReviewQueue.tsx`

Render open cases with observed company name/domain, reason code, candidate count, confidence, source channel, age, and linked blocked job when available. Provide explicit Open/Defer/Reject actions. Never auto-select the first candidate.

### Create `app-front-end/src/components/identity/IdentityResolutionDrawer.tsx`

This is the decision surface for match/create/defer/reject:

- compare candidates by canonical name, domain, confidence, and evidence URLs;
- “Match existing” submits the selected company ID;
- “Create company” requires a canonical name and operator-confirmed domain;
- “Defer” and “Reject” require deliberate confirmation and allow a note;
- after success, invalidate identity cases, company, opportunity, jobs, and deal-flow queries;
- if the case was linked from Dispatch, offer “Retry lookup” using the original job ID.

### Create `app-front-end/src/components/identity/CompanyIdentityPanel.tsx`

On company/opportunity detail, show canonical domain, identity confidence, opportunity state, compatibility linkage, and current evaluation/recommendation/ruling IDs when present. Keep this factual and auditable; do not add unsupported personality labels.

### Create `app-front-end/src/components/identity/SourceObservationsPanel.tsx`

Show the preserved channel timeline—manual lookup, autonomous discovery, inbound, outbound, referral, event, portfolio introduction, import, or backfill—with observed name/domain and resolution state. The API intentionally omits raw private metadata; the component should not assume it exists.

### `app-front-end/src/App.tsx` and routing

Add a stable route/query parameter for opening an identity case from Dispatch or System Intelligence. Preserve the selected case through authentication and drawer close/reopen. Do not create a second company lookup merely to navigate to a case.

## 5. Memo and trace surfaces — follow-on once exposed

The backend records evaluation manifests, but the current frontend does not yet have a dedicated manifest/readiness API. Once exposed, update:

- `app-front-end/src/components/InvestmentMemoContent.tsx`;
- `app-front-end/src/components/memo/MemoEvidenceLedger.tsx`;
- `app-front-end/src/components/memo/MemoRulingSection.tsx`;
- `app-front-end/src/types/startup.ts`.

Show model/prompt/policy/rubric/rules versions as an audit disclosure. Do not crowd the primary recommendation; use a collapsible “Evaluation dependencies” section.

## Recommended frontend implementation order

1. API types: `api/jobs.ts`, `api/identity.ts`, and startup/agent response updates.
2. Dispatch persistence and `useDispatchLookup` authoritative job polling.
3. `DispatchCommandBar` blocked/retry controls and identity-case deep link.
4. `IdentityReviewQueue` and `IdentityResolutionDrawer` with mutation/query tests.
5. `WorkGrid` canonical opportunity keying and source-channel summary.
6. Company identity and source-observation detail panels.
7. Settings system-state block.
8. System Intelligence Meta proposal language, identity queue, and execution health.
9. Live feed wording.
10. Memo manifest disclosure after the backend exposes a stable presentation DTO.

This order first fixes correctness and recovery, then governance language, then deeper audit presentation.
