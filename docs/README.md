# Documentation

The **current-state** documentation lives at the repository root. This directory
holds decision records, reference material, operations runbooks, design sources,
business collateral, and the historical archive.

## Start at the root

| Document | Covers |
|---|---|
| [../README.md](../README.md) | Entry point, repository layout, quick start |
| [../PRODUCT.md](../PRODUCT.md) | Product vision, users, flows |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | System architecture, agent pipeline, data flow |
| [../API.md](../API.md) | Every HTTP endpoint |
| [../DEVELOPMENT.md](../DEVELOPMENT.md) | Setup, configuration, development and testing workflow |
| [../DEPLOYMENT.md](../DEPLOYMENT.md) | Deploy roots, production configuration, Docker |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Workflow, review expectations, coding standards |
| [../ROADMAP.md](../ROADMAP.md) | Known technical debt and forward direction |
| [../AGENTS.md](../AGENTS.md) | Operating rules for humans and AI agents |

## In this directory

### [adr/](adr/) — Architecture Decision Records
Why the system is shaped the way it is. Ten records covering tenancy, versioned
policy, storage, SSE, durable jobs, the canonical layer, deploy roots, the
environment registry, rule-based decisions, and fail-closed gates.

### [operations/](operations/)
| File | Contents |
|---|---|
| [docker.md](operations/docker.md) | Containerised backend: build, run, caveats |
| [backend-memory-tuning.md](operations/backend-memory-tuning.md) | Memory-pressure analysis and the small-instance tuning it justifies |

### [reference/](reference/)
| File | Contents |
|---|---|
| [supabase-schema-audit.md](reference/supabase-schema-audit.md) | Per-table schema audit and the long-run target schema. Previously `SUPABASE_SCHEMA_AUDIT.md` at the repository root; some `supabase/migrations/*.sql` comments still refer to it by that name |

### Scoring decision log — **stable paths, do not move**
| File | Contents |
|---|---|
| [scoring-assessment-audit.md](scoring-assessment-audit.md) | Scoring-engine assessment; referenced by test docstrings |
| [scoring-remediation-checklist.md](scoring-remediation-checklist.md) | Historical scoring decision log; its former Reviewer/scorer implementation has been retired. |

These two are cited by comments in backend source and tests. Keep the paths
stable or update every citation in the same change.

### [known-issues.md](known-issues.md)
Open, reproducible problems with a diagnosis but no fix yet.

### [design/](design/)
`explorations/` holds the four HTML design prototypes that are still referenced —
`J-gallery-instruments.html` is the visual source of truth cited in
`web-front-end` component headers. The living design contract for the product UI
is [`app-front-end/DESIGN_SYSTEM.md`](../app-front-end/DESIGN_SYSTEM.md), with
product rationale in
[`app-front-end/DESIGN_DIRECTION.md`](../app-front-end/DESIGN_DIRECTION.md) and
the design brief in [`.impeccable.md`](../.impeccable.md). Brand assets and the
brand studio live in [`brand-assets/`](../brand-assets/).

### [pitch/](pitch/)
Investor narrative, deck drafts, and positioning collateral. Business material,
not engineering documentation.

### [archive/](archive/) — historical, do not edit
Point-in-time records kept for context:

| Path | Contents |
|---|---|
| `archive/audits/` | Codebase, UI, and diagnosis audits from 2026-06 and 2026-07 |
| `archive/plans/` | Implementation plans and per-change planning ledgers |
| `archive/specs/` | Per-change design specifications |
| `archive/institutional-foundation/` | Phase 0–8 readiness certifications for the canonical layer |
| `archive/product/` | Early PRD artefacts |

**These describe what was true when written.** Several findings in the audits
have since been fixed — the current position is in
[../ROADMAP.md](../ROADMAP.md). Treat the archive as history, never as a
statement of current behaviour.
