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
- **Backend tests require `OPENAI_API_KEY`**: All 4 tests in `backend/tests/` are integration tests that call the OpenAI API. They cannot run without the key. Use `python3 -m pytest tests/ -v` from `backend/`.
- **No database**: Storage uses flat JSON files (`data/startups.json`, `data/settings.json`, `data/portfolio/`). The `data/` dir is gitignored and created on demand.
- **TypeScript checks**: Run `npx tsc --noEmit` in either frontend directory. Both pass cleanly.
- **Builds**: `npx vite build` or `npm run build` in either frontend directory.
- **pytest-asyncio** is needed for the backend test suite (async tests).
