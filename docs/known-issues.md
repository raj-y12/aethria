# Known Issues

Reproducible, diagnosed defects. Broader architectural debt is in
[../ROADMAP.md](../ROADMAP.md); this file is for specific defects. Entries stay
after resolution as a record of root cause and fix — see each **Fixed by** line
for the change that closed it.

---

## Duplicate companies in the identity review queue

**Status:** resolved · **Priority:** P0 · **Surface:** operator-visible ·
**Verified in:** `backend/identity/repository.py` · **Fixed by:**
`backend/identity/repository.py` (`list_case_groups`), `backend/routers/identity.py`
(`/api/identity-cases/groups` + group resolve/defer/reject), `backend/identity/models.py`
(`IdentityCaseGroup`), `app-front-end/src/components/identity/IdentityReviewQueue.tsx`

The identity review list rendered one row per open identity-resolution case, so
the same company could appear several times.

### Root cause

`open_identity_case` upserts on `(user_id, observation_id) where status = 'open'`.
That prevents a duplicate case for the same *observation*, but not for the same
*company*, domain, or provider identity. Source observations are created per
discovery event and per scout persona by design, and repeated discoveries, manual
lookups, and imports each produce another observation for one real company. The
frontend was rendering the data faithfully — each case has a distinct
`identity_case_id`.

### Fix

Cases are grouped server-side by normalized `observed_domain` (a verified domain
is the only signal treated as reliable enough to auto-merge); a case with no
domain stays in its own singleton group until a human confirms the match. The
review queue renders one row per group with an observation count, and resolving
a group transitions every linked case to the same resulting company atomically
(the first case's action runs as given; every other case in the group is then
matched to that same company rather than re-running "create" and producing a
duplicate). Regression coverage: `backend/tests/identity/test_identity_repository_unit.py`
(grouping), `backend/tests/identity/test_identity_endpoints.py`
(atomic group resolution), `app-front-end/src/components/identity/__tests__/IdentityReviewQueue.test.tsx`.

### What not to do

Do not group or de-duplicate in the UI alone. That makes the list look correct
while leaving the underlying identity graph inconsistent — the next stage to read
it will still see several unrelated companies. (Not done here — grouping is
computed server-side from `source_observations`.)

---

## Cross-surface audit findings

The entries below were confirmed from source and test evidence, then fixed.

### Partial canonical-authority rollout leaves investment records internally contradictory

**Status:** resolved · **Priority:** P0 · **Surface:** investment decision integrity ·
**Verified in:** the 2026-08-03 Workvivo production lookup, `backend/pipeline_runner.py`,
`backend/reviewer/engine.py`, `backend/supabase_storage.py`,
`backend/utils/financials_grounding.py`, `backend/authority/service.py`,
`app-front-end/src/lib/reviewScoring.ts`, and
`app-front-end/src/lib/founderMemo.ts` · **Fixed by:** `backend/pipeline_runner.py`
(reload persisted startup before Partner), `backend/identity/ownership_gate.py` (new),
`backend/partner/decision.py` (`_finalize_thesis_and_mandate_gate` ownership check),
`backend/models.py`, `backend/utils/adapters.py`,
`app-front-end/src/lib/reviewScoring.ts`, `app-front-end/src/lib/founderMemo.ts`

### Root cause

Canonical authority was not governing the affected lookup: its legacy startup
record has a completed review and Partner decision, while the corresponding
canonical entity has no evaluation run, criterion assessments, or recommendation.
The pipeline consequently carried incompatible representations instead of one
immutable, evidence-backed fact snapshot.

Financial fields are populated only by the financial-grounding path and Review
deliberately leaves them untouched. Partner received an in-memory Scout object
prepared before Reviewer persistence. The UI preferentially read the compact
consensus `structured_scoring` result rather than the score presentation/rich
evidence, and a partial founder-resolution result could displace known Scout
founder names.

The observed Workvivo record made the impact material: a 2022 Series B and
historical customer-growth claim were treated as current traction in a 2026
review, even as the grounded finance fields correctly reported no verified
valuation or traction metric. It reached Partner despite Workvivo having been
acquired by Zoom in 2023, rather than being stopped for ownership/identity review.

### Fix

