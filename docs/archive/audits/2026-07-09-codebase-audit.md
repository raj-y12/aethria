# Aethria codebase audit — 2026-07-09

Scope: backend, authenticated app, marketing site, shared package, migrations,
configuration, CI, tests, recent history, and all local/uncommitted files.

This is a read-only audit. No production code was changed.

## Executive verdict

Aethria has a strong product model and substantially better engineering discipline
than a typical early-stage AI application. Tenant scoping, typed domain models,
versioned decision policy, row-level persistence, reference validation, and backend
tests are real strengths.

The main problem is not a generally broken codebase. The P0 remediation pass has
closed the immediate reliability/dependency blockers I found, but there are still
important hardening items before this should be considered operationally mature:

1. normal API request handlers still contain synchronous Supabase/settings reads;
2. production SSE delivery timing still needs measurement behind the deployed
   proxy/runtime;
3. the UI's editorial hierarchy is implemented with text contrast that often fails
   WCAG AA;
4. CI is much better, but still does not cover the full browser/user journey that
   exposed the original login-to-data delay.

Overall engineering grade: **B**.

Release posture: **P0 code blockers are fixed locally; deploy backend and frontend
together, then measure login-to-first-SSE-frame and pipeline-write-to-render before
scaling traffic**.

## P0 remediation checklist — reviewed 2026-07-09

Status legend:

- [x] Verified complete
- [~] Implemented substantially, but acceptance criteria are not fully met
- [ ] Not fixed

Current result after the second review pass: **4 complete · 0 partial · 0 unfixed**
for local code/test acceptance. Production timing verification remains a release
check, not a local-code blocker.

### Follow-up pass — 2026-07-09

The dispatch follow-up found and fixed a lifecycle gap: once Scout created a
startup row, Dispatch stopped polling the failure/status path. Review or Partner
failures could therefore leave the takeover stuck in progress. Matched lookups
now poll memo pipeline status and surface failed runs.

The following contained P2 items were also completed and verified locally:

- P2-1: Playwright now uses an isolated default port and never reuses an
  unrelated existing server.
- P2-2: Marketing ESLint flat config is present, its existing lint errors are
  fixed, and CI runs the lint job.
- P2-4: The misleading `beforeunload` warning tied to enabled agents is removed.
- P2-6: Query defaults now use finite freshness and reconnect/mount refresh;
  immutable query paths still opt into static behavior explicitly.
- P2-9: Root-level `python3 -m pytest` now discovers backend tests through the
  repository `pytest.ini`.

The larger P1/P2 architecture items remain open: shared durable queue/SSE
ownership, retrieval-provider fallback, localStorage threat-model changes,
observability, and domain-level file splits.

### P1-P3 completion pass — 2026-07-09

Repository changes from the completion pass:

- P1-1: production startup now refuses process-local queue/SSE state unless the
  deployment explicitly sets `ALLOW_PROCESS_LOCAL_STATE=true`; multi-instance
  deployments must use the Postgres event backplane.
- P1-2: secondary analytics/meta queries are route-gated instead of mounting on
  every authenticated route.
- P1-4, P1-5, P1-7, P1-8: Clerk validation fails closed on configured issuer or
  audience mismatch; warm snapshots use session storage and clear on sign-out;
  logout modal focus/name/reduced-motion behavior is hardened; Supabase-backed
  portfolio services require explicit tenants.
- P1-9: Tavily-empty retrieval now has a bounded DuckDuckGo HTML fallback with
  provider metadata and the same source validation path.
- P2-3, P2-5, P2-8, P2-10, P2-11, P2-12: frontend coverage remains green at
  64 tests; cancellation waits for API acknowledgement; request metrics are
  exported; `backend/requirements.lock` is used by CI/Docker; map assets are
  lazy-loaded with 500 KB bundle budgets; login entry no longer waits for the
  optional activity summary.
- P3: Browserslist data was refreshed, direct Playwright duplication removed,
  transient design/tool artifacts are ignored, and bundle checks are enforced.

Still requiring a deliberate follow-up rather than a misleading checkbox:

- P1-1 cancellation/job ownership is still process-local; the production guard
  prevents unsafe horizontal scaling but durable shared job state is a separate
  schema/worker project.
