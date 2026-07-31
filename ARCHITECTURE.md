# Architecture

How Aethria is put together, why, and where each responsibility lives. This
document describes the system **as implemented**. Decisions that are easy to
question later are recorded separately in [docs/adr/](docs/adr/).

---

## 1. System overview

Three deployable units and one shared database:

```
   ┌──────────────────┐        ┌──────────────────┐
   │  web-front-end   │        │  app-front-end   │
   │  marketing site  │        │  operator console│
   │  Vite + SSG      │        │  Vite SPA        │
   └────────┬─────────┘        └────────┬─────────┘
            │ waitlist POST             │ Clerk JWT (Bearer) on every call
            │                           │ + SSE subscription (GET /api/stream)
            └─────────────┬─────────────┘
                          ▼
                 ┌──────────────────┐        ┌────────────────────────┐
                 │     backend      │───────▶│ OpenAI (chat + embed)  │
                 │  FastAPI (api.py)│───────▶│ Exa → Firecrawl →      │
                 │  + agent pipeline│        │ DuckDuckGo             │
                 └────────┬─────────┘        │ (web retrieval chain)  │
                          │                  └────────────────────────┘
                          │ service-role client / direct DSN
                          ▼
                 ┌──────────────────────────────────┐
                 │ Supabase PostgreSQL              │
                 │  · startups + projections        │
                 │  · agent_jobs (durable queue)    │
                 │  · canonical identity/evidence   │
                 │  · governed policy versions      │
                 └──────────────────────────────────┘
```

The frontends never touch Supabase directly — all persistence goes through the
backend using the service-role client ([ADR-0003](docs/adr/0003-supabase-row-level-storage.md)).

---

## 2. Tenancy model

Aethria is multi-tenant with **no implicit tenant anywhere**.

- The tenant identifier is the Clerk JWT `sub` claim, surfaced as
  `request.state.user_id` by `backend/auth_clerk.py`.
- `backend/tenant_context.py` provides `TenantContext` and `require_user_id()`.
  Every engine constructor and every pipeline entry point calls it, so a missing
  tenant raises at construction rather than silently reading the wrong data.
- Every Supabase query filters on `user_id`; migrations add row-level security
  policies for the tables reached with a non-service role.

This is the single most load-bearing invariant in the codebase.
See [ADR-0001](docs/adr/0001-explicit-tenancy.md).

---

## 3. The agent pipeline

### 3.1 Stage order

```
ScoutEngine → ReviewerEngine → PartnerEngine → PortfolioEngine → MetaAgent
```

Orchestrated by `run_one_pipeline_cycle(user_id)` in `backend/pipeline_runner.py`.
Each stage is `async`, tenant-scoped, individually toggleable in user settings,
and gated on the active fund thesis.

| Stage | Module | Responsibility |
|---|---|---|
| **Scout** | `backend/scout/` | Discover *real* companies via the retrieval chain (Exa semantic search finds candidate companies, Firecrawl reads their pages) + OpenAI structuring. Four personas: `market_driven`, `builder_technical`, `pain_point`, `contrarian`. Persona selection is weighted by the MetaAgent; backpressure throttles discovery when the review backlog builds, and ramp waves accelerate it when the backlog drains. |
| **Reviewer** | `backend/reviewer/` | Three personas — Default, Skeptical, Opportunist — score five dimensions (market, product, technical, execution, defensibility) 1–10 in parallel, then blend into a consensus with variance and confidence discounting. Gap retrieval fills missing evidence before scoring. |
| **Partner** | `backend/partner/` | Produces INVEST / PASS / MONITOR. **Rule-based by default** against versioned thresholds; the LLM is only invoked for the edge-case triggers declared in the active partner-rules file. Escalates to human review when evidence is weak or reviewers disagree. |
| **Portfolio** | `backend/portfolio/` | Tracks accepted companies: execution checkpoints, external signals, feedback loops, and health checks, each on its own interval. Also owns rejection analysis and concentration clustering. |
| **Meta** | `backend/meta/` | Self-optimisation. Analyses outcomes, then mutates scout prompts (`mutator.py`), reweights scout personas (`reweighter.py`), and calibrates reviewer thresholds (`calibrator.py`). Runs on its own interval (`META_AGENT_INTERVAL_SECONDS`, default daily) — it self-gates and returns early when the interval has not elapsed. |

