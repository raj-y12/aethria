# Product Spec

## Product Overview

Aethria is an AI-native dealflow operating system for venture workflows. It converts inbound market signals into structured decisions with traceable reasoning and portfolio context.

The product experience is split into:
- Authenticated operator app (`app-front-end`)
- Public website and access funnel (`web-front-end`)
- Backend API and pipeline runtime (`backend`)

## Primary Users

- Investment associates/analysts managing top-of-funnel.
- Partners making final investment decisions.
- Platform/ops users monitoring pipeline health and escalation queues.

## Core Jobs To Be Done

- Discover and triage opportunities continuously.
- Review opportunities through a normalized scoring rubric.
- Produce decision-ready investment memos.
- Escalate uncertain decisions to human operators.
- Track portfolio-level implications (signals, concentration, watchlist quality).

## Core Product Flows

### 1) Sign-in and Session Gating

- App routes (`/v1`, `/settings`) require Clerk sign-in.
- The app waits for token readiness before loading API-backed views.

### 2) Pipeline Auto-Trigger

- On first app load, client calls `POST /api/agents/trigger`.
- Trigger can be queued, skipped (e.g. disabled/misconfigured), or unavailable.

### 3) Deal Workspace

Main workspace supports:
- Deal grid with startup list and status context.
- Memo panel with full startup detail.
- Judgements feed panel (live intelligence context).
- System panel (escalations, analytics, meta-agent state).

### 4) Progressive Memo UX

Memo endpoint supports partial rendering while pipeline is still running:
- `generating`: show scout/review/partner partials
- `ready`: show markdown memo
- `failed`: show error with partial context

### 5) On-Demand Lookup

- User can submit company name/domain/context from workspace.
- Client queues lookup with a stable `lookup_id`.
- UI tracks lookup progress and opens memo when partner decision lands.
- Failure is surfaced via lookup status polling.

### 6) Escalation Resolution

- Startups requiring human review appear in escalation list.
- Human resolution writes explicit decision + notes + timestamp.

## Functional Requirements

- **Auth**: all private APIs require valid Clerk bearer token.
- **Tenancy**: data must be scoped to `user_id` end-to-end.
- **Queueing**: pipeline and lookup work must execute asynchronously.
- **Resilience**: frontend should remain functional when worker is busy or incomplete.
- **Traceability**: decision artifacts include rationale, confidence, and timestamps.
- **Control Plane**: settings PATCH must be server-validated.
- **Observability**: system health and agent status must be queryable by UI.

## Non-Functional Requirements

- Responsive UI with mobile and desktop layouts.
- Deterministic API contracts for polling-heavy screens.
- Avoid large list payloads (thin list projection for startup grid).
- Graceful degradation when Supabase/OpenAI are not configured.

## Marketing Site Requirements

- Landing experience communicates pipeline phases and product positioning.
- `/request-access` collects waitlist info and triggers notification email.
- Waitlist submissions should attempt backend persistence when API URL is configured.

## Current Scope Boundaries

- Backend is the source of truth for pipeline and analytics state.
- Frontend does not run local business logic replicas for decisions.
- Agent execution is server-side only.
- Public site and app are separate frontends with different intents and entry paths.
