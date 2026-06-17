# AGENTS.md — Aethria

AI-powered venture capital deal-flow platform. Autonomously discovers, evaluates, and makes investment decisions on startups, scoped per user by a "fund thesis."

---

## Architecture

### Pipeline (ordered stages, per user)

```
ScoutEngine → ReviewerEngine → PartnerEngine → PortfolioEngine → MetaAgent
```

Each stage is async, user-scoped, and gated by the active **FundThesis**. No thesis = pipeline doesn't run.

### Request paths

- **Periodic pipeline**: `POST /api/agents/trigger` → enqueued in `_agent_queue` → `run_one_pipeline_cycle(user_id)`
- **On-demand lookup**: `POST /api/startups/lookup` → `_lookup_queue` → `run_on_demand_lookup(user_id, company_name)`
- **Frontend reads**: `GET /api/startups`, `GET /api/memo/:id`, `GET /api/settings`, etc.

### Multi-tenancy

Every storage read/write and engine instantiation requires an explicit `user_id` (Clerk JWT `sub`). `require_user_id()` / `TenantContext` enforce this at construction time — no implicit global tenant.

---

## Key Components

### Backend (`backend/`)

| Module | Role |
|---|---|
| `scout/` | 4 scout personas (Market-Driven, Builder/Technical, Pain-Point, Contrarian). Each uses OpenAI + Tavily web search to discover **real** companies. |
| `reviewer/` | 3 reviewer personas (Default, Skeptical, Opportunist). Score scouts against fund thesis (market/product/technical/execution/defensibility, 1–10). |
| `partner/` | Rule-based decision engine (INVEST / PASS / MONITOR) using versioned rules in `resources/config/partner_rules/v1.json`. LLM only for edge cases. |
| `portfolio/` | Tracks accepted (YES) companies: execution, signals, feedback, health checks. |
| `meta/` | Self-optimization: analyses pipeline outcomes, mutates scout prompts (`mutator.py`), reweights scouts (`reweighter.py`), calibrates reviewer thresholds (`calibrator.py`). |
| `fund_thesis.py` | Per-user investment mandate. `get_active_thesis()` bootstraps a default on first access. Gates the entire pipeline. |
| `pipeline_runner.py` | Orchestrates a single pipeline cycle or on-demand lookup for one user. |
| `api.py` | FastAPI app. Handles auth (Clerk JWT), two async queues (agent + lookup), all REST endpoints. |
| `models.py` | Pydantic models: `Startup`, `ScoutInfo`, `ReviewInfo` (`SingleReview` × 3), `PartnerInfo`. |
| `supabase_storage.py` | Startup CRUD against Supabase `startups` table. Row-level upserts; no full-table rewrites. |
| `supabase_doc_store.py` | Key-value JSON tables (settings, meta state, etc.). |
| `auth_clerk.py` | RS256 JWT verification via Clerk JWKS. Sets `request.state.user_id`. |
| `tenant_context.py` | `TenantContext` dataclass + `require_user_id()`. Blocks execution if user_id is missing. |
| `memory.py` | `DealMemory` — tracks seen startups to avoid re-scouting within a session. |

### Frontend (`app-front-end/src/`)

| Path | Role |
|---|---|
| `App.tsx` | Auth shell: Clerk sign-in gate, token readiness check, route handling. Triggers agents on mount. |
| `components/WorkGrid.tsx` | Primary deal-flow grid — lists startups with status badges. |
| `components/InvestmentMemoContent.tsx` | Renders investment memos. |
| `components/SystemIntelligence.tsx` | Live intelligence feed / system panel. |
| `settings/SettingsPage.tsx` | Fund thesis, agent toggles, cost budget, fund identity. |
| `hooks/useSystemData.ts` | Main data-fetching hook (startups, signals, meta). |
| `api/` | Typed API clients: `startups.ts`, `agents.ts`, `fundThesis.ts`, `settings.ts`, etc. |

---

## Coding Rules

### Python (backend)