### 3.2 The fund thesis gate

`backend/fund_thesis.py` holds the per-user investment mandate.
`get_active_thesis(user_id)` bootstraps a default on first access and is cached
briefly (`FUND_THESIS_CACHE_TTL_SECONDS`). If no complete active thesis exists,
the **periodic** cycle logs a warning and returns without running any stage.

On-demand lookup is deliberately different: it is *mandate-aware* (the thesis
shapes scoring when present) but never thesis-blocked, because a user asking
about a specific company should always get an answer.

### 3.3 Handoff traces

Each stage writes a structured trace onto the startup row via
`backend/agent_trace.py`: what the stage saw, what it trusted, what was missing,
and why it concluded what it did. Quality gates are deterministic and
conservative — fatal failure is reserved for unusable model/schema/storage
output; serious quality issues continue the pipeline but mark handoff quality and
can set `human_review_required`; warnings are persisted rather than dropped.

### 3.4 Decision policy is data

Partner thresholds and LLM-escalation triggers live in
`resources/config/partner_rules/v{1..4}.json`. `resources/config/active.json`
selects the live version (`v4` at time of writing) and
`backend/core/policy_resolver.py` resolves it at runtime. Reviewer rules, the
evaluation rubric, and the default fund thesis are versioned the same way.
Changing decision behaviour means publishing a new policy version, not editing
Python. See [ADR-0002](docs/adr/0002-versioned-decision-policy.md).

The governed path goes further: `backend/services/scoring/` compiles a fund
configuration into a policy, previews it, and publishes it as an immutable
`governed_policy_version` row bound to a content hash, with legacy settings
projected idempotently through an outbox.

---

## 4. Request and data flow

### 4.1 Work admission

Two kinds of work enter the system, and there are two admission paths depending
on configuration:

```
POST /api/agents/trigger  ─┐
POST /api/startups/lookup ─┤
POST /api/opportunities/  ─┘
     manual-lookup
                           │
      USE_SUPABASE_STORAGE=1 (production)      USE_SUPABASE_STORAGE unset (dev)
                           │                                 │
                           ▼                                 ▼
         ┌───────────────────────────────┐      ┌───────────────────────────┐
         │ durable job store (PostgreSQL)│      │ in-process asyncio queues │
         │ agent_jobs: queued → running  │      │ _agent_queue              │
         │ leases · heartbeats · retry   │      │ _lookup_queue             │
         │ blocked · dead_letter         │      │ (no durability)           │
         └───────────────┬───────────────┘      └─────────────┬─────────────┘
                         │  DurableJobWorker                  │  in-process workers
                         └──────────────┬─────────────────────┘
                                        ▼
                        run_one_pipeline_cycle(user_id)
                        run_on_demand_lookup(user_id, …)
```

In production the API returns only after PostgreSQL has committed the job row
(`jobs/repository.py`), so an accepted job survives a process restart. Job types
are `pipeline_cycle`, `company_lookup`, and `evidence_refresh`; the worker
(`jobs/worker.py`) applies leases with fencing tokens, heartbeats, bounded
per-tenant and global concurrency, and explicit `blocked` states with block codes
rather than opaque failures. See [ADR-0005](docs/adr/0005-durable-job-store.md).

### 4.2 Read path

The operator console reads thin projections and fetches detail on demand:

1. `GET /api/startups` returns a **list projection** — no memo blobs — bounded by
   `STARTUPS_LIST_DEFAULT_LIMIT` / `STARTUPS_LIST_MAX_LIMIT`.
2. Selecting a deal fetches `GET /api/startups/{id}` for the full payload.
3. `GET /api/startups/{id}/memo` is progressive: `generating` returns partial
   scout/review/partner slices, `ready` returns the markdown memo, `failed`
   returns the error plus whatever partial data exists.

### 4.3 Live updates

`GET /api/stream` is a Server-Sent Events endpoint. Pipeline stages call
`event_bus.publish(user_id, …)`; the frontend's `useStartupsStream` treats the
parsed hello frame (not HTTP 200) as the health signal and refetches on each
`startups_changed` nudge. Timed polling remains as a slow backstop.

