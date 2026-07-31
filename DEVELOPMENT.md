# Development

Everything needed to get Aethria running locally, change it safely, and prove the
change works.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | CI pins 3.12; `backend/requirements.lock` is resolved against it |
| Node.js | 22 | CI pins 22; both frontends use npm with committed lockfiles |
| PostgreSQL | 16 | Only for running the PostgreSQL contract tests locally |
| Docker | any recent | Optional — containerised backend |

Accounts/keys you will need for the full product: **OpenAI**, **Supabase**,
**Clerk**, and at least one retrieval provider. The chain is
`Exa → Firecrawl → Tavily`, with DuckDuckGo as a keyless last resort: **Exa**
finds candidate companies semantically, **Firecrawl** reads their pages. Set
`EXA_API_KEY` and `FIRECRAWL_API_KEY` for the intended path; `TAVILY_API_KEY` is
optional and only serves the third tier.

---

## 2. Configuration

`.env` at the repository root is the single config file for the backend. It is
loaded by `backend/api.py`, `backend/pipeline_runner.py`, and `run.py`.

```bash
cp .env.example .env
```

`.env.example` is **generated** from `backend/env_config.py`, which is the
canonical registry of every environment variable the backend reads — name, type,
default, section, and description. A test asserts that every `os.getenv` name in
the codebase is registered there and that `.env.example` is in sync, so:

> **Adding a new environment variable means adding an `EnvVar(...)` entry to
> `backend/env_config.py` and regenerating `.env.example`. There is no other
> supported path — CI will fail otherwise.**

### Minimum to run the full pipeline

```bash
OPENAI_API_KEY=sk-...
USE_SUPABASE_STORAGE=1
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
CLERK_JWKS_URL=https://<app>.clerk.accounts.dev/.well-known/jwks.json
TAVILY_API_KEY=...
```

Behaviour when these are missing is deliberate and explicit, never silent:

| Missing | Effect |
|---|---|
| `OPENAI_API_KEY` | Pipeline is skipped immediately with a logged reason |
| `USE_SUPABASE_STORAGE=1` | Falls back to local JSON under `backend/data/` — **dev only**; the production pipeline path and durable job store are unavailable |
| `CLERK_JWKS_URL` | All authenticated routes reject with 401 |
| Active fund thesis | Periodic cycles skip with a warning; on-demand lookup still runs |

### Frontend configuration

Each frontend has its own `.env` (see the committed `.env.example` files):

| Variable | app-front-end | web-front-end |
|---|---|---|
| `VITE_API_URL` | ✔ backend base URL | ✔ |
| `VITE_CLERK_PUBLISHABLE_KEY` | ✔ required at build time | ✔ |
| `VITE_APP_URL` | — | ✔ link target for the app |
| `RESEND_API_KEY` | — | ✔ waitlist serverless function |
| `AETHRIA_WAITLIST_NOTIFY_EMAIL` | — | ✔ waitlist notification target |

The root `.gitignore` keeps `.env` and `.env.*` untracked while allowing every
`.env.example` to remain committed. **Never commit a real secret.**

---

## 3. Install

```bash
pip install -r backend/requirements.lock          # pinned; use this
(cd app-front-end && npm ci)
(cd web-front-end && npm ci)
```

`backend/requirements.txt` holds the loose top-level dependency declarations;
`backend/requirements.lock` is what CI, Docker, and production install. Change
`requirements.txt`, then regenerate the lock.

### Database schema

Apply `supabase/migrations/*.sql` in timestamp order to your Supabase project
(Supabase CLI, the SQL editor, or `psql`). The backend detects unapplied
migrations at startup and logs a `SCHEMA DRIFT` warning naming the missing
columns — the write path tolerates them by dropping fields, so that warning is
the signal that something needs applying.

`supabase/clear_all_tables.sql` resets a **local/dev** database. It is
destructive and is not wired into any automated path.

---

## 4. Running

### Everything at once

```bash
python3 run.py
```

Starts the backend on `:8000`, the operator app on `:3000`, the marketing site on
`:3001`, and — when a tenant is resolvable — the standalone agent process. With
`USE_SUPABASE_STORAGE=1` and no `AETHRIA_AGENT_USER_ID`, `run.py` deliberately
skips the agent subprocess; the API resumes per-user agent loops after login
instead. Logs stream with `[Backend]` / `[App]` / `[Web]` / `[Agents]` prefixes.

### Individually

```bash
# Backend API
cd backend && python3 -m uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Operator app
cd app-front-end && npm run dev

# Marketing site
cd web-front-end && npm run dev

# Agent pipeline only, one tenant
python3 backend/run_system.py --user-id=<clerk_user_id>          # continuous
python3 backend/run_system.py --user-id=<clerk_user_id> --once   # single cycle
```

### Containerised backend

```bash
docker compose up --build      # reads .env, exposes :8000, has a healthcheck
```

Details and caveats in [docs/operations/docker.md](docs/operations/docker.md).

---

## 5. Testing

### Backend

```bash
# From the repository root (pytest.ini sets pythonpath=backend, testpaths=backend/tests)
python3 -m pytest -o asyncio_mode=auto

# Or from backend/
cd backend && python3 -m pytest tests/ -v -o asyncio_mode=auto

# A single area
python3 -m pytest backend/tests/evaluation_v2 -v -o asyncio_mode=auto
```

~190 test modules covering the pipeline contract, scoring engine, partner rules,
identity, jobs, evidence, evaluation, monitoring, security, and API surface.

