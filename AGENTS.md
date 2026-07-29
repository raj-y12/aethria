# AGENTS.md — operating rules for this repository

Rules that govern how code is written here, for human contributors and AI agents
alike. For orientation read [ARCHITECTURE.md](ARCHITECTURE.md); for commands read
[DEVELOPMENT.md](DEVELOPMENT.md); for process read [CONTRIBUTING.md](CONTRIBUTING.md).

---

## What this is

Aethria is a multi-tenant, AI-driven venture deal-flow platform. It discovers
startups, evaluates them against a per-user **fund thesis**, decides
INVEST / PASS / MONITOR, and escalates uncertain cases to a human.

```
ScoutEngine → ReviewerEngine → PartnerEngine → PortfolioEngine → MetaAgent
```

Every stage is async, scoped to one `user_id`, and gated by the active fund
thesis. No thesis, no periodic pipeline.

---

## Non-negotiable invariants

Breaking one of these is a bug, not a trade-off. Each has an ADR.

1. **Explicit tenancy.** Every storage call and engine constructor takes an
   explicit `user_id`. Call `require_user_id()` at the top. Never read a tenant
   from a request body or a global. ([ADR-0001](docs/adr/0001-explicit-tenancy.md))
2. **Fund thesis gates the periodic pipeline.** `get_active_thesis()` must
   succeed; otherwise log a warning and return. On-demand lookup is
   mandate-aware but never thesis-blocked.
3. **Decision policy is versioned data.** Thresholds live in
   `resources/config/partner_rules/`, selected by `resources/config/active.json`.
   Never hardcode a threshold in Python. ([ADR-0002](docs/adr/0002-versioned-decision-policy.md))
4. **Row-level storage.** Targeted upserts only. Never delete-and-rewrite a
   table for one tenant. The frontend never touches Supabase.
   ([ADR-0003](docs/adr/0003-supabase-row-level-storage.md))
5. **Fail closed.** Missing thesis, ambiguous identity, thin evidence, or an
   unconfigured dependency produces a *named* block — never a plausible guess.
   ([ADR-0010](docs/adr/0010-fail-closed-gates.md))
6. **Configuration is registered.** New env var → an `EnvVar(...)` in
   `backend/env_config.py` → regenerate `.env.example`. A bare `os.getenv` for an
   unregistered name fails CI. ([ADR-0008](docs/adr/0008-env-registry.md))
7. **Migrations are append-only.** New timestamped file in
   `supabase/migrations/`. Never edit an applied migration.
8. **LLM calls are the dominant cost.** Keep prompts minimal, respect
   `CostController` budget gates, and don't add a model call where a rule works.
   ([ADR-0009](docs/adr/0009-rule-based-partner-llm-for-edge-cases.md))
9. **Prompt versions track prompt changes.** Any prompt edit must be reflected in
   the `prompt_version` hash via `utils/prompt_version.py`.
10. **Production requires Supabase.** `USE_SUPABASE_STORAGE=1` enables the
    durable job store and the canonical layer; the local JSON store is dev only.

---

## Backend map (`backend/`)

### Pipeline

| Module | Role |
|---|---|
| `pipeline_runner.py` | Orchestrates one pipeline cycle or one on-demand lookup for one user |
| `pipeline_execution.py` / `pipeline_state.py` / `pipeline_concurrency.py` | Typed stage results, persisted run state, concurrency slots |
| `scout/` | 4 personas — `market_driven`, `builder_technical`, `pain_point`, `contrarian`. OpenAI + Tavily; discovers **real** companies with verifiable references |
| `reviewer/` | 3 personas — Default, Skeptical, Opportunist. Score market/product/technical/execution/defensibility 1–10, blend to consensus with confidence discounting |
| `partner/` | Rule-based INVEST / PASS / MONITOR from the active partner-rules version; LLM only for declared edge cases |
| `portfolio/` | Execution, signals, feedback, health, rejection analysis, cost control |
| `meta/` | Self-optimisation: `mutator.py` (prompts), `reweighter.py` (scout weights), `calibrator.py` (reviewer thresholds), `evaluator.py` (prompt eval gate) |
| `opportunity_pipeline.py` | Canonical, orchestration-only manual-lookup service with explicit fail-closed ordering |

### Platform

| Module | Role |
|---|---|
| `api.py` | FastAPI app, lifespan, SSE, and the endpoints not yet extracted to routers |
| `routers/` | Domain routers — jobs, identity, evidence, evaluations, decisions, monitoring, fund intelligence, authority, analytics, meta, fund thesis, portfolio, imports, opportunities, channels/outcomes |
| `jobs/` | Durable PostgreSQL job store: worker, leases, fencing, outbox, lookup outcomes ([ADR-0005](docs/adr/0005-durable-job-store.md)) |
| `auth_clerk.py` | Clerk RS256 JWT verification via JWKS; sets `request.state.user_id` |
| `tenant_context.py` | `TenantContext` + `require_user_id()` |
| `env_config.py` | The environment-variable registry |
| `event_bus.py` | Per-user pub/sub behind `GET /api/stream`, with optional Postgres backplane |
| `security/` | Rate limiter, request guards, prompt safety |
| `supabase_storage.py` | Startup CRUD; targeted column updates; schema-drift detection |
| `supabase_doc_store.py` | Key-value JSON tables (settings, meta state, prompt library) |
| `utils/storage.py` | Local JSON fallback — dev only |
| `models.py` | `Startup`, `ScoutInfo`, `ReviewInfo` (`SingleReview` × 3), `PartnerInfo`, `Financials` |
| `agent_trace.py` | Per-stage structured handoff traces |
| `metrics.py` | Counters behind `GET /metrics` |