- P1-6 low-contrast text and P2-7 god-file decomposition need a broad visual and
  structural refactor, respectively; neither is safely closed by a one-line
  token or file move.
- P2-3 still needs component-level memo and dispatch interaction tests beyond
  the current unit suite, and production SSE/proxy timing remains a deployment
  measurement.
- P3 documentation consolidation remains editorial work, not code behavior.

- [x] **P0-1 — remove pipeline event-loop blocking**
  - [x] Settings, storage creation, thesis reads, stage counts, activity writes,
    lookup-failure writes, reprocessing reads, portfolio stages, MetaAgent cycles,
    and Clerk JWT verification are now offloaded from the serving loop.
  - [x] `_build_pipeline_engines()` is now built through one `asyncio.to_thread`
    boundary in both periodic and lookup paths.
  - [x] Thesis reprocessing now offloads storage reads, settings/thesis access,
    agent-enabled checks, and engine construction.
  - [x] Event-loop lag is exported as
    `aethria_event_loop_lag_seconds` and warned on above a configurable threshold.
  - [x] The heartbeat regression now covers both a slow settings store and slow
    engine construction.
  - [x] The async test has an explicit pytest async marker and runs standalone.
  - **Verdict:** verified complete for the pipeline/SSE event-loop P0. Keep the
    separate P1/P2 work item for synchronous reads in normal API handlers.

- [x] **P0-2 — remove critical/high dependency advisories**
  - [x] App lockfile upgrades Clerk, jsPDF, React Router, DOMPurify, and js-cookie.
  - [x] Marketing lockfile upgrades React Router and Resend's vulnerable chain.
  - [x] Backend requirements upgrade FastAPI, Starlette, PyJWT, and dotenv.
  - [x] `npm audit --omit=dev --audit-level=high` reports zero vulnerabilities for
    both frontends.
  - [x] `pip-audit -r backend/requirements.txt` reports no known vulnerabilities.
  - [x] High-severity npm audits and the Python audit were added to CI.
  - [x] Both frontend production builds and the complete backend suite pass with
    the upgraded dependency set.
  - **Verdict:** verified complete.

- [x] **P0-3 — restore a green persistence contract/test**
  - [x] `isRerun` is now required in the normalized persisted shape.
  - [x] New lookups explicitly store `isRerun: false`.
  - [x] Legacy payloads without the field migrate to `false`.
  - [x] The test verifies rerun preservation, normal lookup persistence,
    deduplication, expiry, clearing, and legacy migration.
  - [x] Full frontend result: 56/56 tests pass.
  - **Verdict:** verified complete.

- [x] **P0-4 — make SSE health prove frame delivery**
  - [x] HTTP 200 now means `connecting`, not healthy.
  - [x] Health requires a parsed data/hello frame.
  - [x] Comment keepalives maintain liveness but cannot establish initial health.
  - [x] Forty seconds without any parsed frame marks the stream stale.
  - [x] A later frame recovers stale → healthy.
  - [x] Healthy-stream safety polling was reduced from 90 seconds to 30 seconds.
  - [x] Client diagnostics now capture connection time, last event, reconnects,
    last HTTP status, and last event reason.
  - [x] A focused stream-health test verifies connecting → healthy → stale →
    healthy.
  - [x] Unhealthy/connecting/stale startup polling is now 15 seconds regardless of
    user idleness.
  - [x] A focused polling-cadence test verifies hidden-tab, healthy-stream, and
    unhealthy-stream behavior.
  - **Verdict:** verified complete for local code acceptance. Production proxy
    behavior and real login-to-first-update timing still need deployment
    measurement before the original incident is operationally closed.

### Review findings before committing

All previously listed code fixes are now implemented and locally verified. Remaining
release checks:

1. Deploy frontend and backend together, record both build SHAs, and measure hello
   arrival plus pipeline-write-to-render latency before declaring the original
   minute-delay incident closed.
2. Keep watching `aethria_event_loop_lag_seconds` after deploy; if API endpoints
   still spike loop lag, move remaining synchronous API request-handler Supabase
   reads behind thread boundaries or a worker/process split.

## The good