1. `check_ownership_conflict` (new `backend/identity/ownership_gate.py`) scans
   Scout/Review text for acquisition language (rule-based, mirroring the existing
   funding-stage text inference in `utils/scout_post_review_enrichment.py`) and,
   absent an explicit operator spinout-verification override, forces Partner to
   MONITOR with `mandate_gate="ownership_conflict"` and `human_review_required=True`
   — reusing the existing `held_recommendation`/`held_next_action` fail-closed
   shape. Regression: `backend/tests/identity/test_ownership_gate.py`,
   `backend/tests/test_partner_mandate_gate.py` (reproduces the Workvivo scenario).
2. Not changed — canonical stays in shadow/reconciliation mode; `AuthorityContext`
   already made `CANONICAL_READ` structurally unreachable
   (`backend/authority/service.py`, untouched by this fix).
3. `pipeline_runner.py`'s on-demand lookup now reloads the persisted startup from
   storage after Reviewer runs and passes that snapshot to Partner instead of the
   stale pre-Reviewer object. `reviewScoring.ts` reads `scoring_presentation` as
   the primary/authoritative source, falling back to legacy fields only when
   absent. `founderMemo.ts` retains a trusted Scout founder name when the
   resolver result is partial or not confidently company-linked.
4. Legacy-review audit and re-evaluation from verified claims only — **not done
   here**; flagged as separate follow-up work, as the original fix direction
   specified.

---

### Tenant-scoped legacy Supabase tables do not enforce row-level security

**Status:** resolved · **Priority:** P0 · **Surface:** tenant isolation ·
**Verified in:** `supabase/migrations/20260314000005_aethria_tables_from_code.sql`,
`supabase/migrations/20260314000006_add_user_id_to_tables.sql` · **Fixed by:**
`supabase/migrations/20260804000002_legacy_tenant_tables_rls.sql`,
`backend/tests/jobs/test_job_repository_postgres.py`

### Root cause

The legacy portfolio, meta, and document tables were created without RLS, and the
later tenant migration added `user_id` and composite keys without adding policies.
`meta_churn_signals`, `pipeline_activity`, and `user_state` have the same gap.

### Fix

A new migration enables RLS on all 20 affected tables with a service-role-only
policy (the backend is the only caller — frontend never touches Supabase directly)
and revokes `anon`/`authenticated` grants. A parametrized Postgres contract test
asserts RLS, policy shape, and grants for every table (requires
`TEST_DATABASE_URL`; not executed live in this session — no local Postgres was
available — but reviewed line-by-line against the already-verified `security_limits`
pattern below).

---

### Rate-limit and lock RPCs are not privilege-hardened

**Status:** resolved · **Priority:** P0 · **Surface:** API availability and tenant
isolation · **Verified in:** `supabase/migrations/20260526000001_security_limits.sql` ·
**Fixed by:** `supabase/migrations/20260804000001_security_limits_privilege_hardening.sql`,
`backend/tests/jobs/test_job_repository_postgres.py`, `.github/workflows/ci.yml`

### Root cause

The `security_limits` table had no RLS. Its rate-limit, acquire-lock, and
release-lock functions are `SECURITY DEFINER` but did not pin `search_path`, revoke
default `PUBLIC` execution, or grant only the service role.

### Fix

A new migration pins an empty `search_path` on all three functions, revokes
`PUBLIC`/`anon`/`authenticated` execution, grants `service_role` only, and enables
RLS with a service-role-only policy on `security_limits`. A Postgres contract test
(`test_target_postgres_security_limits_is_rls_protected_and_rpc_service_role_only`)
checks RLS, policy shape, table grants, and per-function ACL; CI's Postgres
contract job now applies both this migration and its prerequisite.

---

### Switching operator accounts can display another tenant's local UI state

**Status:** resolved · **Priority:** P0 · **Surface:** operator tenancy ·
**Verified in:** `app-front-end/src/App.tsx`,
`app-front-end/src/settings/SettingsPage.tsx`,
`app-front-end/src/pages/FlowPage.tsx`,
`app-front-end/src/hooks/useDispatchLookup.ts` · **Fixed by:** `app-front-end/src/App.tsx`,
`app-front-end/src/App.tenant-switch.test.tsx`

### Root cause

