# Cloud Run migration — diagnostic report (read-only pass)

Date: 2026-07-31. No files were modified. Evidence is from the working tree at
`main` (`1de06dbf`), not from live GCP state — I have no `gcloud` access in this
session, so anything marked **[unverified]** needs a console/CLI check by you.

---

## 1. Current deployment configuration as implemented

### `cloudbuild.yaml` (repo root, 44 lines)

| Setting | Implemented | Your stated intent | Match |
|---|---|---|---|
| build SA | `cloud-build-deployer@$PROJECT_ID` | same | ✅ |
| Dockerfile / context | `backend/Dockerfile`, context `.` | same | ✅ |
| tag | `…/aethria-backend/backend:$COMMIT_SHA` | same | ✅ |
| runtime SA | `cloud-run-backend@$PROJECT_ID` | same | ✅ |
| env file | `--env-vars-file=cloudrun.env.yaml` | same | ✅ |
| invoker | `--no-invoker-iam-check` | same | ✅ |
| ingress | `all` | same | ✅ |
| cpu / memory / timeout | `1` / `2Gi` / `900s` | same | ✅ |
| **min / max** | **`--min=1 --max=2`** | min 1, **max 1** | ❌ |
| **concurrency** | **`--concurrency=8`** | **`1`** | ❌ |
| **secrets** | OPENAI, FIRECRAWL, EXA, CLERK_SECRET_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY, DATABASE_URL | list includes **TAVILY_API_KEY** | ❌ |

Drift is deliberate and recent: `1de06dbf "Allow Cloud Run API concurrency"`
(max 1→2, concurrency 1→8) and `3fa09227 "Remove Tavily secret mapping"`.

### `cloudrun.env.yaml` (16 keys)

All present keys are registered in `backend/env_config.py` — no ADR-0008
violation. `CLERK_AUDIENCE` is absent (optional; `auth_clerk.py:30` treats unset
as "skip audience check"). Notable values: `EVENT_BUS_BACKPLANE=postgres`,
`ALLOW_PROCESS_LOCAL_STATE=false`, `ALLOWED_ORIGINS=https://app.aethria.co`,
`RESUME_AGENT_LOOPS_ON_STARTUP=false`, `DURABLE_JOB_{GLOBAL,TENANT}_CONCURRENCY=1`.

### Dockerfile

Cloud Run-compatible as stated. `HEALTHCHECK` hardcodes port 8000 while Cloud
Run injects `PORT=8080` — harmless, Cloud Run ignores Docker `HEALTHCHECK`, but
it is dead config that will mislead someone later.

---

## 2. Likely causes of the remaining issues, with evidence

Ranked by how likely they are to be what you're actually seeing.

### C1 — `--max=2` breaks per-user scheduling loops (HIGH)

**Evidence:** `backend/api.py:346` (`_per_user_loops`), `api.py:869`
(`_resume_all_user_loops`), `cloudrun.env.yaml` `RESUME_AGENT_LOOPS_ON_STARTUP:
"false"`, `cloudbuild.yaml` `--max=2`.

Per-user agent loops are **process-local `asyncio` tasks**. They start on
whichever instance served the request that enabled them. With `max=2`, Cloud Run
routes the user's later requests to either instance, and when the loop-owning
instance is replaced (deploy, autoscale-down, health recycle) the loop dies —
and `RESUME_AGENT_LOOPS_ON_STARTUP=false` means **nothing ever restarts it**.
Symptom: agents silently stop, no error, `/health` fine, a manual re-trigger
"fixes" it.

`ALLOW_PROCESS_LOCAL_STATE=false` does **not** protect this. Read
`api.py:1164-1180`: that flag only gates the *event backplane*, not the loops.

### C2 — `--concurrency=8` + SSE saturates the request slots (HIGH)

**Evidence:** `api.py:2071` `GET /api/stream` returns a `StreamingResponse` held
open indefinitely; `_SSE_MAX_CONNECTIONS` default 200 (`env_config.py:94`).

