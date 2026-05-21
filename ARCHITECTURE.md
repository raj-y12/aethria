# Architecture

## Monorepo Structure

- `backend/`: FastAPI service + autonomous pipeline engines.
- `app-front-end/`: authenticated operator console.
- `web-front-end/`: marketing and access-request UX.
- `supabase/`: database schema/migrations.

## System Components

### 1) API Layer (`backend/api.py`)

FastAPI is the integration point for:
- authenticated control plane (`/api/settings`, `/api/me`)
- startup pipeline read models (`/api/startups`, memo/status endpoints)
- pipeline orchestration (`/api/agents/trigger`, lookup queueing)
- meta and analytics surfaces (`/api/meta/*`, `/api/analytics/*`)
- fund thesis lifecycle (`/api/fund-thesis*`)

Request auth is enforced through Clerk token verification middleware. Public access is intentionally limited to health/docs endpoints.

### 2) Background Worker Queue

On process startup, the API creates an in-memory async queue and worker task.

Worker job types:
- `cycle`: run one Scout/Reviewer/Partner pipeline cycle for a specific user.
- `lookup`: run focused on-demand discovery for one user/input pair.

This keeps API endpoints responsive while running model-heavy work asynchronously.

### 3) Agent Pipeline

Primary pipeline engines:
- Scout engine: discovers and frames startup opportunities.
- Reviewer engine: scores dimensions, derives verdicts, and thesis alignment fields.
- Partner engine: makes advance/pass/hold decisions and escalations.
- Portfolio engine: maintains watchlist/signals/health style state.
- Meta-Agent engine: periodic optimization feedback loop.

All engines are tenant-scoped by explicit user ID.

### 4) Storage Abstraction

- `SupabaseStartupsStorage`: production path for startup state.
- `Storage`: local file JSON path for non-supabase runs.
- `PortfolioStore`: per-user portfolio artifacts.

API code favors list projections for startup grids to reduce payload size and avoid heavy memo blobs on polling routes.

### 5) Frontend Architecture

`app-front-end`:
- React Router + Clerk auth + TanStack Query.
- `App.tsx` gates app routes by sign-in and token readiness.
- `MainLayout` drives three primary operator surfaces:
  - Work grid (deal list)
  - Memo panel (progressive detail)
  - System/Judgements panels (signals/escalations/meta)
- App auto-triggers agents once after load.

`web-front-end`:
- Animated route-driven public site.
- Waitlist API route sends email via Resend and attempts backend persistence.

## Data Flow

1. User authenticates in app frontend via Clerk.
2. Frontend sends bearer token to backend APIs.
3. App calls `/api/agents/trigger` once to enqueue tenant pipeline work.
4. Worker processes jobs and writes startup/review/partner/memo data.
5. Frontend polls read endpoints (`/api/startups`, `/api/startups/{id}/memo`, analytics) and updates UI.

## Memo Delivery Model

- The startup grid receives a thin payload (`/api/startups`).
- Selecting a startup fetches full detail (`/api/startups/{id}`).
- Memo endpoint returns:
  - `ready` with markdown
  - `generating` with partial scout/review/partner slices
  - `failed` with error and partial data

This avoids blocking UX while preserving deterministic state transitions.

## Operational Modes

- **All-in-one local mode**: `python3 run.py` starts backend + both frontends and optionally agent process.
- **Supabase production mode**: API handles trigger queue and background worker in same process; requires Supabase + OpenAI + Clerk env setup.
- **Agent CLI mode**: `backend/run_system.py --user-id=<clerk_sub>` runs engines independently.

## Agent Handoff Trace

Aethria keeps the MVP pipeline simple, but each stage now emits a structured handoff trace on the startup row through `agent_trace`.

Trace stages:
- `scout`: discovery source coverage, scout confidence, missing thesis context, and source quality flags.
- `reviewer`: reviewer consensus, score variance, structured signal confidence, missing evidence, conflicts, and thesis mismatch warnings.
- `partner`: final recommendation explainability, decision drivers, quality flags consumed from earlier stages, and human-review escalation state.

The trace is intentionally embedded JSON for now rather than a separate event bus or evidence graph. It gives the API and later UI surfaces a single audit object that explains what each stage saw, what it trusted, what was missing, and why the final recommendation happened.

Quality gates are deterministic and conservative:
- Fatal failures remain reserved for unusable model/schema/storage output.
- Serious quality issues continue the pipeline but mark handoff quality and can set `human_review_required`.
- Warnings are persisted so weak sources, missing data, contested reviews, and low confidence are visible instead of silently disappearing.

The partner engine consumes the review handoff quality through the existing review payload. It does not change canonical score thresholds in this layer; it adds decision drivers, risks, and human-review escalation when evidence quality is weak or contested.
