# Full Codebase Audit — Findings and Sequencing

**Date:** 2026-08-18. Eight adversarial, code-verified audits run in parallel (not
confirmatory — each agent explicitly instructed to hunt for bugs, cite exact
`file:line`, and only report findings traced against the actual source), covering
every subsystem in the repo: `backend/reviewer` + `backend/partner`,
`backend/portfolio` + `backend/meta` + `backend/monitoring` + `backend/fund_intelligence`,
`backend/decisions` + `backend/evaluation_v2` + `backend/triage` + `backend/outcomes`,
`backend/identity` + `backend/ingest` + `backend/authority` + `backend/services/scoring`,
`backend/jobs` + pipeline runner/concurrency, `backend/routers` + `backend/security`
(tenancy boundary), `app-front-end/src`, and `web-front-end` + `packages/product-chrome`
+ both migration directories.

**Status: CRITICALs fixed and live-validated same day; HIGH/MEDIUM/LOW
documented and sequenced, not yet implemented.** Same pattern as the
2026-08-17 Scout/evidence audit.

## CRITICALS — all 3 fixed and live-validated, 2026-08-18

- **F1 (same-named-company identity merge):** `identity/acquisition.py`'s
  `operator_confirmed_identity` now only fires when the domain this
  observation actually resolved to (`observed_domain`) matches the operator's
  `lookup_website` hint, instead of firing whenever ANY hint was supplied.
  New regression test
  (`test_operator_confirmation_does_not_apply_to_a_same_named_different_domain`)
  proves a same-named-different-domain candidate no longer inherits the
  operator's confirmation. Live-validated: dispatched "Anthropic Research
  anthropic.com" — confirmed `company_resolution.website` genuinely matched
  the hint (`anthropic.com` == `anthropic.com`), so the legitimate-match case
  still works correctly.
- **F2 (uncaught `IdentityConflictError` crashes the pipeline cycle):**
  `pipeline_runner.py`'s `_admit_autonomous_discoveries` now (a) checks
  whether the opportunity already has a linked legacy startup row before
  creating a new one via `storage.add_discovery` in the not-yet-persisted
  path, reusing the existing row instead of duplicating it, and (b) wraps
  `link_admission_projection` in a try/except that logs and continues on
  `IdentityConflictError` instead of letting it propagate and kill the whole
  cycle — critically, without skipping canonical claims persistence for that
  discovery (an early draft of the fix over-broadly `continue`d past it;
  caught in self-audit before shipping, since claims persistence only
  depends on `admission.company_id`/`opportunity_id`, not the legacy link).
  Two updated tests (`test_two_personas_same_domain_keep_two_observations_one_opportunity`,
  now with a mock that faithfully reproduces the real DB guard instead of a
  no-op that silently passed regardless of the underlying bug) plus one new
  test for the not-yet-persisted reuse path. **Live-validated on a real,
  naturally-occurring conflict**, not a contrived one: dispatching "Anthropic
  Research anthropic.com" created a brand-new legacy startup row that
  canonical identity correctly resolved to the SAME opportunity as
  yesterday's "Anthropic" dispatch — whose `legacy_startup_id` was already a
  DIFFERENT row. Confirmed in the DB that the opportunity's
  `legacy_startup_id` stayed at the first-linked value and the dispatch
  completed end-to-end (PASS ruling, memo rendered) instead of crashing.
- **F3 (stale migration-path documentation + no RLS on the live path):**
  Updated `AGENTS.md` invariants #7 and #10 and the directory listing to name
  `db/migrations/` (applied via `DATABASE_URL` by
  `backend/db/migration_runner.py`) as the live/authoritative path, and
  `supabase/migrations/` as historical-only. Flagged the RLS gap explicitly
  in both the invariant and the "Security and data" section rather than
  silently leaving the doc implying RLS coverage that doesn't exist on the
  live path. **The RLS decision itself (add policies vs. explicitly accept
  app-layer-only tenancy) is a product/architecture call, not made here** —
  flagged for the user per the audit's own suggested sequencing.

Full backend suite after all three: 2281 passed, same 39 pre-existing
Postgres-container failures (environment, not code), zero regressions.

---

## CRITICAL

