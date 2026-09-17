# legacy_supabase

The Supabase compatibility boundary — **not** the production persistence
path (invariant #10: production persistence is plain PostgreSQL via
`DATABASE_URL`).

## Purpose

Hold every module that talks to Supabase directly, so the rest of the
backend can be verified (`tests/test_final_runtime_provider_boundary.py`) to
have zero module-level dependency on it.

## Inputs / Outputs

Supabase client sessions, list/doc JSON blobs, and legacy startup rows — the
same shapes the portable PostgreSQL path produces, for dev/test/migration
tooling only.

## Responsibilities

- `client.py`: user-scoped and service-role Supabase client factory.
- `doc_store.py`: list/doc JSON blob storage.
- `storage.py`: legacy compatibility storage for the startups table,
  including schema-drift detection.

## Non-responsibilities

- Never the production runtime path. Normal API/pipeline code must not
  import this package at module level (enforced by the runtime-boundary
  test's `RUNTIME_MODULES` guard).
- Does not decide when the legacy path is used — `env_config.use_supabase_storage()`
  and per-caller fallback logic own that.

## Dependencies

The `supabase` PyPI package — deliberately **excluded** from
`requirements.lock` (see `requirements-legacy.txt`). This is why
`legacy_supabase/__init__.py` has no package-level re-exports: importing one
submodule (e.g. `legacy_supabase.storage`) must not force-import the others
and pull in a dependency a caller doesn't need.

## Public API

Import the specific submodule you need:
`from legacy_supabase.storage import SupabaseStartupsStorage`.

## Testing

`tests/test_schema_drift.py`, `tests/test_storage_targeted_update.py`,
`tests/test_replace_all_safety.py`, and the other `test_*` files listed in
`ARCHITECTURE.md` §6.