The app cleared TanStack Query data when the Clerk user changed, but did not
remount the tenant-bound shell. Settings drafts, thesis/agent status, selected
memo state, dispatch state, and the fund-configuration hook remained in component
state while the next tenant's requests were pending.

### Fix

`<AppShell key={userId ?? 'anon'} />` forces a full unmount/remount of the
tenant-bound shell (and everything under it — Settings, FlowPage, `useDispatchLookup`
are all descendants) on identity change, while the existing `queryClient.clear()`
still handles the cache. A regression test renders App with a mocked, mutable
`userId`, asserts the shell mounts once on first load and remounts (does not
merely re-render) exactly once per identity change, and confirms a same-user
re-render does not force a spurious remount.

---

### A legacy fund-configuration blob can be assigned to the wrong account

**Status:** resolved · **Priority:** P0 · **Surface:** fund thesis privacy and
integrity · **Verified in:** `app-front-end/src/lib/fundConfiguration.ts` ·
**Fixed by:** `app-front-end/src/lib/fundConfiguration.ts`,
`app-front-end/src/lib/__tests__/fundConfiguration.test.ts`

### Root cause

When no backend configuration or scoped local key existed, the migration copied a
historic unscoped local-storage blob into the first signed-in user's key. That
blob could contain a different tenant's thesis narrative and decision settings.

### Fix

`loadFundConfiguration` now discards the unscoped legacy key instead of copying
it into any user's scoped key — it cannot be safely attributed to the signed-in
tenant. A regression test asserts a user reading after an unscoped legacy blob
exists gets defaults, not the blob's content, and that the scoped key is never
populated from it.

---

### Active-thesis decisions can bypass the mandate gate when LLM alignment is absent

**Status:** resolved · **Priority:** P1 · **Surface:** investment decision safety ·
**Verified in:** `backend/reviewer/engine.py`, `backend/reviewer/base.py`,
`backend/partner/decision.py` · **Fixed by:** `backend/reviewer/engine.py`,
`backend/models.py`, `backend/utils/adapters.py`, `backend/partner/engine.py`,
`backend/partner/decision.py`, `backend/tests/evaluation_v2/test_governed_engine_inputs.py`,
`backend/tests/test_partner_engine_review_payload.py`

### Root cause

For an embedding-backed thesis, Reviewer skips deterministic fallback alignment.
If the LLM output omits or malforms alignment, parsing returns `None`; Partner
treated that exactly like no mandate and could leave an otherwise-INVEST decision
ungated.

### Fix

Reviewer now stamps a `thesis_alignment_state` (`no_active_thesis` /
`missing_under_active_thesis` / `present`) on every review, carried through
`ReviewInfo`/`PartnerInfo`. Partner's mandate-gate finalizer distinguishes the two
previously-conflated `None` cases: "no active thesis" keeps its existing
`no_mandate` (ungated) behavior, while "active thesis, alignment came back
None/malformed" now forces the same fail-closed `held` treatment as an
off-thesis company (`mandate_gate="alignment_missing"`, `human_review_required=True`).
An end-to-end governed-thesis test drives the full persisted-review → Partner
path for this exact scenario.

---

### Durable worker and outbox loops can stop permanently after a repository error

**Status:** resolved · **Priority:** P1 · **Surface:** pipeline reliability ·
**Verified in:** `backend/jobs/worker.py`, `backend/jobs/outbox.py`, `backend/api.py` ·
**Fixed by:** `backend/jobs/worker.py`, `backend/jobs/outbox.py`, `backend/api.py`,
`backend/tests/jobs/test_job_worker.py`, `backend/tests/jobs/test_outbox_publisher.py`

### Root cause

Exceptions from lease recovery, `claim_next()`, or `claim_outbox_batch()` escaped
their background loops. Startup did not supervise the tasks, and system status
reported readiness from repository availability rather than task health.

### Fix

Both loops now catch (never swallow `asyncio.CancelledError`), log, and retry
with bounded exponential backoff instead of letting the task die. `/api/system/status`
exposes `durable_jobs.runtime` (per-loop state: `running`/`stopped`/`failed`/`cancelled`)
and marks the system `degraded` when a supervised loop has actually died, not just
when the repository is slow. Tests cover transient claim/lease-recovery failures
surviving the loop.