### Canonical institutional layer

`identity/` · `evidence/` · `evaluation_v2/` · `decisions/` · `monitoring/` ·
`fund_intelligence/` · `triage/` · `outcomes/` · `ingest/` · `authority/` ·
`services/scoring/`

Rolled out behind `RolloutMode`
(`legacy → shadow → backfill → canonical_write → canonical_read`).
See [ADR-0006](docs/adr/0006-canonical-identity-layer.md).

---

## Frontend map (`app-front-end/src/`)

| Path | Role |
|---|---|
| `main.tsx` | Clerk + TanStack Query providers, fonts, shared product chrome |
| `App.tsx` | Auth shell, token-readiness gate, route-derived panel state, one-time agent trigger |
| `pages/` | `HomePage`, `FlowPage`, `FundPage`, `PortfolioPage` |
| `components/` | Deal grid, memo, dispatch, identity, institutional, queue, scoring, system panels |
| `settings/` | Fund thesis, agent toggles, cost budget, decision thresholds, policy publishing |
| `hooks/` | TanStack Query data hooks — check here before writing new fetch logic |
| `api/` | Typed backend clients. **The only place `fetch` is allowed** |
| `lib/` | Pure, unit-tested logic kept out of components |
| `design-system/` | Tokens and semantics; contract in `DESIGN_SYSTEM.md` |

`web-front-end/` is the public marketing site (React 18 + `vite-react-ssg`), with
a Vercel serverless waitlist function at `api/waitlist.ts`.
`packages/product-chrome/` is source-only shared React chrome used by both.

---

## Coding rules

### Python

- Explicit `user_id`; `require_user_id()` at the top of engines and pipeline
  functions.
- Pydantic models for all data shapes; `.model_dump()` / `.model_validate()`.
- Enums for states, modes, and block reasons — no free-text status strings.
- Async throughout. `asyncio.to_thread` for blocking I/O; `asyncio.gather` only
  where stages are genuinely independent.
- Settings load per user: `load_settings(user_id)`. Never a global config file
  for per-user data.
- Log the reason whenever work is skipped.
- Reference validation is not optional — startups without verifiable external
  references are pruned in the cycle (`remove_startups_without_references`).

### TypeScript

- All backend calls go through typed clients in `src/api/`; tokens come from
  `api/auth.ts`. No `fetch` elsewhere.
- TanStack Query via the existing hooks.
- Framer Motion for animation in the app; don't add another library.
- Named design tokens only — no raw hex, no arbitrary pixel spacing.
- ESLint runs with `--max-warnings 0`.

### SQL

- One new timestamped migration per change, RLS policies included.
- If repository code exercises it, add the migration to the CI list in
  `.github/workflows/ci.yml` and extend the PostgreSQL contract tests.

---

## Common tasks

**New scout persona** — subclass `Scout` in `scout/base.py`, add to
`scout/scouts.py`, register in `ScoutEngine.__init__`, add the `scout_type`
literal to `ScoutInfo` in `models.py`.

**New endpoint** — add to the relevant router in `routers/` (new domain → new
router included in `api.py`), authenticate with `verify_clerk_token(request)`,
apply a rate-limit policy if it triggers work, add a typed client in
`app-front-end/src/api/`, document in [API.md](API.md).

**Change decision behaviour** — new version under
`resources/config/partner_rules/`, bump `resources/config/active.json`, extend
`tests/evaluation_v2/test_partner_rules_contract.py`.

**Schema change** — new migration; never edit an applied one.

---

## Verification gate

```bash
python3 -m pytest -o asyncio_mode=auto
cd app-front-end && npm run lint && npm test && npm run build
cd web-front-end && npm run lint && npm run build
```

---

## Documentation rules

- Root documents describe **current** behaviour. Update them when behaviour
  changes.
- A decision a future reader would have to reverse-engineer gets an ADR in
  `docs/adr/`.
- **Never edit `docs/archive/`** — it is a historical record, and some of its
  findings are already fixed.
- `docs/scoring-remediation-checklist.md` and `docs/scoring-assessment-audit.md`
  are cited from backend source and tests; keep those paths stable.
- Do not add point-in-time audit or plan files to the repository root. They
  belong in `docs/archive/` from the start.

## Small-instance operation

The API process also runs the pipeline. On ~512 MB instances use
`MAX_CONCURRENT_PIPELINE_CYCLES=1`, `RESUME_AGENT_LOOPS_ON_STARTUP=false`,
`MAX_RESUMED_AGENT_LOOPS=3`. Full guidance in [DEPLOYMENT.md](DEPLOYMENT.md) and
[docs/operations/backend-memory-tuning.md](docs/operations/backend-memory-tuning.md).