- Tenant identity is explicit in the primary engines. `ScoutEngine`,
  `ReviewerEngine`, `PartnerEngine`, `MetaAgent`, pipeline entry points, and
  `SupabaseStartupsStorage` fail closed when their tenant is absent.
- The backend suite is broad and fast: **436 passed, 4 skipped** locally.
- The pipeline domain is coherent: scout → review → partner → portfolio → meta.
- Partner policy is versioned JSON rather than scattered business thresholds.
- Startup list reads use a thin projection and return 503 rather than falling back
  to an expensive full-row query.
- On-demand lookup has a separate queue and a dedicated execution slot.
- SSE uses authenticated `fetch`, refreshes Clerk tokens on reconnect, bounds
  subscriber queues, emits keepalives, sends an immediate reconciliation event,
  and has direct ASGI anti-buffering tests.
- Error boundaries, typed API clients, TanStack Query, reduced-motion support in
  several primary flows, and semantic buttons are all present.
- The authenticated app and marketing site both build successfully.
- The authenticated app lint passes with zero warnings.
- Design identity is distinctive and consistent. The product does not look like a
  generic component-library dashboard.

## The bad

- The serving process still has synchronous Supabase/settings work in normal API
  request handlers, even though the P0 pipeline/SSE hot path has been offloaded.
- Login mounts roughly fifteen queries at once, including data unrelated to the
  current route.
- Several query failures are converted into successful `null` values, hiding
  outages and suppressing useful retry/error states.
- The authenticated UI has a systematic low-contrast text problem.
- Frontend coverage is thin relative to the size and complexity of the product.
- Major files remain too large to change safely.
- The marketing app has a lint script that cannot run.
- The E2E command can test an unrelated app already using port 3000.
- Local design/test artifacts are not excluded cleanly from Git status.

## The ugly

- The previous production dependency advisories are fixed locally and covered by
  CI audit gates; keep them fixed before merging.
- The previous dispatch persistence contract failure is fixed locally.
- An issuer mismatch in Clerk JWT validation is deliberately retried without
  issuer validation.
- Confidential deal-flow, settings, signals, and thesis data are persisted
  indefinitely in browser `localStorage`.
- The previous audit's claim that all sync Supabase I/O was removed from async
  paths was false; the P0 pipeline path is now offloaded, but normal API handlers
  still need a separate hardening pass.

---

## P0 — fix before scaling or relying on the system operationally

### P0-1. The pipeline still blocks the API/SSE event loop — **FIXED**

**Evidence**

- `backend/pipeline_runner.py:254-256` calls `load_settings()` directly inside
  `_run_one_pipeline_cycle_inner()`.
- `backend/pipeline_runner.py:281-298` constructs the service/storage clients and
  reads/bootstrap the active thesis synchronously.
- `backend/pipeline_runner.py:343-346` and `443-455` perform synchronous Supabase
  counts/inserts inside the same coroutine.
- `backend/meta/agent.py:42-61` performs document-store reads/writes and a full
  analysis synchronously inside `async run_cycle()`.
- `backend/portfolio/engine.py` exposes async stage methods around predominantly
  synchronous stores.

**Impact**

The background pipeline runs inside the same one-worker uvicorn process that serves
REST and SSE. Any sync Supabase call blocks every request and every stream until it
returns. This directly explains streams that appear connected but deliver late, and
API calls that stall while agents run.

**Fix**

- Move every synchronous stage boundary to `asyncio.to_thread`, not just engine
  storage calls.
- Prefer one sync function per stage, offloaded once, over dozens of tiny thread
  hops.
- Add an event-loop-lag metric and a test that runs a deliberately slow sync store
  while asserting `/health`, `/api/startups`, and `/api/stream` remain responsive.
- Long term, move pipeline execution out of the web process.

**Remediation review:** the identified pipeline orchestration boundaries are now
offloaded, including engine construction in periodic, lookup, and thesis
reprocessing paths. The heartbeat regression covers slow settings reads and slow
engine construction, and the full backend suite is green.

### P0-2. Current frontend dependencies contain critical/high advisories — **FIXED**

**Evidence**

`npm audit --omit=dev` on the current lockfile reports:

- `app-front-end`: 2 critical, 5 high, 1 moderate.
- `web-front-end`: 3 high, 5 moderate.