---

### Fresh schemas are missing portfolio tables and can fall back to shared local files

**Status:** resolved · **Priority:** P1 · **Surface:** production data integrity ·
**Verified in:** `backend/portfolio/store.py`, `backend/utils/feed_fetcher.py`,
`backend/portfolio/rejection.py`, `supabase/migrations/` · **Fixed by:**
`supabase/migrations/20260804000003_portfolio_startups_feed_cache_rejection_patterns.sql`,
`backend/portfolio/rejection.py`, `backend/utils/feed_fetcher.py`,
`backend/tests/test_production_fallbacks.py`

### Root cause

Code required `portfolio_startups`, `portfolio_feed_cache`, and
`portfolio_rejection_patterns`, but no migration created them. On Supabase errors,
feed and rejection paths fell back to local files even in production (unlike
`portfolio/store.py`, which already failed closed correctly); the rejection-pattern
file was not tenant-namespaced.

### Fix

A new migration creates all three tables with service-role-only RLS.
`RejectionAnalyzer`'s local-file fallback path is now per-tenant
(`rejection_patterns_{user_id}.json`, was a single shared file), and both
`RejectionAnalyzer` and `FeedFetcher` raise instead of silently falling back to a
local file when `env_config.local_fallback_allowed()` is false (production).
Regression tests cover both fail-closed paths and the per-tenant filename scoping.

---

### Seven evaluator tests are time-dependent and now fail the backend gate

**Status:** resolved · **Priority:** P1 · **Surface:** CI reliability ·
**Verified in:** `backend/tests/evaluation_v2/test_evaluator.py`,
`backend/evaluation_v2/service.py` · **Fixed by:**
`backend/tests/evaluation_v2/test_evaluator.py`

### Root cause

The shared test evidence fixture expired on `2026-08-01`, while snapshots defaulted
to the current time. The evaluator correctly rejected the expired evidence, but
seven tests expected pre-expiry recommendations and started failing.

### Fix

Evidence timestamps are now fixed (`2026-07-01`–`2026-08-01`) instead of relative
to `datetime.now()`, and every affected test passes an explicit pre-expiry
`evaluation_at`. A dedicated `test_evidence_expiring_on_august_first_is_rejected_after_expiry`
test keeps the expiry-rejection behavior covered. `evaluation_v2/service.py`'s
freshness logic is unchanged.

---

### On-demand lookup behaviour conflicts with the repository contract and ADR

**Status:** resolved · **Priority:** P1 · **Surface:** fund-thesis product contract ·
**Verified in:** `backend/pipeline_runner.py`,
`backend/tests/test_on_demand_lookup_independent.py`, `AGENTS.md`,
`docs/adr/0010-fail-closed-gates.md` · **Fixed by:** `backend/pipeline_runner.py`,
`backend/tests/test_on_demand_lookup_independent.py`, `backend/tests/test_pipeline_execution_semantics.py`

### Root cause

Runtime and tests blocked on-demand lookup without a thesis/published policy. The
documented repository contract, DEVELOPMENT.md, ARCHITECTURE.md, and ADR-0010 say
the opposite: periodic work is thesis-gated, while a named lookup remains
mandate-aware but runs.

### Fix

`run_on_demand_lookup` now catches `EvaluationPrerequisiteError(code="thesis_required")`
specifically and continues without a thesis context (mandate-aware evaluation still
applies when a thesis *is* active); the periodic pipeline's thesis gate is
unchanged. Tests updated to assert the documented behavior, plus a dedicated test
confirming the periodic gate still blocks without a thesis.

---

### Waitlist requests can be reported successful without durable lead capture

**Status:** resolved · **Priority:** P1 · **Surface:** marketing conversion ·
**Verified in:** `web-front-end/api/waitlist.ts`,
`web-front-end/.env.example` · **Fixed by:** `web-front-end/api/waitlist.ts`,
`web-front-end/src/components/AccessForm.tsx`, `web-front-end/.env.example`

### Root cause

An unset recipient defaulted to Resend's `delivered@resend.dev`. The local
configuration documented a backend `/api/waitlist` destination the backend never
implemented, and in local dev the frontend routed straight to that
nonexistent route whenever `VITE_API_URL` was set.

