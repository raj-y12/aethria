# Institutional Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the Phase 0–8 institutional backend as an analyst-grade frontend: durable work, canonical identity review, evidence-backed assessment, human rulings and workflow actions, monitoring, governed Fund Intelligence, channel imports, and outcomes.

**Architecture:** Preserve the existing legacy startup projection for deal-flow compatibility, but treat canonical company/opportunity records as the source of truth for institutional detail. Put all network communication in typed `src/api/` clients, all server reads and invalidation in TanStack Query hooks, and compose the new functionality into three focused surfaces: Dispatch execution, Opportunity Intelligence inside the memo, and Operations inside System Intelligence. Add a tenant-safe compatibility resolver from legacy startup ID to canonical opportunity so the frontend never invents identity links.

**Tech Stack:** React 18, TypeScript, TanStack Query 5, Framer Motion, Vitest/Testing Library, existing CSS design tokens and component conventions.

**Global constraints:** Clerk-authenticated API clients only; no direct component fetches; exact backend state names; factual evidence language; explicit loading, empty, unavailable, and error states; no new runtime dependencies.

---

## Task 1: Typed institutional API contracts

**Files:**
- Create: `app-front-end/src/api/jobs.ts`
- Create: `app-front-end/src/api/identity.ts`
- Create: `app-front-end/src/api/evidence.ts`
- Create: `app-front-end/src/api/evaluations.ts`
- Create: `app-front-end/src/api/decisions.ts`
- Create: `app-front-end/src/api/monitoring.ts`
- Create: `app-front-end/src/api/fundIntelligence.ts`
- Create: `app-front-end/src/api/channelsOutcomes.ts`
- Test: `app-front-end/src/api/__tests__/institutionalClients.test.ts`
- Modify: `app-front-end/src/api/startups.ts`
- Test: `app-front-end/src/api/__tests__/startupsLookup.test.ts`

- [ ] Write request/response tests for URL, method, body, exact durable status, and snake-case mapping.
- [ ] Run focused tests and confirm they fail because the clients/contracts do not exist.
- [ ] Implement a shared authenticated JSON request helper and the minimum clients needed by the tests.
- [ ] Extend lookup/rerun acceptance results with `jobId`, `acceptedAt`, and `pipelineRunId`.
- [ ] Run focused tests and TypeScript build until green.

## Task 2: Durable Dispatch execution

**Files:**
- Modify: `app-front-end/src/lib/dispatchLookupPersistence.ts`
- Modify: `app-front-end/src/hooks/useDispatchLookup.ts`
- Modify: `app-front-end/src/components/DispatchCommandBar.tsx`
- Modify: `app-front-end/src/App.tsx`
- Test: `app-front-end/src/lib/__tests__/dispatchLookupPersistence.test.ts`
- Test: `app-front-end/src/components/__tests__/DispatchCommandBar.test.tsx`

- [ ] Write persistence tests for v2 durable job metadata and safe v1 invalidation.
- [ ] Write component tests for accepted, retry-wait, blocked/dead-letter, retry, and cancellation presentation.
- [ ] Run focused tests and confirm RED.
- [ ] Persist durable metadata, poll the job as authoritative execution state, and retain domain-output polling during transition.
- [ ] Add Retry/Cancel controls, automatic-recovery copy, and identity-review routing for blocked jobs.
- [ ] Run focused tests and build until green.

## Task 3: Canonical identity and compatibility navigation

**Files:**
- Modify: `backend/routers/identity.py`
- Test: `backend/tests/identity/test_identity_api.py`
- Modify: `app-front-end/src/api/identity.ts`
- Create: `app-front-end/src/components/identity/IdentityReviewQueue.tsx`
- Create: `app-front-end/src/components/identity/IdentityResolutionDrawer.tsx`
- Create: `app-front-end/src/components/identity/CompanyIdentityPanel.tsx`
- Create: `app-front-end/src/components/identity/SourceObservationsPanel.tsx`
- Modify: `app-front-end/src/components/SystemIntelligence.tsx`
- Test: `app-front-end/src/components/identity/__tests__/IdentityResolutionDrawer.test.tsx`

