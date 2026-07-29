# Frontend impact ledger — institutional evidence-and-decision platform (Phases 0–8)

Date: 2026-07-15

This ledger identifies frontend work created by the Phase 0–8 backend contracts. No frontend source was changed in the backend implementation stream. The existing UI can still submit work and read the legacy startup projection, but it does not yet present durable execution, canonical identity, evidence/claim provenance, immutable evaluations, human rulings, approval-gated actions, monitoring budgets, Fund Intelligence, channel imports, or outcomes correctly.

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

## 5. Memo and trace surfaces

The backend now exposes the current evidence ledger, immutable evaluation/recommendation, human ruling/action, and monitoring projections. Update:

- `app-front-end/src/components/InvestmentMemoContent.tsx`;
- `app-front-end/src/components/memo/MemoEvidenceLedger.tsx`;
- `app-front-end/src/components/memo/MemoRulingSection.tsx`;
- `app-front-end/src/types/startup.ts`.

Show model/prompt/policy/rubric/rules versions as an audit disclosure. Do not crowd the primary recommendation; use a collapsible “Evaluation dependencies” section.

## 6. Evidence, evaluation, ruling, and action clients — required

### Create `app-front-end/src/api/evidence.ts`

Type and implement:

- `GET /api/opportunities/{opportunity_id}/evidence`;
- `POST /api/opportunities/{opportunity_id}/evidence-plans`;
- `POST /api/claims/{claim_id}/correct`;
- `POST /api/opportunities/{opportunity_id}/confidential-artifacts`.

Model artifacts, evidence items, claims, claim/evidence relationships, and evidence plans separately. Restricted storage references are never returned. Do not treat `founder_asserted`, `operator_asserted`, `model_inferred`, and `externally_verified` as equivalent certainty.

### Create `app-front-end/src/api/evaluations.ts`

Type and implement:

- `GET /api/opportunities/{opportunity_id}/evaluation`;
- `POST /api/opportunities/{opportunity_id}/evaluate`.

The DTO must preserve null criterion scores. `score: null` means “Not scored”; it must not be coerced to zero or five. Include evidence sufficiency, confidence, supporting/contradicting claim IDs, missing evidence, quality flags, immutable snapshot hash, policy/rubric/rules versions, and recommendation change explanation.

### Create `app-front-end/src/api/decisions.ts`

Type and implement:

- `POST /api/opportunities/{opportunity_id}/rulings`;
- `GET/POST /api/opportunities/{opportunity_id}/actions`;
- `POST /api/actions/{workflow_action_id}/approve`.

Use the canonical ruling values `advance | monitor | pass | invest`. Keep a recommendation visually and semantically separate from a human ruling. Type override reasons and action approval states exactly. Approval responses explicitly do not prove an external CRM/email write occurred.

### Create `app-front-end/src/api/monitoring.ts`

Type and implement:

- `POST /api/opportunities/{opportunity_id}/refresh`;
- `PATCH /api/opportunities/{opportunity_id}/service-level`;
- `GET /api/opportunities/{opportunity_id}/monitoring`.

Model service levels 0–5, lifecycle reason, next review, resource envelope, budget reservation, material-change result, and linked durable job. A `429` is visible budget exhaustion; a `409` is a lifecycle-policy block.

### Create `app-front-end/src/api/fundIntelligence.ts`

Type and implement:

- `POST /api/fund-intelligence/derive-overrides`;
- `GET /api/fund-intelligence/proposals` and proposal detail;
- proposal preview and review endpoints;
- the separate governed policy-version publish endpoint.

Never combine Accept and Publish in one client mutation. Acceptance produces `status: draft` and `production_policy_changed: false`. Publication is a second explicit action with its own confirmation and error recovery.

### Create `app-front-end/src/api/channelsOutcomes.ts`

Type and implement:

- `POST /api/imports/csv` and `GET /api/imports/{import_batch_id}`;
- `GET/POST /api/companies/{company_id}/outcomes`;
- `GET /api/outcomes/coverage`.

CSV intake is capped at 500 rows and 1 MB. Type row states `resolved | review_required | error`; never send or expect raw private CSV rows back. Outcome displays must retain verification, evidence artifact IDs, effective/observed dates, materiality, valence, coverage, and `causal_inference_supported: false`.

## 7. Existing component changes for the evidence-and-decision product

### `app-front-end/src/components/InvestmentMemoContent.tsx`

Replace the legacy `resolveEscalation`/optimistic partner-decision path with the human-ruling API. The primary hierarchy should be:

1. current system recommendation and confidence;
2. decisive evidence, contradictions, and missing information;
3. human ruling and rationale;
4. next actions and approvals;
5. audit dependencies and history.

Remove unsupported founder superlatives from synthesized headings. Founder sections should show observable claims such as earned insight, domain history, execution speed, customer pull, prior projects, and interview observations with attribution.

### `app-front-end/src/components/memo/MemoEvidenceLedger.tsx`

Rebuild this component around claim → evidence relationships rather than the legacy flat reference list. Show assertion class, verification state, source/trust class, effective/freshness dates, support vs contradiction, and explicit missing evidence. Add a correction action for operator-authorized users.

### `app-front-end/src/components/memo/MemoRulingSection.tsx`