### Fix

`AETHRIA_WAITLIST_NOTIFY_EMAIL` is now required — the handler returns 503 instead
of silently defaulting. Resend delivery (already fail-closed on error) is the one
canonical durable sink; the dead backend-persistence branch and the stale
`VITE_API_URL` routing indirection were removed, so `AccessForm` always posts to
the one working `/api/waitlist` serverless function.

---

### Waitlist input is interpolated directly into notification-email HTML

**Status:** resolved · **Priority:** P1 · **Surface:** marketing security ·
**Verified in:** `web-front-end/api/waitlist.ts` · **Fixed by:**
`web-front-end/api/waitlist.ts`, `web-front-end/scripts/check-waitlist-escaping.mjs`

### Root cause

Name, email, role, firm, and LinkedIn input were only lightly validated and then
inserted directly into HTML, including an unvalidated href.

### Fix

Server-side length limits on every field, LinkedIn parsed and rejected unless a
well-formed `https://` URL, all text and the href HTML-escaped before
interpolation, and provider errors returned generically (no leaked internals). A
runnable check (`npm run check:waitlist`) asserts a malicious name renders as
literal escaped text and a non-HTTPS LinkedIn value is rejected.

---

### Directly executed integration scripts can still load live credentials

**Status:** resolved · **Priority:** P1 · **Surface:** test-cost control ·
**Verified in:** `backend/tests/test_scouts.py`, `backend/tests/test_end_to_end.py`,
`backend/tests/test_partner_flow.py` · **Fixed by:**
`backend/tests/integration_helpers.py`, `backend/tests/test_scouts.py`,
`backend/tests/test_integration_helpers_live_gate.py`

### Root cause

These pytest-skipped modules were also directly executable and loaded `.env` to
perform live pipeline work, bypassing pytest's provider-isolation fixture.

### Fix

`require_openai_api_key()` (the one chokepoint all three scripts already call, or
now call after `test_scouts.py` was migrated onto the same shared helper as the
other two) now requires `RUN_LIVE_TESTS=1` before returning any key — checked at
the point work actually starts, not merely around the `.env` load, so a credential
already present in the shell environment is caught too. A regression test
confirms both the blocked and explicit-opt-in paths.

---

### Production dependency vulnerabilities are not fully visible to CI gates

**Status:** resolved (backend) / decision recorded (frontend) · **Priority:** P1 ·
**Surface:** dependency security · **Verified in:** `backend/requirements.lock`,
`web-front-end/package-lock.json`, `.github/workflows/ci.yml` · **Fixed by:**
`backend/requirements.lock` (`cryptography` 50.0.0, landed on a prior PR),
`web-front-end/package-lock.json` (`brace-expansion` high-severity fix)

### Root cause

`pip-audit` reported `cryptography 49.0.0` vulnerable to `CVE-2026-69247`. The
marketing lockfile had a high-severity dev-only `brace-expansion` DoS and two
moderate React Router advisories; CI fails npm audit only at high severity.

### Fix