Notable direct dependencies are `jspdf`, `@clerk/react`,
`@clerk/react-router`, `react-router`, `react-router-dom`, and `resend`.

**Impact**

Some advisories concern features Aethria may not invoke, but jsPDF processes memo
content, Clerk is the security boundary, and React Router is the app router. These
cannot be dismissed based only on likely exploitability.

**Fix**

- Upgrade the affected direct dependencies and regenerate lockfiles.
- Exercise login, routing, PDF export, and waitlist delivery after upgrading.
- Add `npm audit --omit=dev --audit-level=high` to both frontend CI jobs.
- Add a Python dependency audit (`pip-audit`) to CI.

**Remediation review:** current npm and Python audits are clean, audit gates are in
CI, and upgraded builds/tests pass.

### P0-3. CI is red on `main` — **FIXED**

**Evidence**

Frontend unit run: **50 passed, 1 failed**. The failing test expects persisted
lookup objects without `isRerun`; normalization now injects `isRerun: false`.

**Impact**

The required `app-frontend` CI job runs this suite, so the current head cannot pass
its own merge gate.

**Fix**

Choose and document the serialization contract:

- preserve absence for backwards-compatible optional fields; or
- make `isRerun` required and update all tests/consumers.

Do not merely loosen the assertion; test v0/v1 stored payload migration explicitly.

**Remediation review:** the normalized contract is now explicit and legacy
migration is tested. The frontend suite is green.

### P0-4. SSE health is inferred from HTTP connection, not delivery health — **FIXED**

**Evidence**

- `app-front-end/src/api/stream.ts:161-163` marks the stream open immediately after
  receiving a 200 response.
- `app-front-end/src/hooks/useSystemData.ts:117-128` then reduces startup polling to
  90 seconds.
- The server emits a hello event (`backend/api.py:1314-1318`), but the client does
  not require that event before declaring the stream healthy.
- Client failures are swallowed and have no logs, metrics, or UI diagnostic
  (`stream.ts:154-171`).

**Impact**

A proxy can return/hold a 200 stream while buffering frames. The client calls this
healthy and waits up to 90 seconds for the next poll. This reproduces the reported
“about a minute” symptom.

**Fix**

- Introduce `connecting | healthy | stale | closed`.
- Set `healthy` only after parsing the hello frame.
- Record `connectedAt`, `lastEventAt`, reconnect count, last HTTP status, and last
  event reason.
- Treat a stream as stale if no keepalive/event is parsed within 2× keepalive.
- Keep the poll at 10–15 seconds until hello is received; use 30 seconds, not 90,
  as the safety net until production telemetry proves otherwise.

**Remediation review:** hello-gated health, stale detection/recovery, diagnostics,
a 30-second healthy safety poll, and fixed 15-second unhealthy/stale polling are
implemented and tested. Production delivery has not yet been measured, so the
operational incident should stay open until deployment telemetry confirms the
login-to-first-frame and pipeline-write-to-render timings.

---

## P1 — major correctness, security, and product issues

### P1-1. Process-local SSE and in-memory queues do not scale safely

`EVENT_BUS_BACKPLANE` defaults to `memory`. That is valid only for the documented
single-worker deployment. With multiple instances:

- the pipeline can publish on a process different from the SSE subscriber;
- cancellation state is process-local;
- per-user loop registries are process-local;
- startup loop resume can start duplicate work;
- queue depth and connection caps are per process.

The optional Postgres LISTEN/NOTIFY backplane solves only event delivery.

**Fix:** keep the service explicitly single-instance until jobs, cancellations,
loop ownership, and events use shared durable state. Set
`EVENT_BUS_BACKPLANE=postgres` before horizontal scaling.

### P1-2. Login causes an avoidable request fan-out

`useSystemData()` mounts startups, escalations, signals, six meta queries, three
analytics queries, system health, thesis runtime, and settings together
(`app-front-end/src/hooks/useSystemData.ts:129-249`).

**Impact:** on a cold 512 MB instance this creates a thundering herd precisely when
the user needs one thing: the startup list. It also causes Clerk verification and
Supabase thread work for route-invisible data.

**Fix:** split route data:

- global: startups, settings/readiness, SSE;
- Flow: escalations and startup detail;
- Portfolio: signals/watchlist;
- Fund/System: meta, health, concentration, calibration.

Prefetch secondary data after the primary startup request settles or during idle.

### P1-3. Transient settings/thesis failures become permanent fake success

`fetchSettings().catch(() => null)` and
`fetchFundThesisRuntime().catch(() => null)` convert network/auth/server failures
into successful query results (`useSystemData.ts:237-249`). Settings is also marked
`STATIC`.

**Impact:** the UI cannot distinguish “not configured” from “API failed.” Agent
state can appear off, settings can remain empty, and no normal retry occurs.

**Fix:** let queries reject; render explicit degraded/error states; retry transient
statuses; reserve `null` for a valid backend response.

### P1-4. Clerk verification blocks the loop and weakens issuer validation

- `backend/auth_clerk.py:51` calls the synchronous JWKS client from async
  middleware.
- `backend/auth_clerk.py:52` disables audience verification.
- `backend/auth_clerk.py:71-79` retries an issuer mismatch without issuer checking.

**Impact:** a cold JWKS fetch can block all requests. More importantly, a configured
issuer mismatch is a security failure and should not be silently accepted.

**Fix:** cache/refresh JWKS asynchronously or offload verification; require the
correct issuer in production; validate the intended audience/authorized party
according to the Clerk token contract; fail closed on mismatch.

### P1-5. Confidential application data is stored indefinitely in localStorage

`app-front-end/src/lib/warmStart.ts:22-32` includes startups, escalations, signals,
thesis runtime, and settings. Lines 52-60 write those values to per-user
`localStorage`. Sign-out clears the in-memory query cache, but not these snapshots.

**Impact:** sensitive fund/deal data remains on a shared device indefinitely and is
available to any script executing on the origin. The new dependency advisories make
that exposure more consequential.

**Fix:** define a threat model. At minimum:

- expire and delete snapshots, not merely refresh them;
- clear them on sign-out;
- avoid persisting settings, signals, and escalation detail;
- consider session-only storage or a minimal non-sensitive startup summary.

### P1-6. WCAG text contrast fails systematically

Oxford `#001433` over paper `#f4f1ea` reaches 4.5:1 only near 60% opacity. Current
contrast examples:

- 45%: about **2.94:1**
- 50%: about **3.44:1**
- 55%: about **4.01:1**
- 60%: about **4.71:1**

There are hundreds of low-opacity text usages; a broad scan found 481 occurrences
in the authenticated frontend. Login labels use 45%; many core body/help/error
texts use 35–55%.

**Impact:** important labels, instructions, empty states, and operational data are
hard to read and fail WCAG AA for normal text.

**Fix:** reserve sub-60% opacity for decorative/non-text marks. Set semantic text
tokens to AA-safe values and ban arbitrary low-opacity text utilities in lint/design
review.

### P1-7. The logout modal is not an accessible modal

`AgentLogoutModal` uses `role="dialog"` but has no accessible name binding, initial
focus, focus trap, focus restoration, or inert background. It also uses arbitrary
`z-[9999]` and does not honor reduced motion.

**Fix:** use native `<dialog>` or a proven focus-management primitive; add
`aria-labelledby`, focus containment/restoration, and reduced-motion variants.

### P1-8. Tenant invariants are inconsistent in lower-level portfolio classes

`PortfolioStore`, `CostController`, and `RejectionAnalyzer` accept optional tenant
IDs. `PortfolioStore` can infer `AETHRIA_AGENT_USER_ID`; the others can silently
fall back to shared local files.

Primary production paths currently pass explicit IDs, but the constructors violate
the stated invariant and make future leakage regressions easy.

**Fix:** require `user_id` at construction for every runtime service. Put explicitly
named local-dev stores behind separate classes/factories.

### P1-9. Retrieval still has one provider

The June audit's only intentionally deferred P0 remains: Tavily is the sole live
retrieval path. Quota/provider failure degrades core discovery and lookup.

**Fix:** add a provider interface, fallback provider, quota/error telemetry, and a
user-visible degraded state.

---

## P2 — important quality and maintainability work

### P2-1. E2E is not trustworthy