**F1. A same-named different company can be silently merged into the wrong
canonical company record.** `backend/identity/acquisition.py:126-129`.
```python
"operator_confirmed_identity": bool(
    is_named_lookup and str(discovery.get("lookup_website") or "").strip()
),
```
This flag is set to `True` whenever the operator supplied *any* `lookup_website`
for a named lookup — it never checks that the flag applies to the domain that
actually ends up marked verified. `observed_domain` (the domain that gets
VERIFIED) is computed independently, from the scout's own discovered
references. In `identity/normalization.py`'s `_domain_is_verified`, this flag
short-circuits every other check (`if operator_confirmed_identity: return True`).
**Same bug class as the Anthropic description-theft bug fixed earlier
today (`c0ccb7e0`)** — an anchor-host check skipped for one code path — except
here the blast radius is a full company-identity merge, not just a wrong
description: `IdentityService.admit()` can attach a new observation/opportunity
onto a completely unrelated existing company, with no NEEDS_REVIEW case opened
(violates AGENTS.md invariant #5, fail-closed on ambiguous identity). Fix
direction: only set `operator_confirmed_identity: True` when
`normalize_domain(observed_domain) == normalize_domain(lookup_website)`.

**F2. `IdentityConflictError` is never caught, and can crash an entire
periodic pipeline cycle while leaving permanent orphan `startups` rows.**
`backend/pipeline_runner.py:640-652`, `backend/identity/repository.py:853-877`.
For autonomous (non-persisted) discoveries, `storage.add_discovery` is called
**unconditionally** — never gated on whether `IdentityService.admit()` actually
created a new canonical company (`admission.created`). When two personas (or
two cycles) independently rediscover the same company, the canonical layer
correctly dedupes, but the legacy-projection insert still fires every time,
and `link_legacy_projection`'s guard (`where legacy_startup_id is null or =
$3`) throws `IdentityConflictError` on the second attempt. That exception is
raised nowhere-caught (verified via repo-wide grep) and propagates to the
outer `except Exception` in `pipeline_runner.py`, turning the **whole cycle**
into a `scout_stage_failed` — Reviewer/Partner/Portfolio/Meta never run for
that cycle. The repo's own test
(`test_two_personas_same_domain_keep_two_observations_one_opportunity`) proves
this fires in normal steady-state operation (two personas, one cycle), not
just on retries — and its mock repository is a no-op that doesn't reproduce
the real "already linked" guard, so it green-lights code that throws in
production. A retried `pipeline_cycle` job re-runs Scout from scratch (see H10
below), so this can loop to dead-letter, leaving N orphan `startups` rows per
affected company. Fix direction: check `admission.created` before persisting;
catch `IdentityConflictError` at the call site as an expected "already
admitted" outcome, not a stage failure.

**F3. The documented migration contract is stale — production runs a
different migration path with zero RLS policies.**
`backend/env_config.py:54-55`, `db/migrations/README.md`,
`backend/evidence/repository.py:83,126`.
`USE_SUPABASE_STORAGE` is explicitly commented `"Deprecated compatibility
switch; normal runtime persistence uses DATABASE_URL."` A separate runner
(`backend/db/migration_runner.py`) applies `db/migrations/*.sql` against
`DATABASE_URL` via its own ledger table, and its own README says
`supabase/migrations/` files "are not edited or re-applied by this system."
Confirmed two real migrations from earlier today
(`20260817000001_evidence_artifact_retrieval_attribution.sql`,
`20260817000002_evidence_items_content_dedup.sql`, both live-applied and
exercised by real code) **do not exist under `supabase/migrations/` at all.**
Meanwhile AGENTS.md invariant #7 and #10 still say "New timestamped file in
`supabase/migrations/`... Production requires Supabase." Worse: **every one
of the 22 `db/migrations/*.sql` files that creates a `user_id`-scoped table
has zero RLS policies** (verified by grepping all files for
`row level security|create policy`) — the actually-live path has no
database-level tenant-isolation backstop at all; it rests entirely on
application-layer `require_user_id()` with nothing to catch a missed
`WHERE user_id = $1`. Fix direction: update AGENTS.md/CLAUDE.md to name
`db/migrations/` as authoritative and either archive `supabase/migrations/`
explicitly or decide/document the RLS story for the live path (add policies,
or explicitly accept app-layer-only tenancy and say why).

---

## HIGH

**H1. `validate_partner_output` crashes with `UnboundLocalError` instead of
the intended `ValueError` when `conviction_level` is missing.**
`backend/partner/schema.py:101-116`. `conf` is read (to backfill
`conviction_level`) before it's assigned a few lines later. The repair-retry
path in `PartnerEngine._decide_and_save` only catches `ValueError`, so a
repaired LLM payload still missing `conviction_level` throws an unhandled
exception instead of a graceful "invalid output, mark failed." Fix: move the
`conf = float(...)` parse above its first use.

**H2. Analyst-supplied `operator_context` bypasses prompt-injection isolation
in the reviewer LLM prompt.** `backend/reviewer/base.py:821-831`. Explicitly
documented in-code as untrusted text that can include "fetched content of any
links," concatenated raw into the prompt with only a prose warning — no
`isolate_untrusted_text`/`flag_prompt_injection`, unlike the identical pattern
already used for scout lookup fields (`scout/base.py:1286-1302`).

**H3. `HealthMonitor`'s duplicate/inactivity/memory-bloat checks compute
findings and then discard them.** `backend/portfolio/health.py:83-195`. Each
check computes severity+description, logs a warning, then `return None`
unconditionally — commented `# For now, just log.` The hourly system-health
layer described in the module docstring is inert; nothing is ever persisted
or surfaced.

**H4. Meta prompt-mutation LLM calls bypass `CostController` entirely.**
`backend/meta/mutator.py:515-534`, `backend/meta/agent.py:203-233`. Confirmed
via grep: none of `CostController`'s four budget methods are referenced
anywhere in `backend/meta/*.py`. `_run_cycle_sync` fires one LLM call per
mutation target with no cap on target count and no budget check — direct
violation of AGENTS.md invariant #8.

**H5. Triage escalation path is write-only — non-`DEEP_REVIEW` dispositions
vanish forever.** `backend/triage/repository.py:35-42` (`get_latest`) has
zero callers anywhere in the backend; no router exposes `triage_assessments`;
no frontend hook references "triage." `INSUFFICIENT_EVIDENCE`,
`OUT_OF_MANDATE`, and `LIGHT_MONITOR` all short-circuit the pipeline to
`status="completed"` with the assessment inserted into a table nobody ever
reads again — `LIGHT_MONITOR` implies ongoing monitoring that doesn't exist.

**H6. Hardcoded decision-relevant thresholds in `backend/triage/service.py`.**
Lines 33/41/47/50: `admission.confidence < 0.5` (the identity floor gating
`DEEP_REVIEW` vs. permanent drop per H5), plus priority ints and confidence
caps — none sourced from `resources/config/`. Direct AGENTS.md invariant #3
violation on a genuinely decision-relevant number.

**H7. `EvaluationRepository.evaluate()` can silently reopen an
already-`invested`/`completed` opportunity's workflow state.**
`backend/evaluation_v2/repository.py:101-110,242-248`,
`backend/authority/repository.py:404-420`. The re-entry guard only checks
`service_level <= 0` and `decision_state == "archived"` — not `invested`,
`completed`, or `monitoring`. Every successful `evaluate()` unconditionally
transitions `workflow_state` back to `ruling_pending`, and
`transition_workflow_on_connection` performs no state-machine legality check
at all. A re-triggered lookup/dispatch on an already-INVESTED company can
silently overwrite `current_recommendation_id` and flip workflow state back
to pending, as if the investment never happened (the underlying
`human_rulings`/`decision_state` record is untouched, but the operational
workflow state the UI keys off of is corrupted).

**H8. Client-controlled evidence trust/verification flags let any
authenticated user inject fabricated "verified" claims into the decision
engine.** `backend/routers/opportunities.py:15-19` (`ManualLookupBody`)
accepts untyped `references`/`claims` dicts forwarded verbatim into
`opportunity_pipeline.py:131-224`: `trust_class=OFFICIAL if ref.get("official")`,
`verification_state=VERIFIED if ref.get("verified")`, and omitting
`assertion_class` **defaults a claim to `EXTERNALLY_VERIFIED`**, the highest
trust tier. These feed directly into `evaluate()`. Contrast with the
`confidential-evidence` endpoint, which hardcodes trust server-side —
`opportunities.py` is the outlier. Any authenticated user can submit a
fabricated "$50M ARR" claim marked externally-verified with no gate.

**H9. `/api/opportunities/manual-lookup` has no rate limiting despite
triggering an LLM evaluation.** `backend/routers/opportunities.py:23-43`.
Unlike the legacy lookup endpoint (`_LOOKUP_MINUTE_POLICY`/`_LOOKUP_DAY_POLICY`
+ in-flight dedup lock), this endpoint has zero rate-limit/lock calls — an
authenticated user can loop it with distinct company names for unbounded LLM
cost.

**H10. Checkpoint-resume was applied only to `company_lookup`, not to the
periodic `pipeline_cycle` job — a retry re-runs Scout (and everything
downstream) from scratch.** `backend/jobs/handlers.py:56-136`.
`run_one_pipeline_cycle` takes no checkpoint callback at all (only
`run_on_demand_lookup` does). A `pipeline_cycle` job retried after a
transient failure past the Scout stage re-does full LLM discovery — real
cost, and the direct trigger condition for F2.

**H11. `javascript:`-scheme URLs from LLM/scraped fields render as clickable
links with no scheme validation.** `app-front-end/src/components/InvestmentMemoContent.tsx`
(8 sites), `IdentityResolutionDrawer.tsx:162`, `MemoDecisionBrief.tsx:27`.
`companyResolution.website`, `linkedin_url`, founder social links, and
`evidence_urls` — all untrusted per the backend's own threat model — become
`href` values with no scheme allowlist. A `javascript:...` value in a
retrieved field executes in the app's origin on click.

**H12. Startup-acknowledgement failures are silently swallowed with no
rollback.** `app-front-end/src/hooks/useAcknowledgeStartup.ts:33-40`,
`api/startups.ts:152-163`. `acknowledgeStartup` returns `null` on any
non-2xx response instead of throwing; the hook applies an optimistic
`is_new_to_user: false` update immediately and does nothing on failure — no
error, no toast, no rollback. The operator sees an item marked "seen" that
the server never recorded.

**H13. Zero RLS policies in the now-authoritative migration path.** See F3 —
listed here too since it's independently actionable (add RLS, or explicitly
document why not) regardless of the documentation-drift fix.