- [ ] Write a backend contract test for tenant-scoped canonical opportunity lookup by legacy startup ID.
- [ ] Run it and confirm RED, then add the read-only compatibility endpoint using the existing repository method.
- [ ] Write UI tests proving identity candidates are compared explicitly and no candidate is auto-selected.
- [ ] Implement the open-case queue, resolution drawer, match/create/defer/reject mutations, and invalidation.
- [ ] Add the factual company/opportunity identity disclosure and bounded source observation timeline.
- [ ] Run backend/frontend focused tests until green.

## Task 4: Opportunity Intelligence workspace

**Files:**
- Create: `app-front-end/src/components/institutional/OpportunityIntelligence.tsx`
- Create: `app-front-end/src/components/institutional/ClaimEvidenceLedger.tsx`
- Create: `app-front-end/src/components/institutional/FounderSignalsPanel.tsx`
- Create: `app-front-end/src/components/institutional/HumanRulingComposer.tsx`
- Create: `app-front-end/src/components/institutional/WorkflowActionQueue.tsx`
- Create: `app-front-end/src/components/institutional/MonitoringControl.tsx`
- Create: `app-front-end/src/components/institutional/ConfidentialArtifactIntake.tsx`
- Modify: `app-front-end/src/components/InvestmentMemoContent.tsx`
- Test: `app-front-end/src/components/institutional/__tests__/OpportunityIntelligence.test.tsx`

- [ ] Write tests for claim/evidence citations, correction, immutable evaluation disclosure, ruling note requirement, action approval, refresh budget, and confidential metadata-only intake.
- [ ] Run tests and confirm RED.
- [ ] Implement a query-backed workspace with Evidence, Decision, Actions, and Monitoring sections.
- [ ] Render observable founder signals from claims/interview evidence without unsupported labels.
- [ ] Gate action execution on explicit approval and show refresh reservation/budget responses.
- [ ] Integrate beneath the existing memo when a canonical opportunity is available, with an unavailable explanation otherwise.
- [ ] Run focused tests and build until green.

## Task 5: Fund Intelligence governance

**Files:**
- Create: `app-front-end/src/components/institutional/ProposalInbox.tsx`
- Create: `app-front-end/src/components/institutional/ProposalReviewDrawer.tsx`
- Modify: `app-front-end/src/components/system/internals.tsx`
- Modify: `app-front-end/src/components/LiveIntelligenceFeed.tsx`
- Test: `app-front-end/src/components/institutional/__tests__/ProposalInbox.test.tsx`

- [ ] Write tests that proposals are never described as applied and activation requires preview, review, and publish.
- [ ] Run tests and confirm RED.
- [ ] Implement proposal list/detail, preview, approval/rejection, and governed publication.
- [ ] Correct Meta copy to distinguish analysis, proposals, and explicit production mutation.
- [ ] Run focused tests and build until green.

## Task 6: Channel intake and outcomes

**Files:**
- Create: `app-front-end/src/components/institutional/CsvImportDrawer.tsx`
- Create: `app-front-end/src/components/institutional/OutcomePanel.tsx`
- Modify: `app-front-end/src/pages/FlowPage.tsx`
- Modify: `app-front-end/src/pages/PortfolioPage.tsx`
- Test: `app-front-end/src/components/institutional/__tests__/ChannelOutcomeTools.test.tsx`

- [ ] Write tests for preview-first CSV import, idempotency key handoff, row results, outcome creation, and coverage disclosure.
- [ ] Run tests and confirm RED.
- [ ] Implement CSV preview/commit and import status result surfaces.
- [ ] Implement company outcome timeline/composer and portfolio-level coverage disclosure.
- [ ] Run focused tests and build until green.

## Task 7: Operational readiness and full verification

**Files:**
- Modify: `app-front-end/src/hooks/useSystemData.ts`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/components/SystemBar.tsx`
- Modify: `app-front-end/src/components/SystemIntelligence.tsx`
- Test: relevant existing system/settings suites

- [ ] Add system status and durable count tests.
- [ ] Implement healthy/degraded/blocked execution states without conflating agent toggles with readiness.
- [ ] Run all frontend tests, lint, TypeScript/Vite build, and bundle check.
- [ ] Run affected backend identity API tests and the institutional backend suites.
- [ ] Inspect `git diff`, verify no unrelated user changes were overwritten, and record any remaining deployment-only dependency.
