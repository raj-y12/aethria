# AGENTS.md — repository contract

The shared contract for any coding agent or human contributor. Claude Code
orchestration lives in [CLAUDE.md](CLAUDE.md). Deeper reading:
[ARCHITECTURE.md](ARCHITECTURE.md) · [API.md](API.md) ·
[DEVELOPMENT.md](DEVELOPMENT.md) · [DEPLOYMENT.md](DEPLOYMENT.md) ·
[CONTRIBUTING.md](CONTRIBUTING.md) · [docs/adr/](docs/adr/)

## What this is

Aethria is a multi-tenant, AI-driven venture deal-flow platform. It discovers
startups, evaluates them against a per-user **fund thesis**, decides
INVEST / PASS / MONITOR, and escalates uncertain cases to a human.

`ScoutEngine → ReviewerEngine → PartnerEngine → PortfolioEngine → MetaAgent`

Every stage is async, scoped to one `user_id`, and gated by the active fund
thesis. No thesis, no periodic pipeline.

## Non-negotiable invariants

Breaking one is a bug, not a trade-off. Each has an ADR in `docs/adr/`.

1. **Explicit tenancy.** Every storage call and engine constructor takes an
   explicit `user_id`; call `require_user_id()` (`backend/tenant_context.py`) at
   the top. Never read a tenant from a request body or a global. (ADR-0001)
2. **Fund thesis gates the periodic pipeline.** `get_active_thesis()` must
   succeed, else log a warning and return. On-demand lookup is mandate-aware but
   never thesis-blocked.
3. **Decision policy is versioned data.** Thresholds live in
   `resources/config/partner_rules/`, selected by `resources/config/active.json`.
   Never hardcode a threshold in Python. (ADR-0002)
4. **Row-level storage.** Targeted upserts only; never delete-and-rewrite a
   tenant's rows. The frontend never touches Supabase. (ADR-0003)
5. **Fail closed.** Missing thesis, ambiguous identity, thin evidence, or an
   unconfigured dependency produces a *named* block — never a plausible guess.
   (ADR-0010)
6. **Configuration is registered.** New env var → `EnvVar(...)` in
   `backend/env_config.py` → regenerate `.env.example`. A bare `os.getenv` for an
   unregistered name fails CI. (ADR-0008)
7. **Migrations are append-only.** New timestamped file in
   `supabase/migrations/`. Never edit an applied migration.
8. **LLM calls are the dominant cost.** Respect `CostController` budget gates.
   No model call where a rule works. (ADR-0009)
9. **Prompt versions track prompt changes** via `backend/utils/prompt_version.py`.
10. **Production requires Supabase.** `USE_SUPABASE_STORAGE=1`; the local JSON
    store is dev only.

## Structure and entry points

```
run.py                    Dev launcher — backend :8000, app :3000, web :3001
backend/                  FastAPI service, pipeline, canonical layer
app-front-end/            Operator SPA (React + Vite + Clerk + TanStack Query)
web-front-end/            Marketing site (React + vite-react-ssg, Vercel)
packages/product-chrome/  Source-only shared React chrome, used by both frontends
resources/config/         Versioned decision policy, rubrics, thesis templates
supabase/migrations/      Append-only SQL
.github/workflows/ci.yml  The authoritative definition of "green"
```

| Surface | Run |
|---|---|
| Everything, locally | `python3 run.py` |
| Backend API (`backend/api.py:app`) | `cd backend && python3 -m uvicorn api:app --reload --port 8000` |
| Pipeline worker | `python3 backend/run_system.py --user-id=<clerk_user_id> [--once]` |
| Frontends | `cd app-front-end` \| `web-front-end` then `npm run dev` |
| Container | `docker compose up --build` (`backend/Dockerfile`, context = repo root) |

Backend layout: `scout/ reviewer/ partner/ portfolio/ meta/` (pipeline stages),
`pipeline_runner.py` + `pipeline_{execution,state,concurrency}.py`, `routers/`
(all new endpoints), `jobs/` (durable Postgres job store, ADR-0005), and the
canonical layer — `identity/ evidence/ evaluation_v2/ decisions/ monitoring/
fund_intelligence/ triage/ outcomes/ ingest/ authority/ services/scoring/` —
behind `RolloutMode` (ADR-0006). Module-by-module detail is in ARCHITECTURE.md.