**H14. The one automated XSS-escaping guard for the waitlist form isn't run
in CI.** `web-front-end/package.json` defines `check:waitlist` (guards
`api/waitlist.ts`'s hand-rolled `escapeHtml()`, which builds an HTML email
from user-submitted fields) and `check:marketing`, but
`.github/workflows/ci.yml`'s `web-frontend` job only runs
`lint`/`build`/`check:bundle`. A future edit that weakens escaping would ship
undetected. Also out of sync with AGENTS.md's own documented gate.

---

## HIGH — 11 of 14 fixed and live-validated, 2026-08-18; H5/H10/H13 deferred

Scoped after reading each: H10 (checkpoint-resume for the periodic pipeline
cycle) requires threading checkpoint state through the entire multi-stage
orchestration function -- a real architectural change, not a surgical fix,
comparable in size to yesterday's deferred MEDIUM items. H5 (triage
escalation surfacing) needs a product decision on what "surface pending
triage dispositions" actually means UX-wise. H13 (RLS) is the same deferred
decision as F3 above.

- **H1** (`partner/schema.py` `UnboundLocalError`): moved the `conf = float(...)`
  parse above the `conviction_level` backfill that reads it.
- **H2** (`reviewer/base.py` operator_context prompt injection): wrapped in
  `isolate_untrusted_text` + `prompt_safety_instruction()`, matching the
  scout-side pattern.