`cryptography` is already at 50.0.0. `npm audit fix` resolved the dev-only
`brace-expansion` advisory with no breaking change. The React Router advisories
require a semver-major bump (6→7) that is tightly coupled to `vite-react-ssg` and
risks breaking SSG routing — deliberately **not** force-upgraded here; left as an
explicit product/architecture decision per the original fix direction ("decide
whether moderate production advisories should gate CI"), not a mechanical fix.

---

### The initial agent trigger treats JSON error responses as success

**Status:** resolved · **Priority:** P2 · **Surface:** operator pipeline trigger ·
**Verified in:** `app-front-end/src/api/agents.ts`, `app-front-end/src/App.tsx`,
`backend/api.py` · **Fixed by:** `app-front-end/src/api/agents.ts`,
`app-front-end/src/App.tsx`, `app-front-end/src/App.test.tsx`

### Root cause

`triggerAgents()` parsed JSON without checking `res.ok`. The app marked the
trigger as attempted before awaiting it and only reset on a rejected promise.

### Fix

`triggerAgents()` now throws on a non-2xx response. `App.tsx` separates
"in-flight" from "succeeded" state so a failed trigger resets and a later ready
event can retry. Regression test covers a rejecting 503 response and the
retry-after-failure guard reset.

---

### Flow docket rows are not keyboard-activatable

**Status:** resolved · **Priority:** P2 · **Surface:** operator accessibility ·
**Verified in:** `app-front-end/src/components/queue/DocketCaseRow.tsx`,
`app-front-end/src/components/WorkGrid.tsx` · **Fixed by:**
`app-front-end/src/components/WorkGrid.tsx`,
`app-front-end/src/components/__tests__/WorkGrid.test.tsx`

### Root cause

Rows were focusable `motion.div` elements with `role="button"`, but the keydown
handler (in `WorkGrid.tsx`, where row activation is actually wired) only
supported ArrowUp/ArrowDown.

### Fix

Enter/Space now trigger the same row-selection action a click would, alongside
the existing arrow-key roving focus.

---

### Busy modal focus traps include disabled controls

**Status:** resolved · **Priority:** P2 · **Surface:** operator accessibility ·
**Verified in:** `app-front-end/src/hooks/useFocusTrap.ts`,
`app-front-end/src/components/AgentLogoutModal.tsx`,
`app-front-end/src/settings/FundThesisConfirmationModal.tsx` · **Fixed by:**
`app-front-end/src/hooks/useFocusTrap.ts`,
`app-front-end/src/hooks/__tests__/useFocusTrap.test.tsx`

### Root cause

The focusable-element selector included disabled buttons, so Tab could escape the
trap when every action was disabled during a request.

### Fix

The selector now excludes `:disabled`; when no enabled control exists, focus
lands on the dialog container itself instead of a disabled element.

---

### Reduced-motion preference is incomplete across operator and marketing surfaces

**Status:** resolved · **Priority:** P2 · **Surface:** motion accessibility ·
**Verified in:** `app-front-end/src/components/AgentLogoutModal.tsx`,
`web-front-end/src/App.tsx`, `web-front-end/src/components/AnimatedRoutes.tsx`,
`packages/product-chrome/src/product-chrome.css` · **Fixed by:**
`app-front-end/src/main.tsx`, `web-front-end/src/App.tsx`,
`web-front-end/src/lib/scrollToAnchor.ts`, `web-front-end/src/HomePage.tsx`,
`packages/product-chrome/src/product-chrome.css`

### Root cause

The operator modal container honoured the preference while its nested content
still ran delayed transforms. Marketing always initialized Lenis smooth scrolling
and used `scrollIntoView({behavior: 'smooth'})` unconditionally. The shared live
indicator had no reduced-motion rule.

### Fix

`<MotionConfig reducedMotion="user">` wraps both app roots, so Framer Motion
automatically drops transform/layout animation (keeping opacity fades) whenever
the OS preference is set — covering every nested `motion.*` element, not just
the container. Lenis is skipped entirely under reduced motion; the anchor-scroll
fallback and `HomePage`'s `#access` deep-link scroll use `behavior: 'auto'`
instead of `'smooth'` in that case. `.pc-live-dot`'s pulse animation is disabled
under `prefers-reduced-motion: reduce`.

---

### Decision-threshold controls visibly overshoot and retain a stale drag lean

**Status:** resolved · **Priority:** P2 · **Surface:** fund-thesis interaction ·
**Verified in:** `app-front-end/src/settings/DecisionThresholdsPanel.tsx`,
`app-front-end/src/index.css` · **Fixed by:**
`app-front-end/src/settings/DecisionThresholdsPanel.tsx`, `app-front-end/src/index.css`,
`app-front-end/src/settings/__tests__/DecisionThresholdsPanel.test.tsx`

### Root cause

The drag lean changed only on pointer events (no idle detection), so it never
relaxed while the pointer was held still. The clip-path transition used an
overshooting cubic-bezier for every commit path (drag, keyboard, numeric), and
the dragging-state clip-path transition added an 80ms lag instead of tracking
the pointer exactly.

### Fix

An idle timer (restarted on every pointer move, cleared on release) relaxes the
lean to 0 after ~120ms of no movement while still dragging. The overshoot
cubic-bezier was replaced with the codebase's standard ease-out; the
dragging-state clip-path transition is now `0ms` (exact tracking). Regression
test drives a pointer-down/move via `fireEvent` + fake timers and asserts the
lean returns to `0deg` while `data-dragging` stays true.

---

### Essential secondary text fails WCAG AA contrast

**Status:** resolved · **Priority:** P2 · **Surface:** marketing and shared chrome
accessibility · **Verified in:** `web-front-end/src/index.css`,
`packages/product-chrome/src/LookupResultSnapshot.tsx`,
`packages/product-chrome/src/LookupCommandBar.tsx` · **Fixed by:**
`web-front-end/src/index.css`, `web-front-end/src/components/plates/MarketPlate.tsx`,
`packages/product-chrome/src/LookupResultSnapshot.tsx`,
`packages/product-chrome/src/LookupCommandBar.tsx`,
`web-front-end/scripts/check-contrast.mjs`

### Root cause

Marketing caption text using `--ink-3` (0.44 alpha, 2.69:1) and several
`text-oxford/NN` opacities below 65 (2.13–3.96:1) fell below the 4.5:1
requirement for normal essential text.

### Fix

Every essential-text usage of `--ink-3` now uses `--ink-2` (0.66 alpha, 5.03:1,
already AA-compliant — no new token needed); every `text-oxford/NN` below 65 in
the two named shared components was bumped to `/65` (4.88:1), reusing an
opacity value already in the codebase's scale. Purely decorative border/background
uses of the same tokens were left untouched. A runnable check
(`npm run check:contrast`) asserts both values clear 4.5:1.

---

### Test coverage does not exercise the highest-risk UI and marketing paths

**Status:** partially resolved · **Priority:** P2 · **Surface:** test assurance ·
**Verified in:** `app-front-end/e2e/smoke.spec.ts`, `web-front-end/package.json`,
`packages/product-chrome/` · **Fixed by:** component/integration-level regression
tests added alongside each fix above (tenant switching, threshold dragging,
identity grouping, ownership gate, waitlist escaping) plus one jsdom-diagnostic
cleanup (`app-front-end/src/components/portfolio/__tests__/CrmExportAction.test.tsx`)

### Root cause

The only Playwright coverage was an unauthenticated shell smoke test. Marketing
and product chrome had no dedicated test scripts; some passing operator tests
emitted jsdom navigation and React `act()` diagnostics.

### Fix / what's left

Authenticated two-user account-switching and fund-thesis/pipeline-control
scenarios need real Playwright browser coverage, but this repo's E2E harness has
no Clerk test credentials registered anywhere (`app-front-end/playwright.config.ts`
explicitly runs against a placeholder key) — provisioning that is separate
test-infrastructure work, not a code fix, and was not done here. In its place,
every scenario named in the fix direction now has real, executable coverage at
the component/integration level: two-user tenant switching
(`App.tenant-switch.test.tsx`), threshold dragging (`DecisionThresholdsPanel.test.tsx`),
identity grouping (`test_identity_repository_unit.py`, `test_identity_endpoints.py`,
`IdentityReviewQueue.test.tsx`), and waitlist form/security
(`check-waitlist-escaping.mjs`). One jsdom "Not implemented: navigation" diagnostic
was removed by stubbing `HTMLAnchorElement.prototype.click` for the blob-download
test that triggered it; the AnimatePresence `act()` warnings in
`settingsRoomLayout.test.ts` / `SettingsPagePolicyRecovery.test.tsx` were not
tracked down — flagged as remaining follow-up.

---

### Marketing SSG renders time-dependent values during hydration

**Status:** resolved · **Priority:** P3 · **Surface:** marketing rendering ·
**Verified in:** `web-front-end/src/components/GalleryFrame.tsx`,
`web-front-end/src/components/plates/AccessPlate.tsx`, `web-front-end/vite.config.ts` ·
**Fixed by:** `web-front-end/src/components/GalleryFrame.tsx`,
`web-front-end/src/components/plates/AccessPlate.tsx`

### Root cause

The pre-rendered pages calculated a day-of-year edition number and copyright
year during render — both computed identically at SSG build time and at
client hydration, so a day/year boundary between the two produced a mismatch.

### Fix

Both values are now computed in a post-mount `useEffect` (never during SSR) with
an em-dash placeholder rendered until then — confirmed in the built HTML output.

---

### The mobile-menu trigger does not announce its expanded state

**Status:** resolved · **Priority:** P3 · **Surface:** operator accessibility ·
**Verified in:** `app-front-end/src/components/MobileHeader.tsx`,
`app-front-end/src/components/AppFrame.tsx` · **Fixed by:**
`app-front-end/src/components/MobileHeader.tsx`, `app-front-end/src/components/AppFrame.tsx`,
`app-front-end/src/components/__tests__/MobileHeader.test.tsx`

### Root cause

The trigger had `aria-controls`, but `AppFrame` owned the open state and never
passed it back as `aria-expanded`.

### Fix

`AppFrame` now passes its `mobileMenuOpen` boolean down as `isOpen`, rendered as
`aria-expanded` on the trigger.

---

### Cloud Run still receives an unused Exa secret

**Status:** resolved · **Priority:** P3 · **Surface:** deployment configuration ·
**Verified in:** `cloudbuild.yaml` · **Fixed by:** `cloudbuild.yaml`

### Root cause

Tracked application code, tests, dependency configuration, and the environment
registry had no Exa client or `EXA_API_KEY` reader, but Cloud Build still injected
that secret into Cloud Run.

### Fix

Confirmed Exa is fully retired from application code (only test fixtures and this
doc referenced it); removed `EXA_API_KEY` from the Cloud Run `--set-secrets` list.

---

### Fabricated and mangled data reached a confidential IC pack

**Status:** resolved · **Priority:** P0 · **Surface:** investment decision integrity ·
**Verified in:** one exported IC pack (CameraMatics, 2026-07-31) audited against
its row in `aethria-prod` · **Fixed by:** `726d556e`, `d1c5df65` (#50)

Six distinct defects, all confirmed against the stored record rather than
inferred, surfaced by manually auditing one real exported memo.

### Root cause

1. **Invented company identifier, persisted.** The Scout prompt asked the model
   for `"id": "uuid"`; `_normalize_scout_ids_inplace` only minted a server-side
   id when the model omitted one, so a compliant model's fabricated UUID always
   won. The stored row's `startup_id` was the textbook placeholder
   `a1b2c3d4-e5f6-4711-9abc-1234567890ab`, printed as "Company ID" on a
   confidential document.
2. **A company resolved as a founder.** "Blueprint Sales Solutions" passed the
   person-name shape test (three capitalised words, no org marker) and became
   `role=CEO` on the record, then "the founders' industry pedigree" in the
   reviewer summary — scraped from an unrelated role on someone else's LinkedIn.
3. **Retrieved traction was reported as missing, and it changed the decision.**
   The reviewer flagged "Missing revenue or traction data" and the partner
   passed partly on that basis, while the same row held concrete firmographics
   (employee count, revenue range, funding rounds) inside a founder-evidence
   snippet nothing read.
4. **A document disagreed with itself on scores** — `int()` truncation printed
   "Execution 4/10" beside a table showing 4.8 for the same field.
5. **Raw floats reached the page** — "Product 5.403333/10".
6. **PARTIAL identity and founder resolution were never surfaced.** Both were
   `PARTIAL` at confidence 0.6 while the pack read as settled fact, and the
   sources list mixed pages actually read with URLs gap-retrieval merely
   surfaced.

### Fix

The company id is now always minted server-side; the prompt no longer asks
for one. Business descriptors are now the org-marker signal for person-vs-company
resolution (with "Sales"/"Global"/"Digital" deliberately excluded — real
surnames and plain adjectives). `utils/traction_extraction.py` lifts
firmographics out of evidence with rules only (no LLM) into
`ScoutInfo.traction_facts` and the reviewer prompt, and now flows through to
the API, frontend types, and both the markdown memo and IC pack renderers —
an unmatched pattern still yields no key, so genuinely absent evidence still
reads as absent. Scores render at one decimal place everywhere. Unread
sources are now marked, and resolution status (including `PARTIAL`) is
stated on the record rather than implied as settled.

### What not to do

Do not treat "the model didn't set a field" as "the field doesn't need a
value" — the fabricated UUID happened because the code only filled the gap
the model left, so a fabricating model's answer always won over a correct
server-generated one. Server-authoritative fields must be set unconditionally,
never merged with a model's optional output.
