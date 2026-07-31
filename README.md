# Aethria

**An autonomous deal-flow operating system for venture teams.**

Aethria continuously discovers startups, evaluates them against a fund's own
written investment thesis, produces decision-ready investment memos, and routes
the uncertain cases to a human. Every judgement it makes is traceable back to the
evidence, the policy version, and the agent stage that produced it.

The repository is a monorepo containing three deployable services and the shared
configuration/persistence assets they depend on.

---

## Table of contents

| Document | What it covers |
|---|---|
| [PRODUCT.md](PRODUCT.md) | Product vision, users, jobs-to-be-done, and the end-to-end product flows |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, agent pipeline, request/data flow, storage model |
| [API.md](API.md) | Every HTTP endpoint the backend exposes, grouped by domain |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup, environment variables, development and testing workflow |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy roots, build assumptions, production configuration, Docker |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching, review expectations, coding standards, definition of done |
| [ROADMAP.md](ROADMAP.md) | Known technical debt and the identifiable forward roadmap |
| [AGENTS.md](AGENTS.md) | Operating rules for humans and AI agents working in this repo |
| [docs/adr/](docs/adr/) | Architecture Decision Records — why the system is shaped the way it is |
| [docs/](docs/README.md) | Reference material, operations runbooks, design system, archive |

---

## Repository layout

```
aethria/
├── backend/              FastAPI service + the autonomous agent pipeline (deploy root)
├── app-front-end/        Authenticated operator console — React + Vite (deploy root)
├── web-front-end/        Public marketing site and access funnel (deploy root)
├── packages/
│   └── product-chrome/   Shared React chrome consumed by both frontends
├── resources/            Versioned runtime configuration: partner rules, rubrics, contracts
├── supabase/migrations/  Ordered SQL migrations — the schema source of truth
├── brand-assets/         Brand studio: logo/wordmark SVGs, hero art, asset check script
├── docs/                 Reference docs, ADRs, operations runbooks, design, archive
├── run.py                One-command local orchestrator (backend + both frontends + agents)
├── docker-compose.yml    Containerised local backend
└── .env.example          Generated from backend/env_config.py — the full config surface
```

The three deploy roots (`backend/`, `app-front-end/`, `web-front-end/`) are
**frozen at the repository root**: Render and Vercel project settings point at
those exact paths. See [ADR-0007](docs/adr/0007-frozen-deploy-roots.md).

---

## The pipeline in one picture

```
                    ┌──────────────── active FundThesis (hard gate) ────────────────┐
                    │                                                               │
  web search  →  ScoutEngine  →  ReviewerEngine  →  PartnerEngine  →  PortfolioEngine  →  MetaAgent
  (Exa +         4 personas      3 personas         versioned rules     signals/health     self-tuning
   Firecrawl)    discovers       score 5 dims       INVEST/PASS/         watchlist         prompts,
                 real            + consensus        MONITOR              concentration     weights,
                 companies                          + escalation                           calibration
```

Every stage is async, scoped to exactly one `user_id`, and writes a structured
handoff trace so the final recommendation can be explained after the fact.

---

## Quick start

Prerequisites: Python 3.12, Node 22, and an OpenAI API key. Supabase and Clerk
credentials are required for the full authenticated product; see
[DEVELOPMENT.md](DEVELOPMENT.md) for the reduced-configuration paths.

```bash
git clone <repo-url> aethria && cd aethria

cp .env.example .env            # then fill in the required values
pip install -r backend/requirements.lock
(cd app-front-end && npm ci)
(cd web-front-end && npm ci)

python3 run.py                  # backend :8000, app :3000, web :3001
```

| Service | Local URL |
|---|---|
| Backend API | http://localhost:8000 |
| Operator app | http://localhost:3000 |
| Marketing site | http://localhost:3001 |

Full setup instructions, per-service commands, and the testing workflow live in
[DEVELOPMENT.md](DEVELOPMENT.md).

---

## Core invariants

These hold everywhere in the codebase. Breaking one is a bug, not a trade-off.

1. **Explicit tenancy.** Every storage read/write and every engine constructor
   takes an explicit `user_id` (the Clerk JWT `sub`). `require_user_id()` fails
   closed at construction time. There is no implicit global tenant.
2. **The fund thesis gates the pipeline.** No active thesis, no periodic cycle.
3. **Decision policy is versioned data, not code.** Partner thresholds live in
   `resources/config/partner_rules/*.json`, selected by `resources/config/active.json`.
4. **Storage is row-level.** Supabase writes are targeted upserts; a single
   user's data is never delete-and-rewritten.
5. **Configuration is registered.** Every environment variable the backend reads
   is declared in `backend/env_config.py`; a test fails the build if a new
   `os.getenv` call is added without registering it.
6. **Migrations are append-only.** New file in `supabase/migrations/` with a
   timestamp prefix; never edit an applied migration.

---

## Licence

Proprietary — all rights reserved. No licence is granted by publication of this
repository.