- **H3** (`portfolio/health.py` dead health checks): confirmed nothing
  downstream reads a persisted record beyond `len()` of the return list
  (`engine.py`'s `_run_health_sync`, and an unasserted print-only smoke
  script) — persisting `SystemHealthRecord`s nobody queries would be unused
  infrastructure. Checks now return the `check_type` string that fired
  instead of always `None`, with severity in the log line.
- **H4** (meta prompt-mutation bypasses `CostController`): registered a
  `"meta"` budget/cooldown, wired `cost_controller` through
  `PromptMutator`/`MetaAgent`/`pipeline_runner.py`. **Self-audit catch**:
  the first version used a single shared `agent_id` (`self.user_id`) for
  every mutation target in a cycle — since `CostController`'s cooldown keys
  on `agent_id`, the first target's call would silently deny every sibling
  target in the same cycle via the cooldown, not just the intended daily
  ceiling. Fixed to use the per-target agent name as `agent_id`. New
  regression test proving both budget denial and the per-target fix.
- **H6** (hardcoded triage thresholds): new `resources/config/triage_rules/v1.json`
  + `core.policy_resolver.get_triage_rules()`, same pattern as
  partner_rules/reviewer_rules/evaluation_rubric. `TriageService.assess()`
  now reads the identity-confidence floor and every disposition's
  priority/confidence-cap from there.