**PostgreSQL contract tests** need a real database and are skipped without one:

```bash
docker run --rm -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aethria -p 5432:5432 postgres:16
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aethria
psql "$TEST_DATABASE_URL" -c "create role anon; create role authenticated; create role service_role;"
# apply the institutional migrations listed in .github/workflows/ci.yml, then:
cd backend && python3 -m pytest tests/jobs/test_job_repository_postgres.py \
  tests/identity/test_identity_repository_postgres.py -v -o asyncio_mode=auto
```

### Frontends

```bash
cd app-front-end
npm run lint          # eslint, zero warnings tolerated
npm test              # vitest — unit + component
npm run build         # tsc && vite build
npm run check:bundle  # bundle-size budget
npm run test:e2e      # Playwright smoke (needs `npx playwright install chromium`)

cd web-front-end
npm run lint
npm run build
npm run check:bundle
npm run check:marketing
```

### What CI runs

`.github/workflows/ci.yml` on every push to `main` and every pull request:

| Job | Contents |
|---|---|
| `app-frontend` | `npm ci` · `npm audit --omit=dev --audit-level=high` · lint · vitest · build · bundle budget |
| `web-frontend` | same shape, minus unit tests, plus the marketing check |
| `app-frontend-e2e` | Playwright smoke against a locally started dev server |
| `backend-deps` | Install `requirements.lock` · `pip-audit` |
| `backend-import` | `python -c "import api"` — catches import-time breakage |
| `backend-tests` | Full pytest suite |
| `backend-postgres-contracts` | Applies the institutional migrations to a `postgres:16` service and runs the repository contract tests |
| `backend-docker` | Builds `backend/Dockerfile` from the repo root context |

CI runs with `USE_SUPABASE_STORAGE=0`, a placeholder OpenAI key, and
`SKIP_REFERENCE_URL_VERIFY=1`, so tests never make real external calls.

---

## 6. Common development tasks

### Add a scout persona

1. Subclass `Scout` in `backend/scout/base.py`.
2. Add the class to `backend/scout/scouts.py`.
3. Register it in `ScoutEngine.__init__` (`backend/scout/engine.py`).
4. Add the `scout_type` literal to `ScoutInfo.scout_type` in `backend/models.py`.
5. The meta-agent reweighter picks it up automatically.

### Add an API endpoint

1. Put it on the relevant router in `backend/routers/` (create a new router
   module for a new domain and include it in `api.py`). Only cross-cutting
   endpoints belong directly in `api.py`.
2. Authenticate with `verify_clerk_token(request)` and read the tenant from
   `request.state.user_id` — never accept a `user_id` from the client.
3. Apply a rate-limit policy if the route triggers work or mutates settings.
4. Add a typed client function under `app-front-end/src/api/*.ts`.
5. Document it in [API.md](API.md).

### Change decision behaviour

Do **not** edit thresholds in Python. Add a new version under
`resources/config/partner_rules/`, bump `resources/config/active.json`, and
extend `backend/tests/evaluation_v2/test_partner_rules_contract.py`. The
governed path (`/api/settings/policy/preview` → `/publish`) is the runtime
equivalent for per-fund configuration.

### Change the schema

New file in `supabase/migrations/` with a timestamp prefix. Never edit an applied
migration. If the new table or column is exercised by repository code, extend the
PostgreSQL contract tests and add the migration to the CI list in
`.github/workflows/ci.yml`.

### Add an environment variable

Add an `EnvVar(...)` to `backend/env_config.py`, use the generated accessor, and
regenerate `.env.example`. Do not call `os.getenv` for a new name directly.

### Regenerate brand assets

```bash
python3 brand-assets/scripts/generate_motion_blur_hero.py   # writes brand-assets/assets/
node brand-assets/scripts/check-brand-assets.mjs            # asserts the studio invariants
npx -y serve brand-assets -l 4400                           # browse the studio
```

---

## 7. Debugging aids

| Variable | Effect |
|---|---|
| `PARTNER_LLM_DEBUG_LOGS=1` | Log full partner prompts and responses |
| `DEBUG_SCORING=1` | Verbose structured-scoring diagnostics |
| `DEAL_CONTEXT_LOG_PIPELINE=1` | Log the deal-context digest through the pipeline |
| `SKIP_REFERENCE_URL_VERIFY=1` | Skip outbound reference verification (what CI uses) |
| `RESUME_AGENT_LOOPS_ON_STARTUP=false` | Don't resume every tenant's loop at boot |
| `PUBLIC_API_DOCS_ENABLED=1` | Expose `/docs` even in a production-like environment |

`app-front-end/screenshot/` is a Vite harness that renders UI states against mock
data for visual inspection without a live backend:

```bash
cd app-front-end && npx vite --config vite.screenshot.config.ts --port 5181
```

---

## 8. Definition of done

Before opening a pull request:

- [ ] `python3 -m pytest -o asyncio_mode=auto` passes
- [ ] `cd app-front-end && npm run lint && npm test && npm run build` passes
- [ ] `cd web-front-end && npm run lint && npm run build` passes
- [ ] New env vars registered in `backend/env_config.py`, `.env.example` regenerated
- [ ] Schema changes are a new migration, and CI's migration list is updated
- [ ] API changes reflected in [API.md](API.md)
- [ ] Behavioural decisions that future readers would question are captured as an
      ADR in [docs/adr/](docs/adr/)
