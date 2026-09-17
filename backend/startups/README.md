# startups

The canonical `startups` table authority (ARCHITECTURE.md §1: "Startup
authority is explicit").

## Purpose

CRUD, projections, and identifier resolution over `public.startups`, the sole
runtime source of startup rows.

## Inputs

`user_id` + a startup id, or a `lookup_id`/legacy identifier to resolve
through the alias bridge.

## Outputs

`Startup` (from `models.py`) rows, list projections, and resolved canonical
ids.

## Responsibilities

- Row-level CRUD and targeted column updates (never delete-and-rewrite —
  invariant #4).
- `CanonicalStartupResolver`: resolve a legacy/alias identifier to the
  canonical row before falling back to a direct lookup.
- `startup_id_aliases`: the tenant-scoped bridge for approved legacy
  identifiers, plus the one-off backfill/reconciliation tooling.

## Non-responsibilities

- Does not run agent logic (scout/reviewer/partner) — it only persists their
  output.
- Does not talk to Supabase; `legacy_supabase/storage.py` is the separate
  compatibility-only path.

## Dependencies

`tenant_context`, `models`.

## Public API

Import from `startups` directly (`from startups import StartupRepository`).
See `startups/__init__.py`.

## Testing

`tests/startup/` (`test_repository_postgres.py`,
`test_repository_projections.py`, `test_id_alias_repository_postgres.py`).