`playwright.config.ts:23-27` reuses any server already listening on port 3000 in
local runs. The audit run tested an unrelated “PartFinder” application and failed
both tests. E2E is also excluded from CI.

**Fix:** use an allocated/dedicated port, verify an Aethria-specific health marker
before tests, set `reuseExistingServer: false`, and run at least unauthenticated
smoke tests in CI.

### P2-2. Marketing lint is broken and omitted from CI

`web-front-end` uses ESLint 9 but has no `eslint.config.*`, so `npm run lint`
terminates before checking code. CI only builds this app.

**Fix:** add flat ESLint config and run lint in the web CI job.

### P2-3. Frontend test depth is too low

The authenticated app has 11 Vitest files / 51 tests and two unauthenticated smoke
tests, compared with roughly 26k lines of TS/TSX/CSS. Critical untested surfaces
include:

- SSE parser/reconnect/health behavior;
- `useSystemData` request gating and retry semantics;
- login → token → first data timing;
- `useDispatchLookup` background failures/cancellation/rerun;
- memo rendering and PDF export;
- settings save/publish behavior;
- keyboard/focus behavior for takeover/modal flows.

### P2-4. `beforeunload` warns when agents are enabled, not running

`App.tsx:49-59` installs the browser leave warning whenever any stage is enabled.
The comment says “actively running,” but it does not read loop/cycle state.

**Impact:** users get a scary, generic browser warning during normal navigation or
tab close even though agents are intentionally server-side and can continue.

**Fix:** remove it, or gate it only on unsaved local work that would actually be
lost.

### P2-5. “Cancel lookup” is optimistic and process-local

The UI immediately clears all lookup state, then fires cancellation without waiting.
If the request fails or reaches another instance, expensive work continues while
the product says it was canceled.

**Fix:** persist cancellation in shared job state, acknowledge it, and display
“cancel requested” until the worker confirms.

### P2-6. Static-query defaults can preserve stale information too long

The global QueryClient uses infinite stale time and no mount/focus/reconnect refresh.
Per-query intent corrects some paths, but new queries default to never refreshing,
which is a dangerous default for an operational product.

**Fix:** make finite stale time the global default; opt truly immutable data into
infinity.

### P2-7. God files remain a change-safety problem

Largest production files include:

- `InvestmentMemoContent.css`: 4,367 lines
- `backend/api.py`: 2,551
- `backend/partner/decision.py`: 1,877
- `backend/supabase_storage.py`: 1,381
- `InvestmentMemoContent.tsx`: 1,350
- `backend/scout/base.py`: 1,215
- `backend/reviewer/engine.py`: 1,141
- `SettingsPage.tsx`: 1,104
- `components/system/internals.tsx`: 1,009

Split by domain boundaries, not arbitrary line count. Start with API routers, memo
sections/styles, settings sections, and system panels.

### P2-8. Production observability is not enough to diagnose the reported issue

Missing:

- request duration/status by endpoint;
- event-loop lag;
- SSE accepted/healthy/stale/reconnect/delivery counters;
- per-stage duration and sync-I/O duration;
- client first-auth, first-startup-response, first-render, and first-SSE-event marks;
- trace/correlation ID from browser → API → pipeline event.

Without these, the team can only infer whether the minute was cold start, auth,
Supabase, event-loop block, proxy buffering, missed event, or deployment skew.

### P2-9. Backend packaging/test invocation is fragile

Running `python3 -m pytest backend/tests` from repository root yields 68 collection
errors because backend modules use top-level imports and require `cwd=backend`.
The documented local invocation is correct, but the project is not package-safe.

**Fix:** package the backend or define root pytest configuration/PYTHONPATH so the
test command is location-independent.

### P2-10. Python builds are only directly pinned, not fully locked

Direct requirements are now exact-pinned, which is an improvement, but transitive
resolution is still not committed. CI and production can resolve different
transitive versions over time.

**Fix:** commit a generated lock from `uv` or `pip-tools` and install it in CI and
Docker.

### P2-11. Marketing payload is heavy

The marketing build emits one ~450 KB JS entry (~150 KB gzip), a 108 KB world map,
and many font subsets. The page also uses GSAP, Lenis, Framer Motion, D3, and
TopoJSON together.

