# Deployment

Aethria deploys as three independent units from one repository. Their roots are
fixed at the repository root because the hosting providers are configured to
point at those exact paths.

| Unit | Deploy root | Host | Build |
|---|---|---|---|
| Operator app | `app-front-end/` | Vercel | `npm run build` → `dist/` |
| Marketing site | `web-front-end/` | Vercel | `npm run build` → `dist/` |
| Backend API | `backend/` | Render (or any container host) | `uvicorn api:app` / `backend/Dockerfile` |

> **Do not move `backend/`, `app-front-end/`, or `web-front-end/` into an
> `apps/`, `services/`, or workspace layout** without changing the Vercel and
> Render project settings in the same change. `run.py` also resolves all three
> from the repository root. See [ADR-0007](docs/adr/0007-frozen-deploy-roots.md).

---

## Operator app (`app-front-end`)

| Setting | Value |
|---|---|
| Package manager | npm, using the committed `package-lock.json` |
| Install | `npm ci` |
| Build | `npm run build` (`tsc && vite build`) |
| Output | `dist/` |
| SPA routing | `app-front-end/vercel.json` rewrites non-asset, extensionless routes to `/index.html` |

Required build-time environment (Vite inlines `import.meta.env` at build time —
these must be present in the **build** environment, not just at runtime):

```
VITE_CLERK_PUBLISHABLE_KEY=pk_live_...
VITE_API_URL=https://api.yourdomain.com
```

`main.tsx` throws at startup if `VITE_CLERK_PUBLISHABLE_KEY` is absent, so a
missing key fails the build loudly rather than shipping a blank shell.

## Marketing site (`web-front-end`)

| Setting | Value |
|---|---|
| Install | `npm ci` |
| Build | `npm run build` (`tsc && vite-react-ssg build` — static generation) |
| Output | `dist/` |
| Routing | `web-front-end/vercel.json` rewrites `/home` to `/home.html` and all non-`/api/` routes to `/index.html` |
| Serverless | `web-front-end/api/waitlist.ts` |

Environment:

```
VITE_API_URL=https://api.yourdomain.com
VITE_APP_URL=https://app.yourdomain.com
VITE_CLERK_PUBLISHABLE_KEY=pk_live_...
RESEND_API_KEY=...                       # waitlist notification email
AETHRIA_WAITLIST_NOTIFY_EMAIL=...        # where waitlist notifications go
```

## Backend (`backend`)

Start command:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1
```

`--workers 1` is intentional. The API process also hosts the durable job worker,
the SSE fan-out, and the per-user agent loops; multiple workers in one instance
would multiply memory and duplicate loops. Scale by instance, not by worker
count — and if you run more than one instance, configure the event backplane
(below).

### Required production environment

```
OPENAI_API_KEY=sk-...
EXA_API_KEY=...
FIRECRAWL_API_KEY=...
# DATABASE_URL is the runtime PostgreSQL DSN (the physical host may still be Supabase).
DATABASE_URL=postgresql://...
# Supabase compatibility variables are not required by normal runtime.
CLERK_JWKS_URL=https://<app>.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://<app>.clerk.accounts.dev
ALLOWED_ORIGINS=https://app.yourdomain.com,https://yourdomain.com
ENVIRONMENT=production
```

### Multi-instance safety (fails closed)

With `ENVIRONMENT=production`, the app **refuses to boot** unless one of these is
true:

- `EVENT_BUS_BACKPLANE=postgres` with a working `DATABASE_URL`, so SSE events
  fan out across instances; or
- `ALLOW_PROCESS_LOCAL_STATE=true`, an explicit acknowledgement that this is a
  documented single-instance deployment.

This exists so a second instance can never be added silently, leaving half the
connected clients without live updates.

### Small-instance tuning

The API runs model-heavy pipeline work in-process. On a ~512 MB instance, OOM is
the failure mode to plan for:

```
MAX_CONCURRENT_PIPELINE_CYCLES=1
MAX_CONCURRENT_LOOKUPS=2
RESUME_AGENT_LOOPS_ON_STARTUP=false
MAX_RESUMED_AGENT_LOOPS=3
FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT=500
MALLOC_ARENA_MAX=2
```

With `RESUME_AGENT_LOOPS_ON_STARTUP=false`, users still get cycles from the
`POST /api/agents/trigger` the console issues on login, plus the loop started for
that session. Raise the instance size before raising these numbers. Background:
[docs/operations/backend-memory-tuning.md](docs/operations/backend-memory-tuning.md).

### API docs in production

`/docs` and `/openapi.json` are closed in production unless
`PUBLIC_API_DOCS_ENABLED=1`.

---

## Database

`DATABASE_URL` is the canonical runtime connection. It may point to local
PostgreSQL, Cloud SQL, Supabase Postgres, or another supported PostgreSQL
provider. The application-owned runner applies `db/migrations/` and records
versions in `app_migrations.schema_migrations`; the backend refuses to start
durable workers when that ledger is missing or behind.

`supabase/migrations/` is a compatibility/security overlay for the legacy
Supabase Data API path. It is not the source of truth for canonical runtime
tables. Supabase deployments apply the provider-neutral migrations first and
then the role/RLS overlay required by the Data API. Local/direct PostgreSQL
deployments apply only `db/migrations/` and use explicit tenant predicates in
repositories.

Cloud Build runs the provider-neutral migration runner before Cloud Run deploy.
The `_APPLY_SUPABASE_OVERLAYS` substitution defaults to `true` for the current
Supabase-backed service; set it to `false` for Cloud SQL or another ordinary
PostgreSQL deployment. Local Docker Compose runs only the provider-neutral
runner before the backend starts.

On the first run against the existing Supabase project, the runner performs a
guarded adoption of the already-applied legacy schema into
`app_migrations.schema_migrations`. It does not replay equivalent historical
DDL, delete tenant rows, or rewrite existing data. Only missing additive
migrations and the Supabase RLS overlays are then applied. Historical orphaned
pipeline-state rows are preserved; their new foreign key is installed as
`NOT VALID` so future writes are protected while reconciliation remains an
explicit, separate operation. Later Cloud Build runs are repeatable.

---

## Docker

```bash
docker build -f backend/Dockerfile -t aethria-backend .    # build context = repo root
docker compose up --build                                  # local, reads .env
```

The Dockerfile copies `backend/` **and** `resources/` (the versioned policy files
are read at runtime), installs `backend/requirements.lock`, drops to a non-root
`appuser`, and defines a `/health` healthcheck. `.dockerignore` keeps the
frontends, docs, and local data out of the build context. CI builds this image on
every PR. More in [docs/operations/docker.md](docs/operations/docker.md).

---

## Release checklist

1. CI green on the pull request (all eight jobs).
2. Provider-neutral migrations applied to the target PostgreSQL database.
3. Backend deployed; check `GET /health`, then `GET /api/system/status`, and
   confirm the shared PostgreSQL pool and migration ledger are healthy.
4. Frontends deployed **with** the backend when an API contract changed — the
   console and API are versioned together, not independently.
5. Smoke: sign in, confirm the deal grid paints, dispatch a lookup, confirm the
   SSE stream delivers a `startups_changed` nudge rather than the poll backstop
   filling in.

## Generated artefacts

`dist/` directories are built by Vite on each deploy and are not committed.
Neither is `tsconfig.tsbuildinfo`, `__pycache__/`, or anything under
`backend/data/` (the dev-only file fallback store).
