# Aethria Monorepo

Aethria is an autonomous dealflow operating system for venture teams.

## Current Layout

The current deploy roots are intentionally unchanged:

- `backend/`: FastAPI API, Scout/Reviewer/Partner/Portfolio agents, Meta-Agent, storage adapters.
- `app-front-end/`: authenticated product UI for pipeline operations and memo workflows.
- `web-front-end/`: public marketing and access-request experience.
- `supabase/`: SQL/migration assets for production persistence.

Supporting material lives outside the deploy roots:

- `docs/`: product, architecture, API, environment, deployment, and pitch documentation.
- `docs/pitch/`: investor narrative, deck drafts, and pitch collateral.
- `docs/design/brand-assets/`: brand asset source files and generated brand imagery.
- `resources/`: runtime configuration and contracts, including partner rules.
- `packages/`: shared or experimental package work that is not a current deploy root.
- `scripts/`: repository maintenance scripts.

## Runtime Topology

- Backend API: `http://localhost:8000`
- App frontend: `http://localhost:3000`
- Web frontend: `http://localhost:3001`

Run all services together:

```bash
python3 run.py
```

Run each service independently:

```bash
# Backend
cd backend
python3 -m uvicorn api:app --reload --host 0.0.0.0 --port 8000

# App frontend
cd app-front-end
npm run dev

# Web frontend
cd web-front-end
npm run dev
```

## Key Product Behavior

- Authentication uses Clerk JWTs; all private API routes require `Authorization: Bearer <token>`.
- The app triggers pipeline execution on load with `POST /api/agents/trigger`.
- Deal intelligence is staged: Scout -> Reviewer -> Partner -> Portfolio.
- Memo rendering is progressive: `/api/startups/{id}/memo` can return `generating` plus partial content.
- On-demand lookup can be queued from the app (`POST /api/startups/lookup`) and tracked by lookup ID.

## Storage Model

- **Production path**: Supabase-backed, per-user data (required for agent-triggered API flow).
- **Local fallback path**: file-backed JSON storage under `backend/data/`.

Core user-scoped artifacts include settings, startups, escalations, portfolio decisions, signals, and meta-agent outputs.

## Environment Notes

See [docs/env.md](docs/env.md) for service-specific environment variables.

See [docs/deployment.md](docs/deployment.md) for current Vercel and Render deploy-root assumptions.

## Developer Commands

```bash
# App/frontend typecheck
cd app-front-end && npx tsc --noEmit

# Web/frontend typecheck
cd web-front-end && npx tsc --noEmit

# Backend tests (requires OPENAI_API_KEY)
cd backend
python3 -m pytest tests/ -v -o asyncio_mode=auto
```
