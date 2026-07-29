# ADR-0001 — Explicit tenancy on every path

**Status:** Accepted

## Context

Aethria is multi-tenant: each user has their own fund thesis, deal flow,
settings, cost budget, and decision history. A cross-tenant leak here is not a
cosmetic bug — it means one fund seeing another fund's pipeline.

The common patterns for this are a request-scoped global (thread-local or
context variable) carrying the current tenant, or an ORM-level default filter.
Both work until something runs outside a request: a background loop, a queue
worker, a CLI, a test. In this system almost everything interesting runs outside
a request.

## Decision

Tenancy is an explicit parameter, everywhere.

- The tenant identifier is the Clerk JWT `sub`, extracted by `auth_clerk.py` into
  `request.state.user_id`. It is **never** read from a request body or query
  parameter.
- Every engine constructor, pipeline function, repository method, and storage
  call takes `user_id` explicitly.
- `tenant_context.require_user_id()` validates it at the top of each of those,
  raising immediately when it is missing or empty — at construction time, not at
  first query.
- Every Supabase query filters on `user_id`; migrations add RLS policies for
  tables reached with a non-service role.
- There is no ambient tenant to fall back to, so forgetting to pass one is a
  crash rather than a leak.

## Consequences

**Good.** The failure mode of a mistake is a loud error in the wrong place rather
than silent data exposure. Background loops, workers, CLI runs, and tests all use
the same code path as request handlers. Reviewers can check tenancy by reading a
function signature.

**Cost.** `user_id` threads through a large number of signatures, which is
verbose and occasionally tedious. Constructors take more arguments than they
otherwise would. This is accepted deliberately: the verbosity is the mechanism.

## Alternatives considered

- **`contextvars` request scope.** Would remove the parameter threading, but
  loses its guarantee exactly where the risk is highest — inside the async
  pipeline, workers, and `asyncio.to_thread` offloads, where context propagation
  is subtle and easy to get wrong.
- **RLS alone with a per-request database role.** Strong at the database layer,
  but the backend uses the service-role client for pipeline work, which bypasses
  RLS by design. RLS is a second line of defence here, not the first.