Frontend layout (`app-front-end/src/`): `api/` (typed clients — **the only place
`fetch` is allowed**), `hooks/` (TanStack Query — check before writing new fetch
logic), `lib/` (pure, unit-tested logic), `components/ pages/ settings/ admin/`,
`design-system/` (contract in `app-front-end/DESIGN_SYSTEM.md`).

## Architecture boundaries

- The frontend never talks to Supabase; it calls the backend API only.
- Only `src/api/` may call `fetch`. Components use hooks.
- Engines never read a tenant from ambient state — `user_id` is a parameter.
- Thresholds are data in `resources/config/`, not code in `backend/`.
- `packages/product-chrome/` must not import app-specific modules.
- Do not move `backend/`, `app-front-end/`, or `web-front-end/` into an `apps/`
  or workspace layout without updating Vercel, the container host, and `run.py`
  in the same change.

## Commands

**npm** for both frontends (`npm ci` in CI, per-app lockfile, no root workspace —
there is no root `package.json`); **pip** for the backend (`requirements.txt` for
dev, `backend/requirements.lock` is what CI installs). Node 22, Python 3.12.

### Verification gate

Mirrors `.github/workflows/ci.yml`. Run all of it before calling work done.

```bash
python3 -m pytest -o asyncio_mode=auto      # root; pytest.ini sets pythonpath/testpaths
cd app-front-end && npm run lint && npm test && npm run build && npm run check:bundle
cd web-front-end && npm run lint && npm run build && npm run check:bundle && npm run check:marketing
```

Also available: `npm run test:e2e` (Playwright; needs `npx playwright install
chromium`), and Postgres contract tests — `docker run --rm -e
POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aethria -p 5432:5432 postgres:16`, then
`cd backend && python3 -m pytest tests/jobs/test_job_repository_postgres.py -v -o
asyncio_mode=auto`. CI additionally runs a dependency audit, `python -c "import
api"`, and a Docker build — expect those to be what fails if you touch
dependencies, migrations, or `backend/Dockerfile`.

## Conventions

**Python** — `require_user_id()` at the top of engines and pipeline functions;
Pydantic models for all data shapes; enums for states, modes, and block reasons
(no free-text status strings); async throughout, `asyncio.to_thread` for blocking
I/O; `load_settings(user_id)`, never a global config for per-user data; log the
named reason whenever work is skipped; startups without verifiable external
references are pruned (`remove_startups_without_references`).

**TypeScript** — backend calls only through `src/api/` clients, tokens from
`api/auth.ts`; TanStack Query via existing hooks; Framer Motion only (do not add
another animation library); named design tokens only, no raw hex or arbitrary
pixel spacing; ESLint `--max-warnings 0`, a warning is a failure.

**SQL** — one new timestamped migration per change, RLS included. If repository
code exercises it, add it to the CI list in `.github/workflows/ci.yml` and extend
the Postgres contract tests.

## Testing

Backend tests live in `backend/tests/`, mirroring the module layout; new
behaviour needs a test in the matching subdirectory. A bug fix starts with a
failing test that reproduces it. Decision-behaviour changes must extend
`backend/tests/evaluation_v2/test_partner_rules_contract.py`. Frontend: pure
logic in `src/lib/` with a Vitest test; component tests only for behaviour, not
markup. Never weaken or delete a test to make a change pass — if a test is
genuinely wrong, say why before changing it.

## Security and data

- The tenant comes from the verified Clerk JWT via `request.state.user_id` —
  never from a request body, query string, or global.
- Authenticate every new endpoint with `verify_clerk_token(request)`; add a
  rate-limit policy if it triggers work.
- Never commit secrets. `.env` is ignored; `.env.example` is generated from
  `backend/env_config.py`.
- Never log API keys, JWTs, or request bodies containing user data.
- User text reaching an LLM passes through `backend/security/` prompt safety.
- RLS policies ship with every migration adding a tenant-scoped table. Never
  edit an applied migration, even to fix a typo — write a follow-up.

## Preserve contracts