Cloud Run counts a long-lived SSE stream as one of the 8 concurrent requests.
Every open browser tab holds one. 8 tabs pin an instance; 16 pin the whole
service at `max=2`, and further API calls queue behind them until the 900 s
timeout. Render had no per-instance request cap, so this is a *new* failure mode
introduced by the migration, not a pre-existing one. Symptom: intermittent
hangs/504s that correlate with how many tabs are open, worse over a working day.

### C3 — Cloud Run's 900 s request timeout truncates every SSE stream (MEDIUM)

**Evidence:** `--timeout=900s`; client reconnects with backoff
(`app-front-end/src/api/stream.ts:178-203`), and each reconnect emits the hello
nudge (`api.py:2057`) which triggers a full refetch.

Not fatal — the client recovers — but you will see a reconnect + refetch storm
every 15 minutes per tab, and `streamDiagnostics.reconnectCount` climbing
steadily. If your symptom is "the feed blinks / refetches on a timer", this is it.

### C4 — Tavily fallback silently disabled (MEDIUM)

**Evidence:** `3fa09227` removed `TAVILY_API_KEY` from `--set-secrets`, but
`env_config.py:223` still registers it and the DEC-004 `extract_pages` chain
still falls back to `tavily_extract` after Firecrawl.

With no key, the fallback leg is a no-op. Firecrawl errors now surface as a
fail-closed block instead of degrading to Tavily. Symptom: intermittent
thin-evidence blocks / empty lookups that used to succeed.

### C5 — Clerk is pointed at a **development** instance (MEDIUM–HIGH, verify first)

**Evidence:** `cloudrun.env.yaml` →
`CLERK_ISSUER: https://wealthy-sawfly-5.clerk.accounts.dev`.