- **Always pass `user_id` explicitly.** Never use a global/implicit tenant. Call `require_user_id()` at the top of any engine constructor or pipeline function.
- **Pydantic models for all data shapes.** `models.py` is the source of truth. Use `.model_dump()` / `.model_validate()`.
- **Supabase storage is row-level.** Use upsert patterns; never delete+rewrite a full table for one user's data.
- **LLM calls are expensive.** Scout/reviewer/partner prompts must be minimal. Partner engine is rule-based by default — only call LLM for the triggers defined in `partner_rules/v1.json`.
- **Partner rules are versioned JSON.** Logic changes go in `resources/config/partner_rules/`. Don't hardcode thresholds in Python.
- **Reference validation is mandatory.** Startups without verifiable external references are pruned. Don't skip `reference_validation`.
- **Settings are user-scoped via Supabase.** Load with `load_settings(user_id)`. Never read a global config file for per-user settings.
- **Async throughout.** Pipeline engines are `async`. Use `asyncio.gather()` for parallel stages where safe.

### TypeScript (frontend)

- **Auth token via Clerk.** All API calls must go through `api/auth.ts` (`setTokenGetter` / `getToken`). Never bypass auth.
- **TanStack Query for data fetching.** Use existing hooks in `hooks/` before writing new fetch logic.
- **No direct `fetch` calls outside `api/`.** All backend communication lives in typed client modules under `src/api/`.
- **Framer Motion for animations.** Don't introduce other animation libraries.

---

## Important Constraints

1. **Fund thesis is a hard gate.** `get_active_thesis()` must succeed before any pipeline stage runs. Missing or incomplete thesis = skip cycle, log warning, return.
2. **`USE_SUPABASE_STORAGE=1` is required for pipeline execution.** Local file storage is a fallback for dev only; the pipeline will not run without Supabase.
3. **`OPENAI_API_KEY` is required.** Missing key = pipeline skipped immediately (no silent failures).
4. **All Supabase operations use the service role client** (`get_service_client()`). The frontend never touches Supabase directly.
5. **Per-user cost budgets** (`CostController`) can be enabled in settings. Respect budget gates in engines — don't bypass `cost_controller` checks.
6. **MetaAgent runs on a daily interval** (`META_AGENT_INTERVAL_SECONDS=86400`). It mutates prompts and reweights scouts — any prompt changes must be reflected in `prompt_version` hashes via `utils/prompt_version.py`.
7. **Supabase migrations must be applied** before new tables/columns are used. Migrations live in `supabase/migrations/`.

---

## Development Guidelines

### Environment variables (`.env` at project root)

```
OPENAI_API_KEY=
USE_SUPABASE_STORAGE=1
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
CLERK_JWKS_URL=
CLERK_ISSUER=          # optional
SCOUT_MODEL=gpt-5-nano
REVIEWER_MODEL=gpt-5-nano
PARTNER_USE_LLM=true
META_AGENT_ENABLED=true
```

### Render / small instances (memory)

The API runs scout/reviewer/partner pipelines in-process. On Render Starter (~512MB), OOM is common if many users have agents enabled or cycles overlap.

Recommended production env:

```
MAX_CONCURRENT_PIPELINE_CYCLES=1
RESUME_AGENT_LOOPS_ON_STARTUP=false
MAX_RESUMED_AGENT_LOOPS=3
FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT=500
```

Users with agents enabled still get cycles via `POST /api/agents/trigger` on login and the persistent loop started for that session. Upgrade the Render instance if you need many simultaneous agent loops after cold start.

### Running locally

```bash
# Backend (from repo root)
python run.py --user-id=<clerk_user_id>

# Or directly
python backend/run_system.py --user-id=<clerk_user_id>

# API server
cd backend && uvicorn api:app --reload

# Frontend
cd app-front-end && npm install && npm run dev
```

### Adding a new scout persona

1. Subclass `Scout` in `backend/scout/base.py`.
2. Add it to `backend/scout/scouts.py`.
3. Register it in `ScoutEngine.__init__` in `backend/scout/engine.py`.
4. Add the `scout_type` literal to `ScoutInfo.scout_type` in `models.py`.

### Adding a new API endpoint

1. Add route to `backend/api.py`.
2. Protect with `verify_clerk_token(request)` — sets `request.state.user_id`.
3. Add typed client function in the relevant `app-front-end/src/api/*.ts` file.

### Modifying partner decision logic

Edit `resources/config/partner_rules/v1.json`. Python reads this at runtime via `core/policy_resolver.py`. Increment `"version"` in the JSON when making breaking changes.

### Schema / Supabase changes

Always create a new migration file in `supabase/migrations/` with the timestamp prefix. Never modify existing migration files.
