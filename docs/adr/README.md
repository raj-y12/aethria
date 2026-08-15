# Architecture Decision Records

Each ADR records one decision that shaped the system: the context that forced it,
what was chosen, and what it costs. They exist so a future reader can tell the
difference between a deliberate constraint and an accident.

These are written **retrospectively** from the implemented code — the decisions
predate the records. Dates reflect when the decision became visible in the
codebase, not when the record was written.

## Status values

- **Accepted** — in force; the code reflects it.
- **Superseded by ADR-NNNN** — replaced; kept for history.
- **Deprecated** — no longer in force, not replaced.

## Index

| # | Decision | Status |
|---|---|---|
| [0001](0001-explicit-tenancy.md) | Explicit `user_id` on every path; no implicit tenant | Accepted |
| [0002](0002-versioned-decision-policy.md) | Investment decision policy is versioned data, not code | Accepted |
| [0003](0003-supabase-row-level-storage.md) | Supabase with service-role, row-level writes; frontends never touch the database | Accepted |
| [0004](0004-sse-with-poll-backstop.md) | SSE push with a polling backstop, and a fail-closed multi-instance guard | Accepted |
| [0005](0005-durable-job-store.md) | Durable PostgreSQL job store for accepted work | Accepted |
| [0006](0006-canonical-identity-layer.md) | A canonical identity/evidence/decision layer, rolled out behind authority modes | Accepted |
| [0007](0007-frozen-deploy-roots.md) | Deploy roots stay at the repository root | Accepted |
| [0008](0008-env-registry.md) | A single registry for every environment variable | Accepted |
| [0009](0009-rule-based-partner-llm-for-edge-cases.md) | Rule-based partner decisions; the LLM only for declared edge cases | Accepted |
| [0010](0010-fail-closed-gates.md) | Fail closed on missing thesis, ambiguous identity, or thin evidence | Accepted |
| [0011](0011-decision-case-and-fund-intelligence-authority.md) | Historical Decision Cases and Fund Intelligence authority boundaries | Accepted |
| [0012](0012-investment-read-is-narrative-not-score.md) | The investment read is narrative, and never a score input | Accepted |
| [0013](0013-evidence-sufficiency-precedes-machine-recommendation.md) | Evidence sufficiency precedes machine recommendation | Accepted |

## Writing a new one

Copy the shape of an existing record: **Context · Decision · Consequences ·
Alternatives considered**. Number sequentially. If a new ADR replaces an old one,
mark the old one *Superseded by* in the same pull request.
