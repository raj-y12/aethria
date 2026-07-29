# ADR-0004 — SSE push with a polling backstop

**Status:** Accepted

## Context

A pipeline cycle takes minutes and writes results incrementally. The console
originally polled on a timer, which meant a choice between a stale UI and a
constant request load — and the poll interval was the dominant term in
"login to first data" latency.

WebSockets were more machinery than the need justified: the traffic is one-way,
server to client, and small.

## Decision

`GET /api/stream` is a Server-Sent Events endpoint, per user.

- Pipeline stages call `event_bus.publish(user_id, …)`. The frontend's
  `useStartupsStream` refetches on each `startups_changed` nudge; the event
  carries a signal, not the data.
- The stream's health signal is the **parsed hello frame**, not HTTP 200 — a
  proxy that returns 200 and then buffers the body is a broken stream, and this
  is how the client detects it.
- Timed polling stays as a slow backstop, so a blocked stream degrades to the
  previous behaviour rather than to a frozen UI.
- Connections are capped by `SSE_MAX_CONNECTIONS` (503 beyond) with a keepalive
  comment every `SSE_KEEPALIVE_SECONDS`. Queues are bounded and drop oldest.
- `event_bus.py` is process-local by default. `EVENT_BUS_BACKPLANE=postgres`
  with a direct `DATABASE_URL` adds `LISTEN`/`NOTIFY` fan-out between instances.

## The fail-closed guard

A process-local event bus is correct for one instance and silently wrong for two:
clients connected to instance A never see events published on instance B. So
booting with `ENVIRONMENT=production` **raises** unless either the Postgres
backplane is enabled and starts successfully, or `ALLOW_PROCESS_LOCAL_STATE=true`
explicitly acknowledges a single-instance deployment.

This makes "we scaled to two instances and half the users stopped getting live
updates" impossible to do by accident.

## Consequences

**Good.** Updates arrive in about the time it takes to write them. Poll load
drops without losing the safety net. Multi-instance misconfiguration fails at
boot rather than in production traffic.

**Cost.** Long-lived connections consume a slot and file descriptor per client,
which is why the cap exists. The backplane adds a second dependency on a direct
database connection, separate from the Supabase REST client.

## Alternatives considered

- **WebSockets.** Bidirectional machinery for a unidirectional need.
- **Redis pub/sub backplane.** Another service to run; PostgreSQL
  `LISTEN`/`NOTIFY` is already available on a database the system requires.
- **Push the data, not a nudge.** Would couple the event payload to every read
  model's shape. Refetching keeps one code path for reads.