**Fix:** measure real use. Remove duplicate motion/scroll tooling where possible,
lazy-load the map, restrict font subsets, and set a bundle budget.

### P2-12. The login welcome still blocks entry for up to eight seconds

The post-login CTA is hidden while the optional activity summary loads. The request
is time-boxed to eight seconds, but optional context should not gate entering the
product.

**Fix:** render the CTA immediately and fill activity asynchronously.

---

## P3 — cleanup and polish

- Root Git status contains roughly 50 untracked screenshots, `.playwright-mcp/`
  artifacts, and `.cursor/settings.json` (~11 MB total). Move intentional design
  evidence under `docs/design/` and ignore transient browser/tool output.
- `caniuse-lite` is six months old in both builds.
- `app-front-end` declares both `playwright` and `@playwright/test`; one is likely
  redundant.
- The app's raw split JS is still sizeable; PDF export is lazy, but bundle budgets
  would prevent regressions.
- The design system documentation is app-local while product context is spread
  across `docs/PRODUCT_SPEC.md`, `DESIGN_SYSTEM.md`, and older audit files. Add a
  short current product/design index and mark superseded audits.

---

## SSE/login diagnosis

### What is already correct

- Authenticated stream request.
- Fresh token on reconnect.
- Bounded queues and connection cap.
- Keepalive comments.
- No-proxy-buffering headers.
- Immediate `startups_changed: stream_connected` reconciliation frame.
- ASGI test proving middleware does not buffer the generator.
- 15-second fallback polling while the stream is disconnected.

### Original most likely failure chain before the P0 remediation

1. Login completes.
2. The app mounts a large read burst.
3. The initial startup query settles and triggers the agent loop.
4. Pipeline/meta/portfolio code performs sync Supabase work on the uvicorn event
   loop.
5. The SSE HTTP response may already be open, so the client calls it healthy.
6. Frames or the follow-up startup refetch are delayed by event-loop blocking or
   proxy buffering.
7. Because the stream is “healthy,” polling backs off to 90 seconds.
8. Data finally appears at the next poll, matching the observed minute-scale lag.

The second P0 remediation pass breaks this chain locally: pipeline construction
and stage boundaries are offloaded, SSE is not healthy until a data frame is
parsed, stale streams recover/fall back, and unhealthy polling is fixed at 15
seconds. Production timing still has to be measured behind the deployed proxy.

### Other hypotheses to verify in production

- source commit with the hello-frame fix is not deployed;
- frontend/backend deployments are on different revisions;
- a proxy buffers fetch-based SSE frames despite headers;
- more than one Render instance/process is active with the memory backplane;
- Supabase list projection returns transient 503s under the login burst;
- Render cold start dominates the first authenticated read.

### Required reproduction instrumentation

Capture one login with:

- frontend build SHA and backend build SHA;
- `performance.mark` for auth complete, token ready, AppShell mount, startup request
  start/end, stream response, hello parsed, first event, first non-empty render;
- server request duration and event-loop lag;
- SSE subscriber instance ID and event publisher instance ID;
- pipeline stage timings and every sync-I/O block over 100 ms.

Acceptance target:

- warm login first startup data <1.5 s p95;
- cold login <5 s p95 after backend health responds;
- hello parsed <1 s after stream response;
- pipeline write visible <2 s p95;
- safety poll no slower than 30 s.

---

## Frontend technical audit score

| Dimension | Score | Main reason |
|---|---:|---|
| Accessibility | 2/4 | Semantic structure is good; contrast and modal focus are not |
| Performance | 2/4 | Route-independent request fan-out and heavy optional bundles |
| Responsive | 3/4 | Login works at 390×844; signed-in surfaces need authenticated E2E coverage |
| Theming | 3/4 | Strong tokens and identity; opacity variants bypass semantic safety |
| Anti-patterns | 3/4 | Distinctive product language; excessive tiny uppercase/low-opacity metadata |
| **Total** | **13/20** | **Acceptable, significant work needed** |

Anti-pattern verdict: it does not look like generic AI UI. The failure mode is the
opposite: the editorial system is applied so aggressively that legibility,
conventional focus behavior, and task speed sometimes lose to visual tone.

---

## Verification record

Run on commit `3112ed09`:

- Backend: **436 passed, 4 skipped**, 2 Supabase deprecation warnings.
- Authenticated frontend lint: **pass**.
- Authenticated frontend build: **pass**.
- Authenticated frontend unit tests: **50 passed, 1 failed**.
- Authenticated frontend E2E: **2 failed**, because the config reused an unrelated
  server on port 3000.
- Marketing build: **pass**.
- Marketing lint: **cannot start**; ESLint 9 flat config missing.
- Shared `packages/product-chrome`: `tsc --noEmit` **pass**.
- Dependency audit: failed at the severities listed above.

### P0 change review verification

First pass against the uncommitted P0 remediation diff on 2026-07-09:

- Backend complete suite with CI async configuration:
  **437 passed, 4 skipped**, 3 warnings.
- Backend P0 targeted suite: **20 passed**.
- The new event-loop test run without CI's `asyncio_mode=auto`: **1 failed**
  because the async test has no explicit pytest async marker.
- Authenticated frontend complete suite: **53/53 passed**.
- Authenticated frontend lint: **pass**.
- Authenticated frontend production build: **pass**.
- Marketing frontend production build: **pass**.
- `npm ls --all`: **pass** for both frontend dependency trees.
- Authenticated frontend production dependency audit: **0 vulnerabilities**.
- Marketing frontend production dependency audit: **0 vulnerabilities**.
- Python requirements audit: **no known vulnerabilities**.

At the first pass, this verification supported closing P0-2 and P0-3 only; P0-1
and P0-4 still had the code-path and polling gaps that were fixed in the
follow-up pass below.

Second pass after the follow-up P0 changes on 2026-07-09:

- Backend targeted P0/SSE suite:
  **21 passed**, 1 warning.
- Backend complete suite with CI async configuration:
  **438 passed, 4 skipped**, 3 warnings.
- Authenticated frontend targeted P0/auth/warm-start suite:
  **5 files passed, 11 tests passed**.
- Authenticated frontend complete suite:
  **13 files passed, 56 tests passed**.
- Authenticated frontend lint:
  **pass**.
- Authenticated frontend production build:
  **pass**.
- Marketing frontend production build:
  **pass**.
- Authenticated frontend production dependency audit:
  **0 vulnerabilities**.
- Marketing frontend production dependency audit:
  **0 vulnerabilities**.
- Python requirements audit:
  **no known vulnerabilities**.

This second-pass verification supports closing all four P0 items for local
code/test acceptance. Production timing still needs to be measured after deploy.

## Recommended fix order

### First 48 hours

1. Deploy the P0 backend and frontend changes together; record both build SHAs.
2. Measure login-to-first-SSE-frame and pipeline-write-to-render timing in
   production.
3. Watch `aethria_event_loop_lag_seconds` during real agent cycles.
4. If normal API endpoints still create loop-lag spikes, offload remaining
   synchronous request-handler Supabase/settings reads.
5. Fix Clerk issuer/audience behavior.

### Week 1

6. Split `useSystemData` by route and prioritize startup data.
7. Stop swallowing settings/thesis errors.
8. Replace low-contrast semantic text tokens.
9. Fix modal focus management and remove the misleading unload warning.
10. Fix Playwright server isolation and add smoke E2E to CI.
11. Add/verify marketing lint in CI now that dependency audit gates exist.

### Weeks 2–3

12. Move pipeline jobs to durable shared execution or explicitly freeze deployment
    to one instance.
13. Add retrieval provider fallback.
14. Reduce persisted local browser data.
15. Add tests for login timing, lookup lifecycle, settings, memo/PDF, and
    keyboard interaction.
16. Split the largest backend/frontend files along existing domain boundaries.
17. Add full Python locking and frontend bundle budgets.

## Honest limits

- Production credentials and logs were not used, so the exact deployed SSE failure
  was not reproduced end-to-end.
- Authenticated screens could not be live-tested without submitting user
  credentials. Source, existing screenshots, builds, and the signed-out responsive
  surface were audited.
- Dependency advisories are point-in-time; the current second-pass local audit is
  clean, but CI should keep enforcing this before merge/deploy.
- This was a structural and targeted deep audit of ~75k source lines, not a claim
  that every line was manually reviewed.