Render the recommendation as system advice and the ruling as the GP's authoritative action. Add rationale, risk acknowledgement, mandate exception, investor confidence, structured override reason, prior ruling history, and fast `ADVANCE / MONITOR / PASS` controls. `INVEST` should be reserved for the final commitment flow.

### `app-front-end/src/components/scoring/AssessmentScorecard.tsx` and `ConfidenceIndicator.tsx`

Support unscored criteria, partial/insufficient evidence, contradiction flags, and confidence caps. Never render missing evidence as a neutral score. Add a compact evaluation-version disclosure and recommendation-change summary.

### `app-front-end/src/components/WorkGrid.tsx`

Key rows by `opportunity_id`, display attention priority, service level/next-review status, source-channel count, current recommendation, and current ruling separately. Historical passes at service level 0 should not appear as actively monitored. Invalidate the row after ruling, service-level change, refresh acceptance, or claim correction.

### `app-front-end/src/components/queue/DocketCaseRow.tsx`, `QueueAttentionBadge.tsx`, and `app-front-end/src/lib/queueAttentionDriver.ts`

Use backend `attention_priority` and lifecycle data as the authoritative queue driver. Add explicit states for identity review, insufficient evidence, refresh blocked/budget exhausted, monitor due, and action awaiting approval. Do not derive institutional attention solely from the legacy reviewer score.

### `app-front-end/src/components/SystemIntelligence.tsx` and `app-front-end/src/components/system/internals.tsx`

Add a Fund Intelligence proposal inbox with pattern, attribution, sample size/period, supporting and contradicting examples, limitations, bounded preview, and Accept/Edit/Reject/Defer. After acceptance, show “Draft policy version created”; require a separate Publish button and confirmation. Preserve rejected/deferred history instead of hiding it.

The existing Scout weights and calibration panels must be read as proposals/diagnostics. Remove any wording suggesting that automatic Meta cycles changed production.

### `app-front-end/src/settings/SettingsPage.tsx`, `DecisionThresholdsPanel.tsx`, and `policyPublishRecovery.ts`

Integrate governed draft publication without bypassing the existing policy compiler. Show active policy versus accepted draft, proposal provenance, validation errors, publish confirmation, and recovery if the policy publish succeeds but the UI loses the response. Add monitoring daily-budget and default service-level explanation, but do not let UI settings imply archived deals will refresh.

### `app-front-end/src/pages/PortfolioPage.tsx`

Add an outcome timeline and coverage disclosure. Financing, shutdown, acquisition, commercial milestones, and follow-on decisions are observations—not proof that an earlier recommendation was correct or mistaken. Always render the backend limitations near aggregate outcome analysis.

### `app-front-end/src/pages/FlowPage.tsx`

Add a bounded CSV intake entry point and import summary. Require column mapping, explicit confirmation before treating mapped domains as operator-confirmed identity, and a review queue link for ambiguous rows. A CRM CSV is an intake channel, not live bidirectional CRM sync.

### `app-front-end/src/App.tsx`

Add routes or stable query parameters for identity cases, opportunity detail tabs, Fund Intelligence proposal detail, import result, and outcome entry. Query invalidation should preserve the canonical opportunity selection rather than navigating through a legacy startup duplicate.

## 8. New components to add

- `components/evidence/ClaimEvidenceLedger.tsx` — claim/evidence graph rendered as an accessible ledger, with contradictions and corrections.
- `components/evidence/FounderSignalsPanel.tsx` — allowed observable founder signals only, with interview/operator attribution.
- `components/decisions/RecommendationPanel.tsx` — immutable system recommendation, drivers, risks, gaps, and change explanation.
- `components/decisions/HumanRulingComposer.tsx` — rapid ruling and structured override capture.
- `components/actions/WorkflowActionQueue.tsx` — generated questions, information requests, monitor reviews, decision packs, and approval status.
- `components/monitoring/MonitoringControl.tsx` — service level, next review, refresh reason/envelope, reservation, and material-change history.
- `components/fund-intelligence/ProposalInbox.tsx` and `ProposalReviewDrawer.tsx` — governed learning review and separate publication.
- `components/imports/CsvImportDrawer.tsx` and `ImportResultPanel.tsx` — mapping, bounds, resolved/review/error rows, and identity links.
- `components/outcomes/OutcomeTimeline.tsx`, `OutcomeComposer.tsx`, and `OutcomeCoverageDisclosure.tsx` — provenance-first outcomes without causal claims.
- `components/evidence/ConfidentialArtifactIntake.tsx` — deck/email metadata registration, retention policy, and no storage-reference display.

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
10. Add evidence/evaluation/decision/monitoring API clients and opportunity detail queries.
11. Replace the legacy memo decision path with `RecommendationPanel` + `HumanRulingComposer`.
12. Rebuild `MemoEvidenceLedger` and scoring surfaces around claims, contradictions, unscored criteria, and versions.
13. Add workflow-action and monitoring controls.
14. Add the Fund Intelligence inbox, keeping Accept and Publish separate.
15. Add bounded CSV/CRM CSV intake and import-result identity review links.
16. Add outcome timeline and coverage disclosure.
17. Add confidential deck/email metadata intake.

This order first fixes correctness and recovery, then the authoritative recommendation/ruling model, then governance, workflows, and broader channel coverage.