Public interfaces. Changing one is a deliberate, announced act, never a side
effect of a refactor: **HTTP API** shapes in [API.md](API.md) (fields may be
added; never renamed, retyped, or removed without updating API.md and the typed
client in the same change) · **SSE events** on `GET /api/stream` · **persisted
shapes** in Supabase and the job store · **policy files** in `resources/config/`
(add a version, never mutate a published one) · **enum values** reaching the
database or frontend (add; never repurpose).

## Repository navigation (Graphify)

`graphify-out/` holds a generated knowledge graph. Prefer it over broad grep
sweeps when orienting: `graphify query "<question>"`, `graphify path "<A>" "<B>"`,
`graphify explain "<concept>"`. `GRAPH_REPORT.md` only for broad architecture
review. **It is a hint, not evidence — verify anything load-bearing against the
source file.** Refresh with `scripts/update_graph.sh`; see CLAUDE.md for when.

## Codex: bounded implementation worker

Codex operates here as an **implementation and review worker**, not as an
autonomous agent. [CLAUDE.md](CLAUDE.md) is the controlling orchestration
policy; where this section and a delegated task disagree, the task must be
narrower, never broader.

**Scope discipline.** Do exactly what the task specifies. Do not widen scope, and
do not do unrelated cleanup, reformatting, renaming, or "while I was in there"
improvements — the repository prohibits those regardless of who makes them.
Every changed line must trace to the task.

**No unsupported architectural decisions.** Do not introduce a new module,
dependency, abstraction, data model, or public interface unless the task
explicitly calls for it. Do not decide product behaviour — thresholds, block
reasons, schema migration strategy, and API field removals are not the worker's
call.

**Stop and escalate** when requirements are ambiguous, when the task conflicts
with an invariant above, or when doing the work correctly requires a decision the
task does not authorise. Report the ambiguity; do not resolve it by guessing.

**Testing is part of the task, not a follow-up.** Produce the tests the task
requires, run them, and report the actual output. Never weaken, skip, or delete
an existing test to make a change pass — if a test appears wrong, stop and say
why.

**No automatic commits.** Do not commit, push, tag, branch, merge, or rebase
unless explicitly instructed. Leave the work in the working tree.

**Report** the files changed, the commands run with their real output, anything
deliberately not done, and any assumption made. A summary claiming success is not
evidence of success — the diff and the command output are.

## Definition of done

1. The verification gate passes and you have seen the output — not assumed it.
2. New behaviour has a test; a bug fix has a test that failed before the fix.
3. No invariant above is broken.
4. Docs describing changed behaviour are updated in the same change; root
   documents describe *current* behaviour.
5. A decision a future reader would have to reverse-engineer has an ADR.
6. `.env.example` regenerated if an env var was added.
7. The diff contains only changes that trace to the request.

## Prohibited

Broad refactors unrelated to the task, or reformatting adjacent code · editing
`docs/archive/` (historical record) · point-in-time audit or plan files in the
repository root (they belong in `docs/archive/` from the start) · moving
`docs/scoring-remediation-checklist.md` or `docs/scoring-assessment-audit.md`
(cited from source and tests) · editing an applied migration · adding a
dependency the stdlib or an installed one already covers · committing generated
output (`graphify-out/`, `dist/`, `node_modules/`, `data/`, `backend/data/`) ·
weakening a test, gate, or type to make something pass.

## Common tasks

**New scout persona** — subclass `Scout` in `backend/scout/base.py`, add to
`scout/scouts.py`, register in `ScoutEngine.__init__`, add the `scout_type`
literal to `ScoutInfo` in `models.py`.

**New endpoint** — add to the relevant router in `backend/routers/` (new domain →
new router included in `api.py`), authenticate, rate-limit if it triggers work,
add a typed client in `app-front-end/src/api/`, document in API.md.

**Change decision behaviour** — new version under `resources/config/partner_rules/`,
bump `resources/config/active.json`, extend the partner-rules contract test.

**Small instances** (~512 MB): `MAX_CONCURRENT_PIPELINE_CYCLES=1`,
`RESUME_AGENT_LOOPS_ON_STARTUP=false`, `MAX_RESUMED_AGENT_LOOPS=3`. See
[docs/operations/backend-memory-tuning.md](docs/operations/backend-memory-tuning.md).
