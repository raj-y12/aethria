"""Legacy Supabase compatibility boundary — not the production persistence path.

Production persistence is plain PostgreSQL via `DATABASE_URL` (AGENTS.md
invariant #10). These modules remain only for migration/import tooling,
pool-less legacy tests, and dev fallback. New runtime code must not depend on
this package; see ARCHITECTURE.md §6 for the storage boundary.

Deliberately no package-level re-exports here: the `supabase` PyPI dependency
is excluded from `requirements.lock` (see `requirements-legacy.txt`), so each
submodule stays independently importable without pulling in the others'
dependency footprint. Import the submodule you need directly:

- legacy_supabase.client — Supabase client factory (user-scoped + service-role).
- legacy_supabase.doc_store — Supabase-backed storage for list/doc JSON blobs.
- legacy_supabase.storage — legacy compatibility storage for the startups table.
"""
from __future__ import annotations
