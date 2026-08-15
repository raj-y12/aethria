# Development

Everything needed to get Aethria running locally, change it safely, and prove the
change works.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | CI pins 3.12; `backend/requirements.lock` is resolved against it |
| Node.js | 22 | CI pins 22; both frontends use npm with committed lockfiles |
| PostgreSQL | 16 | Local runtime database and PostgreSQL contract tests |
| Docker | any recent | Optional — containerised backend |

Accounts/keys you will need for the full product: **OpenAI**, **Clerk**, and at
least one retrieval provider. Supabase is not required for local runtime. The chain is
`Exa → Firecrawl`, with DuckDuckGo as a keyless last resort: **Exa** finds
candidate companies semantically, **Firecrawl** reads their pages. Set both
`EXA_API_KEY` and `FIRECRAWL_API_KEY`.

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
DATABASE_URL=postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test
CLERK_JWKS_URL=https://<app>.clerk.accounts.dev/.well-known/jwks.json
EXA_API_KEY=...
FIRECRAWL_API_KEY=...
```

Behaviour when these are missing is deliberate and explicit, never silent:

| Missing | Effect |
|---|---|
| `OPENAI_API_KEY` | Pipeline is skipped immediately with a logged reason |
| `DATABASE_URL` (or `SUPABASE_DB_URL`) | Durable jobs and canonical repositories are unavailable; accepted-work endpoints fail closed |
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
# Optional only for isolated legacy Supabase compatibility tests/tools:
pip install -r backend/requirements-legacy.txt
(cd app-front-end && npm ci)
(cd web-front-end && npm ci)
```

`backend/requirements.txt` holds the loose top-level dependency declarations;
`backend/requirements.lock` is what CI, Docker, and production install. Change
`requirements.txt`, then regenerate the lock.
The optional `backend/requirements-legacy.txt` is not installed into the
production image; it exists only for compatibility tests and historical tools.

### Database schema

Historical `supabase/migrations/*.sql` files are retained for reconciliation
and live-database history. They are not the runtime migration ledger.

The post-Supabase schema is being migrated to ordinary PostgreSQL. The
application-owned runner is `backend/db/migration_runner.py`; it applies
timestamped files from `db/migrations/` and records them in
`app_migrations.schema_migrations`. `db/baseline/` is reserved for the
reviewed provider-neutral schema snapshot. Do not edit historical files under
`supabase/migrations/` or use them as the future migration ledger.

Startup persistence uses `public.startups` as its sole canonical runtime
authority. `startup_id_aliases` resolves approved legacy identifiers from the
historical reconciliation. The live Supabase `portfolio_startups` table is
preserved historical data only, is not created by provider-neutral migrations,
and is not read or written by normal runtime code. Live deletion or archival is
an operational decision outside this migration.

Fund-thesis reads used by periodic evaluation are verified against the
provider-neutral PostgreSQL contract in `db/migrations/`, through the shared
asyncpg pool and `backend/fund_thesis_repository.py`. The repository reads the
active version, version history, embeddings, missing-embedding worklist, and
pipeline links with explicit tenant predicates. Thesis creation, activation,
and embedding backfill use the bounded canonical repository paths. Policy
publication uses `FundIntelligenceRepository` and the
`governed_policy_versions` table; historical policy compatibility remains
separately scoped for the 5D cleanup.

`supabase/clear_all_tables.sql` resets a **local/dev** database. It is
destructive and is not wired into any automated path.

---

## 4. Running

### Everything at once

```bash
python3 run.py
```

Starts the backend on `:8000`, the operator app on `:3000`, the marketing site on
`:3001` with Uvicorn auto-reload enabled, and — when a tenant is resolvable — the standalone agent process. With
no `AETHRIA_AGENT_USER_ID`, `run.py` deliberately skips the agent subprocess;
the API resumes per-user agent loops after login instead. Logs stream with
`[Backend]` / `[App]` / `[Web]` / `[Agents]` prefixes. When `DATABASE_URL`
targets `127.0.0.1:15432`, it also starts the local PostgreSQL Compose service,
waits for it, and applies the provider-neutral migrations to the local database
before starting the backend. When the database is `aethria_prod_snapshot`, this
is the mutable working copy; reset it from the immutable golden backup with
`python3 run.py --reset-local-snapshot`. On macOS, when the active Docker
context is `colima`, it starts Colima automatically if the Docker daemon is
unavailable. It stops that database container on exit only when it started it;
already-running database containers are left running. The launcher prints a
static header with the ports and current snapshot, followed by normal terminal
logs.

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

**PostgreSQL contract tests** use ordinary PostgreSQL 16 and the portable
migrations under `db/migrations/`; they do not use Supabase migrations or
compatibility roles:

```bash
docker-compose up -d postgres
until docker-compose exec -T postgres pg_isready -U aethria -d aethria_test; do sleep 1; done
export TEST_DATABASE_URL=postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test
cd backend && python3 scripts/migrate_postgres.py
cd ..
python3 -m pytest -o asyncio_mode=auto -q \
  backend/tests/memory/test_repository_postgres.py \
  backend/tests/settings/test_settings_repository_postgres.py \
  backend/tests/user_state/test_repository_postgres.py
```

The jobs, identity, authority, fund-intelligence, security, and legacy-table
contract tests run against the provider-neutral schema. Do not apply historical
`supabase/migrations/` files to this contract database as a workaround.

Inspect the application migration ledger with:

```bash
docker-compose exec -T postgres psql -U aethria -d aethria_test -c \
  "select version, name from app_migrations.schema_migrations order by version"
```

Reset the local test database with:

```bash
docker-compose down -v
```

The password above is local-only test data and must never be reused for
production configuration.

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

Rate limits, short-lived locks, and Meta/Portfolio schedule claims use
application-owned asyncpg repositories over the shared PostgreSQL pool. Do not
add Supabase RPCs or synchronous database calls to these paths. Lock release
requires the opaque owner token returned by acquisition; schedule claiming is
separate from durable `agent_jobs` leasing.

### Change the schema

For provider-neutral direct PostgreSQL work,
add a new timestamped file in `db/migrations/` and extend the PostgreSQL
contract tests. Never edit an applied migration. Historical Supabase migrations
remain immutable source material.

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