- **H7** (`evaluate()` can reopen an INVESTED opportunity): added
  `decision_state == "invested"` and `workflow_state in ("completed",
  "monitoring")` to the existing re-entry guard (previously only checked
  `"archived"`). Two new tests using the file's existing mocked-connection
  pattern.
- **H8** (client-controlled evidence trust flags in manual-lookup):
  `trust_class`/`verification_state`/`assertion_class` are now server-derived
  (`TrustClass.OPERATOR`, `VerificationState.UNVERIFIED`,
  `AssertionClass.OPERATOR_ASSERTED`) regardless of what the client sends.
  Left `UNVERIFIED` rather than the confidential-evidence endpoint's
  `VERIFIED` deliberately — this path accepts bulk, self-graded, structured
  data at conviction-bearing volume with no way to verify it server-side, so
  the existing `require_verified_evidence` policy gate correctly excludes it
  from automated scoring eligibility, the same mechanism already governing
  every other evidence path.
- **H9** (manual-lookup has no rate limit): now shares
  `LOOKUP_MINUTE_POLICY`/`LOOKUP_DAY_POLICY` with the legacy lookup endpoint.
- **H11** (`javascript:` URL injection in memo UI): new `safeHref()` helper
  in `lib/memoReferenceHref.ts` (scheme-allowlists http/https), wired into
  all genuinely-vulnerable sites in `InvestmentMemoContent.tsx`,
  `IdentityResolutionDrawer.tsx`, `MemoDecisionBrief.tsx`. One site
  (`InvestmentMemoContent.tsx`'s `analystContext` link) was already gated by
  an equivalent scheme check and didn't need touching.
- **H12** (silent startup-acknowledgement failure): `useAcknowledgeStartup`
  now rolls the optimistic cache write back to the pre-acknowledgement
  startup on both a `null` response and a thrown error, plus logs via
  `console.error` (no toast system exists in this codebase to surface it
  visually — building one would be new scope, not a surgical fix).
- **H14** (waitlist XSS guard not run in CI): added `check:waitlist` and
  `check:marketing` to the `web-frontend` CI job.

**Verification:** full backend suite 2297 passed (same 39 pre-existing
Postgres-container failures), full frontend suite 489 passed, lint/build/
bundle-budget clean. Live-dispatched Notion Labs end-to-end through the
actual running app after restarting the backend — completed cleanly (PASS
ruling, no crash) exercising H1/H2/H7 and general pipeline stability under
real traffic. H8/H9 validated via a `TestClient`-based test against the real
FastAPI app and real rate limiter (the manual-lookup endpoint isn't wired
into the current UI, so a browser dispatch wouldn't reach it).

---

## MEDIUM

**M1. LLM-reported `human_review_required` can suppress escalation for
non-red-flag trigger reasons.** `backend/partner/decision.py:2320`. Only
`has_red_flags` force-overrides to `True`; grey-zone/contradiction/missing-
assumption triggers trust the model's own judgment on whether to escalate.

**M2. `PortfolioEngine.cost_controller` is instantiated but never called
anywhere in `portfolio/`.** `backend/portfolio/engine.py:101`. A
budget-enforcer that enforces nothing — misleading, though harmless today
since nothing in `portfolio/` makes LLM calls.

**M3. Full-table read/replace on a per-tenant metrics table, violating
row-level-storage invariant #4.** `backend/portfolio/feedback.py:282-303`
(`_calculate_verdict_distribution`) is the only call site of `_write_file` in
the codebase — reads the entire `agent_metrics` table, mutates in memory,
writes it all back, creating a lost-update race against any concurrent
`add_agent_metric` call.

**M4. Hardcoded, triplicated threshold in `backend/meta/calibrator.py`.**
`default_weak = 6.0` appears as a bare Python literal at three call sites
with no `resources/config/` backing. Mitigated by `apply()` always raising
(proposal-only, never auto-published) but still invariant #3 drift.

**M5. Same "one self-reported number gates independent decisions" disease
recurs in `evaluate_snapshot`.** `backend/evaluation_v2/service.py`.
`confidence_at_snapshot` simultaneously gates score eligibility, weights the
criterion average, AND composes the reported confidence — no independent
cross-check anywhere in the file. Same pattern as the C4 bug fixed
yesterday, recurring in a different function.

**M6. `is_production_env()` fails open when deployment env vars are
unset.** `backend/env_config.py:401-416`. Returns `False` (dev) rather than
erroring when none of `ENVIRONMENT`/`APP_ENV`/`FASTAPI_ENV` is set — silently
exposes `/docs`/`/openapi.json`/`/redoc`, defaults the admin dashboard to
**enabled**, and weakens rate-limiting, all with no log line. Real risk given
the in-progress Oracle/Coolify infra migration.

**M7. `/api/admin/*` auth is prefix-based and opt-in per route, not
structurally enforced.** `backend/api.py:1474,1490`. Both existing admin
routes correctly call `_require_admin_claims` today, but nothing would catch
a future admin route that forgets to.

**M8. Raw hex colors bypass the design-token system.**
`app-front-end/src/settings/DecisionThresholdsPanel.tsx:17-21`,
`lib/fundConfiguration.ts:338-343,732-741`. Direct AGENTS.md violation
("named design tokens only, no raw hex").

**M9. Cooperative-fencing gap between lease reclaim and zombie-worker
discovery.** `backend/jobs/worker.py:73-100`, `repository.py:308-374`. A
reclaimed job's original owner only notices at its next heartbeat tick
(default 20s) — a narrow but real double-execution window for
non-checkpointed side effects in that gap.

**M10. `/api/waitlist` has no rate limiting on a public, cost-triggering
endpoint.** `web-front-end/api/waitlist.ts`. Trivial to script; burns Resend
send quota with no throttle.

---

## LOW (worth noting, not urgent)

- Dead computation: `HealthMonitor._run_cluster_analysis` runs
  `ClusterAnalyzer.analyze()`, discards the result, and logs only — the value
  that actually reaches the mutator comes from a separate, independent
  computation in `meta/analyser.py`. `PortfolioEngine.cluster_analyzer` is
  instantiated but never referenced. (`backend/portfolio/health.py:156-175`,
  `engine.py:103`)
- Unreachable landmine: a defensive `None`-row fallback in
  `fund_intelligence/repository.py:502-508` references an undefined
  `version_id` — would raise `NameError` if the query ever gains an
  `ON CONFLICT` clause that makes the branch reachable.
- `investment_transition_is_allowed` (`backend/decisions/service.py:35-37`)
  is dead code; the real gate is inline in the repository. Misleading, not
  broken.
- Unbounded in-process `_user_locks` dict in
  `backend/pipeline_concurrency.py:16,41-47` — slow memory leak per distinct
  tenant, and the concurrency cap it enforces is process-local (doc claims a
  global cap; confirm before scaling workers horizontally).
- Unbounded per-item string sizes in `ManualLookupBody.references`/`.claims`
  (`opportunities.py:19-20`) — list length capped, individual field length
  isn't, inconsistent with sibling fields in the same file.
- Waitlist "Position #N" UI (`web-front-end/src/components/AccessForm.tsx:88`)
  reads a `position` field the API never returns — dead UI, not a bug.

---

## Suggested sequencing

Mirroring the 2026-08-17 audit's approach: smallest-safe-fix-first within each
severity band, but a few items need a product/architecture call before
touching code:

1. **F1, F2** — both are the exact "anchor/gate check skipped for one path"
   bug class already fixed twice today; likely safe to fix directly once
   prioritized, same shape as yesterday's batch.
2. **F3 / H13** — needs a decision: is RLS actually wanted on the live
   Postgres path, or is app-layer `require_user_id()` the accepted tenancy
   model going forward? Not mine to decide; fixing the doc drift alone is
   safe and should happen regardless.
3. **H8, H9** — real, exploitable-today security gaps on a public endpoint;
   high priority once decided.
4. **H1, H10, H11, H12** — bounded, surgical fixes, same shape as yesterday's
   HIGH batch.
5. **H5, H6, H7** — the triage/decision-workflow findings need a product call
   on intended triage behavior (should `LIGHT_MONITOR` actually monitor
   something? what should re-evaluating an INVESTED opportunity do?) before
   fixing, not a blind patch.
6. **H4, H14** — mechanical, low-risk, batchable with the above.
7. Remaining MEDIUM/LOW items — batchable once the above are sequenced.
