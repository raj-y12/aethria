# Docker — Backend API

Run the FastAPI backend in Docker for local development or ad-hoc deployment. Production uses the same image on Railway; see [deployment.md](deployment.md) for Vercel/Railway roots.

Frontends (`app-front-end`, `web-front-end`) are **not** containerized. Run them with Vite locally or use hosted Vercel builds.

## Prerequisites

- Docker Engine or Docker Desktop
- A repo-root `.env` with backend variables (see [env.md](env.md))

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
```

## Run

Pass secrets at runtime — never bake `.env` into the image:

```bash
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 aethria-backend
```

Or use docker compose (see below).

### Required environment variables

For full pipeline execution, set at minimum:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM calls for scout/reviewer/partner |
| `USE_SUPABASE_STORAGE=1` | Production storage path |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend service-role client |
| `CLERK_JWKS_URL` | JWT verification |

See [env.md](env.md) for optional variables (`SCOUT_MODEL`, `ALLOWED_ORIGINS`, etc.).

### Recommended local Docker settings

These reduce memory use on small machines (same guidance as [AGENTS.md](../AGENTS.md)):

```bash
RESUME_AGENT_LOOPS_ON_STARTUP=false
MAX_CONCURRENT_PIPELINE_CYCLES=1
```

Add them to `.env` or pass with `-e`.

### Local file storage fallback

If `USE_SUPABASE_STORAGE=0`, the backend writes under `backend/data/`. Mount a volume:

```bash
docker run --rm -p 8000:8000 --env-file .env \
  -v "$(pwd)/backend/data:/app/backend/data" \
  aethria-backend
```

Production Docker usage should keep `USE_SUPABASE_STORAGE=1`.

## Docker Compose

From the repo root:

```bash
docker compose up --build
```

Stops with `Ctrl+C` or `docker compose down`.

## Health check

`GET /health` is public (no auth), lightweight, and does not call OpenAI, agents, or Supabase.

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

The Dockerfile and compose file include a built-in healthcheck against this endpoint.

For authenticated deployment diagnostics, use `GET /api/agents/status` (requires Clerk JWT).

## How this relates to Railway

| | Railway (production) | Docker (local) |
|--|----------------------|----------------|
| Build | `backend/Dockerfile` from repo root | Same |
| Image layout | `/app/backend` + `/app/resources` | Same |
| Start command | `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1` | Same |
| Secrets | Railway Variables | `--env-file .env` or compose `env_file` |
| Frontends | Vercel (separate) | Not in this image |

Railway reads `railway.toml` at the repo root for health checks and watch paths.
