# CLAUDE.md

The operating rules for this repository live in **[AGENTS.md](AGENTS.md)** —
one file, for human contributors and AI agents alike. Read it before changing
code. This file exists only so that tools looking for `CLAUDE.md` find the
pointer.

@AGENTS.md

## Orientation

| Need | Document |
|---|---|
| What the system is and how it fits together | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What the product does and for whom | [PRODUCT.md](PRODUCT.md) |
| Endpoints | [API.md](API.md) |
| Setup, run, test | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Deploy | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Process and review expectations | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Known debt and direction | [ROADMAP.md](ROADMAP.md) |
| Why things are the way they are | [docs/adr/](docs/adr/) |

## The five rules that matter most

1. Every storage call and engine takes an explicit `user_id`; call
   `require_user_id()`. Never take a tenant from a request body.
2. The fund thesis gates the periodic pipeline. No thesis → log and return.
3. Decision thresholds live in `resources/config/partner_rules/`, never in Python.
4. Supabase writes are targeted row-level upserts. Migrations are append-only.
5. Fail closed with a named reason. Never produce a plausible answer from
   inadequate input.

## Verification gate

```bash
python3 -m pytest -o asyncio_mode=auto
cd app-front-end && npm run lint && npm test && npm run build
cd web-front-end && npm run lint && npm run build
```
