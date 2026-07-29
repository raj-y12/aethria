# ADR-0007 — Deploy roots stay at the repository root

**Status:** Accepted

## Context

The repository holds three deployable units. The conventional monorepo layout
would nest them under `apps/` or `services/`. Two Vercel projects and one Render
service are configured against the current paths, and `run.py` resolves all three
relative to the repository root.

Moving them is a one-line change in the repository and a coordinated
reconfiguration of three externally managed hosting projects — with a window
where a deploy silently builds nothing, or builds the wrong directory.

## Decision

`backend/`, `app-front-end/`, and `web-front-end/` stay at the repository root.

Supporting material — docs, resources, shared packages, brand assets, migrations
— is organised freely around them.

Moving a deploy root is permitted, but only as a deliberate change that updates
the hosting configuration in the same operation. It is not a refactor to be done
in passing.

## Consequences

**Good.** Deploys keep working. New contributors find the three services
immediately. `run.py`, `docker-compose.yml`, `backend/Dockerfile`,
`.dockerignore`, and the CI `working-directory` settings all agree with each
other without indirection.

**Cost.** The repository root is busier than a nested layout, and the three
frontrunners sit alongside `docs/`, `resources/`, and `packages/` without visual
hierarchy. Accepted: this is cosmetic, and the alternative risks deploys.

## Alternatives considered

- **`apps/` + `packages/` workspace layout.** Tidier, and worth doing if the
  repository ever adopts a workspace tool that needs it. Not worth a deploy
  outage on its own.