`backend/event_bus.py` is process-local by default. For multi-instance
deployments, `EVENT_BUS_BACKPLANE=postgres` plus a direct `DATABASE_URL` adds
`LISTEN`/`NOTIFY` fan-out between instances. **Production fails closed**: booting
with `ENVIRONMENT=production` and neither a backplane nor an explicit
`ALLOW_PROCESS_LOCAL_STATE=true` raises at startup, so a silently-broken
multi-instance deployment is impossible. See [ADR-0004](docs/adr/0004-sse-with-poll-backstop.md).

---

## 5. The canonical institutional layer

Alongside the original `startups` model, the backend implements a canonical
evidence-and-decision domain. It is being rolled out behind an explicit authority
mode rather than swapped in at once.

| Domain | Module | What it owns |
|---|---|---|
| Identity | `backend/identity/` | Source observations → normalisation → canonical `companies` / `opportunities`; ambiguous matches become `identity_cases` for human resolution rather than silent merges. |
| Evidence | `backend/evidence/` | Artifacts, claims, claim↔evidence links, trust/verification classes, access classes for confidential material, operator corrections, and prompt-injection detection on ingested text. |
| Evaluation | `backend/evaluation_v2/` | Immutable evaluations bound to a policy version and an evidence snapshot, with explicit prerequisites — a thesis-blind or evidence-thin evaluation fails closed instead of guessing. |
| Decisions | `backend/decisions/` | Authoritative human rulings, workflow actions, approvals, CRM export. An approval records intent; it does not itself perform an external write. |
| Monitoring | `backend/monitoring/` | Service levels 0–5, refresh reservations with cost envelopes, material-change checks. |
| Fund intelligence | `backend/fund_intelligence/` | Derives attributed policy proposals from outcomes; proposals are previewed, human-reviewed, and published as governed policy versions. |
| Triage | `backend/triage/` | Light-touch assessment before deep review. |
| Outcomes / channels | `backend/outcomes/`, `backend/ingest/` | Immutable later observations (funding, launches, acquisitions) and bounded CSV/CRM/referral intake. |
| Authority | `backend/authority/` | The rollout state machine itself. |

`backend/opportunity_pipeline.py` is the orchestration-only application service
that sequences these for a manual lookup, making the fail-closed ordering
explicit so a caller cannot accidentally run a thesis-blind evaluation or
evaluate an ambiguous company.

**Rollout modes** (`authority/models.py::RolloutMode`):
`legacy → shadow → backfill → canonical_write → canonical_read`, with
reconciliation and rollback endpoints under `/api/authority/*`. Workflow state
(`WorkflowState`) and block codes (`BlockCode`) are enums, not free text, so a
stuck opportunity always names its reason.
See [ADR-0006](docs/adr/0006-canonical-identity-layer.md).

---

## 6. Storage

| Concern | Implementation |
|---|---|
| Startup CRUD | `backend/supabase_storage.py` — targeted column updates preserve TOAST pointers; `replace_all` is upsert-first, prune-after. Detects schema drift at startup and logs it loudly, because the write path otherwise tolerates missing columns by dropping fields. |
| Key-value documents | `backend/supabase_doc_store.py` — settings, meta state, prompt library, calibration. |
| Portfolio artefacts | `backend/portfolio/store.py` + `repository.py`. |
| Durable jobs & canonical domain | Direct PostgreSQL via `asyncpg` (`backend/jobs/postgres.py`), pooled and lease-aware. |
| Dev fallback | `backend/utils/storage.py` — local JSON under `backend/data/`. **Dev only**; the production pipeline requires `USE_SUPABASE_STORAGE=1`. |

Schema lives in `supabase/migrations/`, applied in timestamp order and never
edited after the fact. `supabase/clear_all_tables.sql` is a destructive local
reset helper, not part of any automated path.

---

## 7. Security posture

- **Authentication**: Clerk RS256 JWT verified against the JWKS endpoint
  (`backend/auth_clerk.py`). Issuer and audience are verified when configured;
  JWKS fetching happens off the event loop. Failures are 401, fail-closed.
- **Public surface**: `/health` only, plus OpenAPI/docs — and those are gated off
  in production unless `PUBLIC_API_DOCS_ENABLED` is set.
- **Rate limiting**: `backend/security/rate_limiter.py` applies fixed-window
  policies per route class (lookup/minute, lookup/day, resolve, agent trigger,
  meta trigger, settings mutation, admin login/overview).
