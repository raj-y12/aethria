# Codebase Audit Remediation Design

## Purpose

Remediate the confirmed production defects in `docs/2026-07-14-full-codebase-audit.md` without combining correctness work with a high-risk database-client rewrite or a broad API-router reorganization.

## Scope

This remediation will:

- make memo generation use the canonical `PartnerInfo` schema;
- make duplicate lookup dispatch resolve to the existing startup and report that outcome explicitly;
- make portfolio and MetaAgent intervals durable across reconstructed engine instances;
- make portfolio signal reads honor the configured storage backend and make stale warnings idempotent;
- make decision filtering use `recommendation` rather than removed legacy model attributes;
- keep lookup cancellations bounded without clearing live cancellations;
- prevent agent enablement from reporting a running state when every stage is disabled;
- run mandatory reference pruning in the production periodic pipeline;
- replace the identified deprecated executor calls with `asyncio.to_thread`;
- add regression tests for each behavior.

The standalone engine loops, API router split, and plain-Postgres migration remain separate follow-up projects. They change deployment architecture but are not prerequisites for correcting the audited runtime behavior.

## Architecture

### Canonical partner decisions

`PartnerInfo.recommendation` (`INVEST`, `PASS`, `MONITOR`) is the only decision field used by runtime model code. Legacy `YES`, `NO`, and `MAYBE` values remain confined to explicit adapters and human-resolution data. Memo generation will render the canonical recommendation and confidence, and decision storage filters will normalize legacy filter inputs at their boundary.

### Duplicate lookup identity

Storage insertion returns the canonical persisted startup ID. When that ID differs from the newly scouted UUID, ScoutEngine reports `ALREADY_IN_DEAL_FLOW` and the lookup runner continues with the existing row instead of a phantom ID. Rerun requests that intentionally replace an existing startup retain their existing force-rerun path.

The normalized-name unique-index migration is intentionally fail-safe. Operators must query and reconcile pre-existing tenant/name duplicates before applying it; the migration aborts rather than choosing data to merge or delete.

### Durable scheduling

Pipeline-stage due times must survive engine reconstruction and process restarts. A service-role-only PostgreSQL function atomically inserts or advances one row per tenant/job and returns only successfully claimed jobs. A stage claims its due time before doing work, preventing overlapping processes from running the same scheduled stage twice. Claim failures propagate so expensive work fails closed; PortfolioEngine isolates the outage so later pipeline bookkeeping can continue.

### Portfolio storage boundary

PortfolioStore exposes a backend-aware signal query and a watchlist update operation. PortfolioEngine does not read fallback files or append replacement watchlist records directly. Existing warnings are updated only when their values change, preventing repeated records.

### Bounded cancellation state

Cancellation keys are held in insertion order with a maximum size. Adding a key evicts only the oldest key, never the entire set. Membership checks and cleanup retain the existing API contract.

### Agent status consistency

Enabling the global agent loop requires at least one saved stage toggle. If no stage is enabled, the endpoint returns a validation response and persists `stopped`; it does not create a loop or transiently claim `running`.

### Reference enforcement

The periodic pipeline invokes reference pruning after scouting and before review. The existing origin/resolution guards remain authoritative. On-demand mandate-aware lookup behavior is unchanged.

## Error handling and observability

- Duplicate lookup is a successful, explicit outcome rather than a retry-driven failure.
- Schedule-store failures fail closed for expensive execution and log the affected user and stage.
- Reference-prune errors are visible but do not discard already validated rows.
- Portfolio stage failures remain isolated so one stage cannot prevent later due stages.
- Existing tenant scoping is preserved for every new storage call.

## Testing

Each defect receives a regression test that is observed failing before implementation. Focused tests cover memo generation, duplicate identity, decision filtering, durable schedules, Supabase-backed signals, cancellation eviction, agent toggling, reference pruning, and thread dispatch. The complete backend suite is run after focused tests, followed by searches proving that removed legacy `PartnerInfo` attributes are no longer read in production code.

## Follow-up projects

1. Split `backend/api.py` into startup, lookup, agent, and admin routers.
2. Replace Supabase/PostgREST retry and schema-string matching with direct Postgres transactions and migration enforcement.
3. Remove standalone engine `run_forever()` entry points after the production orchestrator is the sole documented execution path.
