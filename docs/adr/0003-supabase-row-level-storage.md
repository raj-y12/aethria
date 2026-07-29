# ADR-0003 — Supabase with service-role, row-level writes

**Status:** Accepted

## Context

Aethria needs a managed PostgreSQL with authentication-adjacent tooling, plus a
persistence pattern that survives a pipeline writing large nested JSON documents
(review payloads, memos, evidence ledgers) many times per cycle.

Two failure modes drove this: a full-table read-modify-write per tenant, which
does not scale and races with concurrent cycles; and rewriting whole rows on
every partial update, which rewrites the large TOASTed columns each time and
inflates both storage churn and egress.

## Decision

- Supabase PostgreSQL is the production datastore. `USE_SUPABASE_STORAGE=1` is
  required for the pipeline to run; the local JSON store is a dev-only fallback.
- All backend access uses the **service-role** client (`get_service_client()`)
  or a direct `asyncpg` pool for the canonical domain and job store.
- **Frontends never talk to Supabase.** Every read and write goes through the
  backend, which is where tenancy and policy are enforced.
- Writes are row-level and targeted: `_update_startup_columns` updates only the
  columns that changed, so untouched TOAST pointers survive. `replace_all` is
  upsert-first and prune-after, never delete-then-write.
- The startup grid reads a thin list projection; heavy blobs load only on an
  explicit detail fetch.
- Schema lives in `supabase/migrations/`, applied in timestamp order and never
  edited afterwards.

## Consequences

**Good.** Concurrent cycles for the same tenant do not clobber each other.
Storage churn and egress stay bounded. There is one place — the backend — where
tenancy, rate limits, and policy are enforced.

**Cost.** The service-role client bypasses RLS, so RLS is a second line of
defence rather than the primary control; ADR-0001 is what actually protects
tenants. The write path tolerates unknown columns by dropping them and retrying,
which makes unapplied migrations survivable but silent — mitigated by the
startup `SCHEMA DRIFT` check that names missing columns loudly.

## Alternatives considered

- **Supabase client-side with RLS.** Would remove a hop, but puts tenancy,
  rate limiting, and policy enforcement in the browser. Rejected.
- **A general ORM.** The write patterns here are deliberately hand-shaped around
  TOAST behaviour and partial updates; an ORM's default full-row update is the
  thing being avoided.