- **Request guards**: `backend/security/request_guards.py` validates route IDs and
  enforces authenticated-user requirements before handlers run.
- **Prompt safety**: `backend/security/prompt_safety.py` and
  `evidence.service.detect_prompt_injection` screen retrieved third-party text
  before it reaches a model prompt.
- **Admin surface**: separate secret-based login with its own token TTL, audit
  logging (`admin_audit.py`), and failure-count limits.
- **Distributed locks**: agent trigger, lookup, and meta trigger each take a
  TTL'd lock so concurrent requests cannot double-run a tenant's cycle.

---

## 8. Frontend architecture

### 8.1 `app-front-end/` — operator console

- React 19, Vite, React Router, TanStack Query, Framer Motion, Tailwind.
- `main.tsx` mounts `ClerkProvider` + `QueryClientProvider`. Query defaults use
  finite freshness (90s stale time) with refetch on mount/reconnect; immutable
  queries opt into static behaviour explicitly.
- `App.tsx` is the auth shell: sign-in gate, token-readiness check, route-derived
  panel state, and a one-time `POST /api/agents/trigger` on load when agents are
  enabled.
- Route roots: `/v1` (workspace), `/v1/fund`, `/v1/portfolio`, `/v1/flow`,
  `/v1/deal/*`, `/v1/settings`, `/admin`, `/sign-in`.
- `src/api/` holds every typed backend client. **No `fetch` outside `src/api/`**,
  and every client goes through `api/auth.ts` for the Clerk token.
- `src/design-system/` holds tokens and semantics; the visual contract is
  documented in [`app-front-end/DESIGN_SYSTEM.md`](app-front-end/DESIGN_SYSTEM.md)
  and the product rationale in
  [`app-front-end/DESIGN_DIRECTION.md`](app-front-end/DESIGN_DIRECTION.md).
- `src/lib/` holds pure, unit-tested logic (scoring presentation, memo text,
  lookup tracking, warm start, attention drivers) kept out of components.
- `screenshot/` is a Vite harness for rendering UI states headlessly against
  mock data; `vite.screenshot.config.ts` and `.claude/launch.json` drive it.

### 8.2 `web-front-end/` — marketing site

- React 18 + `vite-react-ssg` (static generation), GSAP/Framer Motion/Lenis for
  motion, D3 + TopoJSON for the market map.
- `api/waitlist.ts` is a Vercel serverless function: sends notification email via
  Resend and attempts backend persistence when an API URL is configured.
- Visual source of truth for the current design is
  `docs/design/explorations/J-gallery-instruments.html`, referenced from the
  component headers.

### 8.3 `packages/product-chrome/`

Shared, framework-light React chrome (`LookupCommandBar`, `MandateCard`,
`LookupResultSnapshot`) plus its CSS, consumed by **both** frontends via a path
alias. It is a source-only workspace package — no build step, no publish.

---

## 9. Configuration

`backend/env_config.py` is the canonical registry of every environment variable
the backend reads: name, type, default, section, and description. Two things
derive from it — `.env.example` is generated from it, and a test asserts that
every `os.getenv` name in the codebase is registered and that `.env.example` is
in sync. A new environment variable therefore cannot be added without being
documented. Accessors read `os.environ` at call time (not at import), because the
pipeline re-reads settings each cycle and tests monkeypatch after import.
See [ADR-0008](docs/adr/0008-env-registry.md).

Per-user configuration (fund identity, agent toggles, cost budget, portfolio
settings) lives in Supabase and is loaded with `load_settings(user_id)` — never
from a global config file.

---

## 10. Observability

- `GET /health` — liveness.
- `GET /api/system/status` and `GET /api/analytics/system-health` — readiness
  diagnostics: worker state, Supabase/OpenAI configuration, thesis readiness.
- `GET /metrics` — process and pipeline counters (`backend/metrics.py`).
- `GET /api/agents/status`, `GET /api/agents/loop-status` — per-tenant agent state.
- RSS and event-loop-lag samplers run as background tasks and warn above
  `LOOP_LAG_WARN_SECONDS`; `MALLOC_ARENA_MAX` is tuned for RSS control on small
  instances (see [docs/operations/backend-memory-tuning.md](docs/operations/backend-memory-tuning.md)).
