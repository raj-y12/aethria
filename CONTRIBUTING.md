# Contributing

This document covers how work gets into `main`. For *how to run things*, see
[DEVELOPMENT.md](DEVELOPMENT.md); for the rules that govern the code itself, see
[AGENTS.md](AGENTS.md).

---

## Before you start

Read, in order:

1. [ARCHITECTURE.md](ARCHITECTURE.md) — how the system fits together
2. [AGENTS.md](AGENTS.md) — the coding rules and invariants, for humans and AI agents alike
3. [docs/adr/](docs/adr/) — why the load-bearing decisions were made

If your change contradicts an ADR, that is fine — but supersede the ADR in the
same pull request rather than quietly diverging from it.

---

## Workflow

1. **Branch from `main`.** Use a descriptive name: `fix/lookup-duplicate-cases`,
   `feat/outcome-coverage-api`, `docs/deployment-runbook`.
2. **Keep the change coherent.** One concern per pull request. Refactors,
   behaviour changes, and formatting sweeps land separately — a reviewer should
   never have to separate them by eye.
3. **Write the test first when fixing a bug.** A regression test that fails
   before the fix and passes after is the proof the fix is real.
4. **Run the full local gate** (see [Definition of done](DEVELOPMENT.md#8-definition-of-done)).
5. **Open a pull request** describing what changed, why, and how you verified it.
   Link the ADR if you added or superseded one.
6. **CI must be green.** All eight jobs, including the dependency audits. A red
   audit is a real finding, not noise to retry past.

Commits: imperative subject line, explain *why* in the body when the reason is
not obvious from the diff.

---

## Review expectations

A reviewer is checking, in priority order:

1. **Tenancy.** Does every new storage path and engine take an explicit
   `user_id`? Is any tenant identifier accepted from a client request body?
   (It must not be — it comes from the verified JWT.)
2. **Fail-closed behaviour.** On missing thesis, ambiguous identity, thin
   evidence, or an unconfigured dependency, does the code produce a *named*
   block or a plausible guess?
3. **Policy as data.** Are decision thresholds still in versioned JSON rather
   than in Python?
4. **Blast radius.** Row-level writes only. No full-table rewrites for one
   tenant's data. No migration edited in place.
5. **Cost.** LLM calls are the dominant cost. Is a new call necessary, minimal,
   and gated by the cost controller where one applies?
6. **Tests.** Does the new path have coverage that would actually fail if the
   behaviour regressed?
7. **Docs.** API change → [API.md](API.md). New env var → `backend/env_config.py`
   and a regenerated `.env.example`. Architectural decision → an ADR.

---

## Coding standards

### Python (`backend/`)

- Explicit `user_id` on every storage call and engine constructor; call
  `require_user_id()` at the top.
- Pydantic models for all data shapes — `backend/models.py` and the per-domain
  `models.py` files are the source of truth. Use `.model_dump()` /
  `.model_validate()`, not ad-hoc dicts.
- `async` throughout the pipeline. Offload blocking I/O with
  `asyncio.to_thread`; parallelise with `asyncio.gather` only where the stages
  are genuinely independent.
- Enums for states, block reasons, and modes. No free-text status strings.
- New configuration goes through `backend/env_config.py`. Never add a bare
  `os.getenv("NEW_THING")`.
- Log the reason when you skip work. A silent skip is a bug report waiting to
  happen.

### TypeScript (`app-front-end/`, `web-front-end/`)

- All backend calls live in typed client modules under `src/api/`. **No `fetch`
  outside `src/api/`.**
- Auth tokens come from `api/auth.ts` (`setTokenGetter` / `getToken`). Never
  bypass it.
- Data fetching uses TanStack Query through the hooks in `src/hooks/`. Check for
  an existing hook before writing new fetch logic.
- Pure logic belongs in `src/lib/` with unit tests, not inside components.
- Framer Motion is the animation library for the app; don't add another.
- Visual changes follow [`app-front-end/DESIGN_SYSTEM.md`](app-front-end/DESIGN_SYSTEM.md).
  Named tokens only — no raw hex, no arbitrary pixel spacing.
- ESLint runs with `--max-warnings 0`. Fix the warning; don't disable the rule
  without a comment explaining why.

### SQL (`supabase/migrations/`)

- One new timestamped file per change. Applied migrations are immutable.
- Include the RLS policies alongside the table in the same migration.
- If repository code exercises the new schema, add the migration to the CI list
  in `.github/workflows/ci.yml` and extend the PostgreSQL contract tests.

---

## Documentation

Docs live in two places, and the split matters:

| Location | Contents |
|---|---|
| Repository root | The canonical, current-state documents: README, ARCHITECTURE, PRODUCT, API, DEVELOPMENT, DEPLOYMENT, ROADMAP, CONTRIBUTING, AGENTS |
| `docs/` | Reference material, ADRs, operations runbooks, design, business collateral, and the archive |

Rules of thumb:

- **Update the root document** when current behaviour changes. Root docs describe
  what the system does *now*; they are not a changelog.
- **Add an ADR** (`docs/adr/`) when you make a decision a future reader would
  otherwise have to reverse-engineer. Copy the format of an existing one.
- **Never edit `docs/archive/`.** It is a historical record — point-in-time
  audits, plans, and design specs. Some of its findings are already fixed; it
  documents what was true when written, not what is true now.
- `docs/scoring-remediation-checklist.md` and `docs/scoring-assessment-audit.md`
  are referenced by comments in backend source and tests — keep those paths
  stable.

---

## Security

- Never commit secrets. `.env` and `.env.*` are gitignored; `.env.example` files
  carry placeholder values only.
- The service-role Supabase client is backend-only. The frontends never talk to
  Supabase directly.
- Text retrieved from third parties is untrusted input. Route it through the
  prompt-safety and injection-detection helpers before it reaches a model prompt.
- If you find a security issue, raise it privately with the maintainers rather
  than in a public issue.
