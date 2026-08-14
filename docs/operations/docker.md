# Docker — Backend API

Run the FastAPI backend in Docker for local development or ad-hoc deployment. This does **not** replace the current Render deployment; see [DEPLOYMENT.md](../../DEPLOYMENT.md) for Vercel/Render roots.

Frontends (`app-front-end`, `web-front-end`) are **not** containerized. Run them with Vite locally or use hosted Vercel builds.

## Prerequisites

- Docker Engine or Docker Desktop
- A repo-root `.env` with backend variables (see [DEVELOPMENT.md](../../DEVELOPMENT.md))

## Build

Build context is the **repository root** so both `backend/` and `resources/` are included:

```bash
docker build -f backend/Dockerfile -t aethria-backend .
```

The image layout mirrors production:

```
/app/
  backend/     ← WORKDIR; uvicorn runs here
  resources/   ← policy JSON (partner/reviewer/rubric/thesis rules)
  db/          ← provider-neutral PostgreSQL migrations
```

## Run

Pass secrets at runtime — never bake `.env` into the image:

```bash
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 aethria-backend
```

Or use docker compose (see below).

### Local production snapshot protection

The normal compose stack uses the disposable `aethria-postgres-test-data`
volume. The restored production snapshot is intentionally separate and is
started only through `docker-compose.snapshot.yml`, which uses the explicitly
created external volume `aethria-prod-snapshot-data`.

`run.py` detects `aethria_prod_snapshot`, selects the snapshot compose stack,
and verifies `db/snapshots/aethria_prod_snapshot_manifest.json`. It never runs
normal migrations against that database. A manifest mismatch stops startup;
it does not repair or overwrite the snapshot.

The snapshot volume is not removed by normal compose cleanup. To intentionally
replace it, stop the services, create a new backup first, and perform the
restore as a separate operator action. Do not add the backup dump to git.

### Required environment variables

For full pipeline execution, set at minimum:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM calls for scout/reviewer/partner |
| `DATABASE_URL` | Canonical PostgreSQL connection (local, Cloud SQL, Supabase Postgres, or another supported provider) |
| `USE_SUPABASE_STORAGE=1` | Legacy Supabase Data API compatibility routes only |
| `SUPABASE_URL` | Required only by legacy Supabase compatibility routes |
| `SUPABASE_SERVICE_ROLE_KEY` | Required only by legacy Supabase compatibility routes |
| `CLERK_JWKS_URL` | JWT verification |

See [DEVELOPMENT.md](../../DEVELOPMENT.md) for optional variables (`SCOUT_MODEL`, `ALLOWED_ORIGINS`, etc.).

### Recommended local Docker settings

These reduce memory use on small machines (same guidance as [DEPLOYMENT.md](../../DEPLOYMENT.md)):

```bash
RESUME_AGENT_LOOPS_ON_STARTUP=false
MAX_CONCURRENT_PIPELINE_CYCLES=1
```

Add them to `.env` or pass with `-e`.

### Compatibility file storage fallback

Only run without `DATABASE_URL` in explicit non-production compatibility mode. In
that mode, legacy local writes go under `backend/data/`. Mount a volume:

```bash
docker run --rm -p 8000:8000 --env-file .env \
  -v "$(pwd)/backend/data:/app/backend/data" \
  aethria-backend
```

Production Docker usage should provide `DATABASE_URL`; it may point to Supabase
Postgres, but the canonical runtime is not tied to the Supabase Data API.

## Docker Compose

From the repo root:

```bash
docker compose up --build
```

Stops with `Ctrl+C` or `docker compose down`.

The separate snapshot stack is selected automatically by `run.py` when the
local `DATABASE_URL` names `aethria_prod_snapshot`. For direct inspection:

```bash
docker volume create aethria-prod-snapshot-data
docker compose -f docker-compose.snapshot.yml up -d postgres
```

Do not run `docker compose down -v` against the snapshot stack unless you have
an external backup and explicitly intend to remove that snapshot volume.

## Health check

`GET /health` is public (no auth), lightweight, and does not call OpenAI, agents, or Supabase.

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

The Dockerfile and compose file include a built-in healthcheck against this endpoint.

For authenticated deployment diagnostics, use `GET /api/agents/status` (requires Clerk JWT).

## How this differs from Render

| | Render (current) | Docker (local) |
|--|------------------|----------------|
| Deploy root | `backend/` | Image: `/app/backend` |
| Policy JSON | Full repo cloned; `resources/` on disk | Copied into image at `/app/resources` |
| Start command | `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1` | Same |
| Secrets | Render dashboard env | `--env-file .env` or compose `env_file` |
| Frontends | Vercel | Not in this image |

Render configuration is unchanged by this Docker support.

## Follow-up (not implemented)

- CI/CD to build and push images
- Render Docker deploy
- Frontend containerization
- Kubernetes
