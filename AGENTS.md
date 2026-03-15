# Aethria

Autonomous DealFlow OS for venture capital — AI-powered pipeline: Scout → Reviewer → Partner → Portfolio.

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Start command | Notes |
|---------|------|---------------|-------|
| Backend API | 8000 | `cd backend && python3 -m uvicorn api:app --reload --host 0.0.0.0 --port 8000` | FastAPI; no database needed (flat JSON files in `data/`) |
| App frontend | 3000 | `cd app-front-end && npm run dev` | Vite + React; proxies `/api` → backend |
| Web frontend | 3001 | `cd web-front-end && npm run dev` | Vite + React; marketing site |
| All-in-one | — | `python3 run.py` (repo root) | Starts all services + AI agents |

### Gotchas

- **No ESLint config**: Both frontends declare `npm run lint` but have no `eslint.config.js` file. ESLint 9.x will error. This is a pre-existing repo gap.
- **`python` vs `python3`**: The environment has `python3` but no `python` symlink. Always use `python3`.
- **Backend tests require `OPENAI_API_KEY`**: All 4 tests in `backend/tests/` are integration tests that call the OpenAI API. They cannot run without the key.
- **pytest asyncio mode**: Tests are async but lack `@pytest.mark.asyncio` decorators. Run with: `python3 -m pytest tests/ -v -o asyncio_mode=auto` from `backend/`.
- **No database**: Storage uses flat JSON files (`data/startups.json`, `data/settings.json`, `data/portfolio/`). The `data/` dir is gitignored and created on demand.
- **TypeScript checks**: Run `npx tsc --noEmit` in either frontend directory. Both pass cleanly.
- **Builds**: `npx vite build` or `npm run build` in either frontend directory.
- **pytest-asyncio** is needed for the backend test suite (async tests).
- **Agents and user ID**: User ID is always dynamic (no default in code). With Supabase, run agents with `python3 backend/run_system.py --user-id=<clerk_user_id>`. For `python3 run.py`, set `AETHRIA_AGENT_USER_ID` in `.env` so the all-in-one launcher passes it. You can remove `AETHRIA_DEFAULT_USER_ID` from `.env`.

### Deployment (e.g. Render) — agents must have these env vars

On Render (or any host where only the **backend** runs, no separate agents process), agents run via the API: when a user loads the app, `POST /api/agents/trigger` enqueues a pipeline run and a background worker in the same process runs it. For that to work, set these **backend** environment variables in the Render dashboard:

| Variable | Required for agents | Notes |
|----------|---------------------|--------|
| `USE_SUPABASE_STORAGE` | **Yes** | Set to `1`, `true`, or `yes`. If unset, trigger returns "skipped" (supabase_required) and no pipeline runs. |
| `OPENAI_API_KEY` | **Yes** | If unset, the worker skips the pipeline cycle (logs "OPENAI_API_KEY missing, skipping pipeline"). |
| `SUPABASE_URL` | **Yes** | Backend and pipeline use this for storage. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Yes** | Backend uses service role for all Supabase access. |
| `CLERK_JWKS_URL` | **Yes** (auth) | Required for JWT verification; without it the API will 401. |

Optional: `CLERK_ISSUER`, `ALLOWED_ORIGINS` (comma-separated), `SCOUT_MODEL`, `REVIEWER_MODEL`, etc.

**Debugging**: `GET /api/agents/status` (after signing in) returns `worker_ready`, `supabase_configured`, and `openai_configured` so you can see what’s missing on the server.

### Data written to DB (Supabase, all per user when `USE_SUPABASE_STORAGE=1`)

| Data | Table / store | How it’s user-scoped |
|------|----------------|----------------------|
| **Settings** | `settings` (doc) | `(user_id, key)` with key = user_id; load/save pass `user_id`. |
| **Startups** (discoveries, reviews, partner decision, human_resolution) | `startups` | `SupabaseStartupsStorage(client, user_id)`; every read/write uses `user_id`. |
| **Escalations** | Derived from startups | Same as startups; resolve writes `human_resolution` on that user’s startup via `_get_storage(request)`. |
| **Decisions** (advance/pass/hold + reasoning) | `portfolio_decisions` (list) | `list_get_all` / `list_upsert` use run context `user_id` (API sets it; pipeline sets it). |
| **Portfolio positions, rejections, watchlist, signals, agent_metrics** | `portfolio_*` (list) | Same as decisions; portfolio store uses run context. |
| **Memory, meta_* (prompt library, weights, calibration, mutation_log, reports), analytics_sector_concentration, serp_usage, portfolio_budgets** | Doc/list tables | All use run context (or explicit `user_id` where added); pipeline and API set run context so writes are per user. |

Run context: API calls `set_run_user_id(request.state.user_id)` after auth; pipeline calls `set_run_user_id(user_id)` at start of each cycle. So all doc/list access during a request or pipeline run is for that user.

### Backpressure and ramp-up

- **Scouts**: If `unreviewed > SCOUT_BACKPRESSURE_THRESHOLD` (default 10), the scout cycle is skipped so reviewers can catch up. Set `SCOUT_BACKPRESSURE_THRESHOLD` in env to tune.
- **Reviewers**: If `undecided > REVIEWER_BACKPRESSURE_THRESHOLD` (default 10), the review cycle is skipped so partners can catch up. When `unreviewed > REVIEWER_RAMP_THRESHOLD` (default 5), reviewers process up to `REVIEWER_RAMP_BATCH_MAX` (default 5) per cycle instead of `batch_size` (1). Set env vars to tune.
- **Partners**: Process up to `PARTNER_BATCH_MAX` (default 20) undecided per cycle so cycles stay bounded; when backlog is high they still make progress every interval.