`*.clerk.accounts.dev` is a Clerk *development* instance. If the Vercel
production build uses a `pk_live_…` key, its JWTs carry issuer
`https://clerk.aethria.co` and `verify_clerk_token` (`auth_clerk.py:55-58`)
rejects them → **401 on every authenticated endpoint while `/health` stays
green**. If your symptom is "logged in but everything 401s", this is the cause.
If the frontend is still on the dev key, this is merely wrong-for-production.
**[unverified — I can't see the Vercel env.]**

### C6 — `ALLOWED_ORIGINS` covers only `https://app.aethria.co` (LOW–MEDIUM)

**Evidence:** `cloudrun.env.yaml`; `api.py:1298-1312` builds `_cors_origins` from
localhost + that list, with `allow_credentials=True`.

No apex/`www`, no Vercel preview domains. Preview deployments will fail CORS
preflight. Fine if you only ever exercise production.

### C7 — `DATABASE_URL` pooler mode is load-bearing and unverified (LOW, high blast radius)

**Evidence:** `event_bus.py:161` reads `DATABASE_URL`; the backplane uses
`LISTEN/NOTIFY`, which **Supavisor transaction mode (port 6543) does not
support**. `api.py:1166-1179`: in production a backplane that fails to start
`raise`s — the container never becomes ready.

Your local `.env` uses the pooler on **port 5432 (session mode)**, which is
correct. The Secret Manager copy must match. Since the service is up, it
probably does — but confirm before anyone "helpfully" swaps it to 6543.

### C8 — `/api/admin/*` bypasses Clerk and its secrets are unmapped (LOW today)

**Evidence:** `api.py:1330` — `_ADMIN_PATH_PREFIX = "/api/admin/"` skips
`clerk_auth_middleware` entirely; `admin_auth.py:26` requires
`ADMIN_TOKEN_SECRET`, `:46` requires `ADMIN_DASHBOARD_SECRET`. Neither appears in
`cloudrun.env.yaml` or `--set-secrets`.

Currently safe: `_admin_dashboard_enabled()` (`api.py:1316`) is false in
production unless explicitly enabled, so the routes 404. But the infra-layer
invoker check is now off, so this prefix is directly internet-reachable; if
anyone sets `ADMIN_DASHBOARD_ENABLED=1` without the two secrets, the handler
raises `RuntimeError` at request time. Worth a note, not a fix.

### C9 — Docs stale (LOW)

`DEPLOYMENT.md:11` still names Render as the backend host. No Cloud Run runbook
exists. Definition-of-done item 4.

---

## 3. Minimal ordered fix plan

Each step is independently revertible. Stop after any step that resolves your
symptom rather than doing all of them.

| # | Fix | Class | Revert |
|---|---|---|---|
| 1 | Confirm the Clerk issuer the *frontend* actually mints against; align `CLERK_ISSUER`/`CLERK_JWKS_URL` to the production instance if it's live | config-only | restore two lines |
| 2 | `--max=2` → `--max=1` | deployment-only | one arg |
| 3 | `--concurrency=8` → a value that leaves headroom for SSE (see Q1 below) | deployment-only | one arg |
| 4 | Re-add `TAVILY_API_KEY=TAVILY_API_KEY:latest` to `--set-secrets` (secret already exists; runtime SA already has project-wide accessor) | deployment-only | one arg |
| 5 | Add apex/preview origins to `ALLOWED_ORIGINS` *if* you need preview builds | config-only | one line |
| 6 | Verify the `DATABASE_URL` secret is pooler **session** mode (5432) | verification-only | n/a |
| 7 | Update `DEPLOYMENT.md` for Cloud Run; drop the misleading port-8000 `HEALTHCHECK` | docs/app | git revert |

**No application-code change is required for any of C1–C7.** That is the good
news: every live issue identified here is a deploy-arg or env-value fix. C8 and
the `HEALTHCHECK` line are the only code-adjacent items, and neither is urgent.

Explicitly **not** proposed: splitting the worker, Cloud Run Jobs, Pub/Sub,
making the per-user loops multi-instance safe. C1 is solved for now by
`max=1` — the durable-loop redesign is the *next* migration, not this one.

## 4. Risks and rollback

- Steps 2–4 are single-arg changes to `cloudbuild.yaml`; rollback is
  `git revert` + a rebuild, or `gcloud run services update-traffic
  aethria-backend --to-revisions=<previous>=100` for an instant revert without a
  build.
- `max=1` means a deploy has a brief single-instance gap. Same as Render.
- Keep the Render service warm until steps 1–4 are verified, as you planned.
- Step 1 is the only one that can *cause* an outage (wrong issuer = total 401).
  Verify the frontend's Clerk key before touching it.

## 5. Verification after each fix

- **Every step:** `curl -sS -o /dev/null -w '%{http_code}' https://<url>/health`
  → 200; then an authenticated call from the SPA (not curl) → 200 with real data.
- **Step 1:** log in on `app.aethria.co`, confirm `GET /api/startups` returns 200,
  not 401. Check logs for `CLERK_JWKS_URL not set` / signature errors.
- **Steps 2–3:** open 8+ tabs, confirm API calls still return promptly; watch
  Cloud Run's *instance count* and *request concurrency* metrics.
- **Step 4:** trigger a lookup that would exercise the extraction chain; confirm
  no fail-closed block where Tavily should have covered.
- **Repo gate before any commit** (AGENTS.md): `python3 -m pytest -o
  asyncio_mode=auto` at root. Frontend gate is untouched by these changes.
- No new tests are warranted — none of steps 1–6 change application behaviour,
  they restore intended deploy parameters. Step 7 is docs.

## 6. Open questions

- **Q1.** Target concurrency. `1` (your stated intent) makes SSE unusable —
  one stream would consume the only slot. Render-equivalence and SSE pull in
  opposite directions here; I'd suggest keeping a moderate value with `max=1`
  rather than dropping to 1, but the number depends on expected tab count.
- **Q2.** Is the Clerk dev instance intentional for now?
- **Q3.** The `## Current observed issues` section of the brief was left empty —
  the ranking above is inferred from config drift, not from your symptoms.
