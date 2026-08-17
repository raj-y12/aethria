# Legacy/Canonical Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the migration approved in [docs/archive/specs/2026-07-15-evidence-decision-platform-design.md](../specs/2026-07-15-evidence-decision-platform-design.md) — collapse the two independent, disagreeing recommendation systems (legacy `partner`/`reviewer` and canonical `evaluation_v2`) into one, so the product has a single source of truth instead of two engines that can silently contradict each other.

**Architecture:** Strangler migration, not a rewrite — per §21.1 of the source spec, this is a *master* plan; each sub-project below gets its own detailed task-by-task plan before implementation begins, written by whoever picks it up, after reading the actual files involved (not from this document alone). This document exists to sequence the sub-projects correctly and record why each one is scoped the way it is.

**Tech Stack:** Python 3.12, FastAPI, asyncpg/PostgreSQL, Pydantic. No new dependencies.

## Global Constraints

- Explicit `user_id` tenancy on every storage call, constructor, and job (invariant 1).
- Thresholds are versioned policy data in `resources/config/`, never hardcoded in Python (invariant 3). Any threshold discovered hardcoded during this work gets extracted, not just relocated to a different Python file.
- Row-level storage; never delete-and-rewrite a tenant's rows (invariant 4).
- Fail closed: missing thesis, ambiguous identity, thin evidence, or an unconfigured dependency produces a named block (invariant 5).
- Migrations are append-only; never edit an applied migration (invariant 7).
- No model call where a rule already works (invariant 8).
- Public API shapes, SSE events, persisted rows, enum values, and policy files are contracts — additive changes only unless a sub-project explicitly says otherwise and updates API.md in the same change.
- Never weaken or delete a test to make a change pass.

---

## Why this exists (context for a fresh reader)

Two systems currently run for every dispatch and produce two independent recommendations from overlapping evidence:

- **Legacy**: `scout/` (2,556 lines, 4 personas) researches a company and writes narrative JSON onto `startups`. `reviewer/` (3,525 lines, 3 personas) scores it via `services/scoring/*` into `structured_scoring`. `partner/decision.py` (2,210 lines, one file) applies rule-based thresholds to produce a recommendation. `portfolio/store.py` (531 lines) persists portfolio effects.
- **Canonical**: `identity/` resolves company/opportunity identity. `evidence/` holds claims and evidence artifacts (populated today by extracting facts out of scout's narrative output, not by independent retrieval). `evaluation_v2/service.py`'s `evaluate_snapshot()` scores claims deterministically and produces its own recommendation, stored via `evaluation_v2/repository.py`. `decisions/` records the human ruling. `portfolio/repository.py` (151 lines) is the canonical portfolio store, wired but barely used.

The canonical evaluator now runs for every dispatch (bridged in `backend/jobs/handlers.py::_execute_company_lookup`, 2026-08-16), but nothing reconciles its output with the legacy `partner/decision.py` recommendation or the legacy reviewer's `structured_scoring`. A reader can see "Blocked by evidence" from canonical and five confident dimension scores from legacy on the same document.

Per the source spec's own Phase 4 exit criteria (never completed): *"Current PartnerEngine adapted behind RecommendationEngine"* and *"Existing startup and memo APIs served from compatibility projections."* This plan finishes that.

## Sequencing

Four sub-projects, in this order. Each is independently shippable and testable — do not start sub-project N+1 until N's acceptance criteria pass in CI.

1. **Partner-behind-evaluator** — the recommendation itself stops disagreeing with itself. Highest leverage, does first.
2. **Reviewer scoring collapse** — the Assessment scores stop being a second, unreconciled scoring system.
3. **Portfolio store consolidation** — one portfolio persistence path instead of two.
4. **Canonical evidence extraction** — only attempt once 1–3 are done; this is the one that eventually lets scout's persona pipeline shrink, and it's the riskiest because nothing else does company research today.

---

### Sub-project 1: Partner-behind-evaluator

**Detailed task-level plan:** [2026-08-16-partner-behind-evaluator.md](2026-08-16-partner-behind-evaluator.md).

**Objective (corrected after a full read of `partner/decision.py` and `partner/engine.py`):** "retire outright" was wrong — `partner/decision.py` is not a redundant duplicate scorer, it holds real investment-committee policy with no canonical equivalent (mandate-fit gating with an IC-exception override, an ownership-conflict fail-closed check, a portfolio-concentration adjustment, six risk/driver predicates, and a genuine LLM-escalation exception path for ambiguous cases — plus the audited `conviction=8` hardcode). Only the threshold ladder itself (`_canonical_recommendation`) duplicates canonical and is safe to delete outright. Everything else needs porting to a canonical home as small, reused functions, not a second large engine — see the sub-plan for the ponytail-lens breakdown of what reuses existing code (`check_ownership_conflict`, `partner_rules.mandate_fit` config, canonical's own per-criterion coverage state) versus what's genuinely new.

**Acceptance criteria:**
- A dispatch produces exactly one recommendation, not two, reachable from the memo/startup APIs.
- No API response field is renamed or removed without an API.md update in the same change (additive only, or an explicitly announced breaking change with a version note).
- The `conviction=8` hardcoded branch and any other threshold found hardcoded in `partner/decision.py` is extracted into `resources/config/partner_rules/`, versioned, and covered by `backend/tests/evaluation_v2/test_partner_rules_contract.py`.
- `backend/tests/evaluation_v2/test_partner_rules_contract.py` and `backend/tests/test_decision_safety_certification.py` (or their successors) pass.
- No caller of the old `partner/decision.py` recommendation silently gets a different answer for the same evidence — a golden-set regression comparison (legacy output vs. new output, same inputs) is part of the required tests for this sub-project, not optional.

**Required tests:** golden-set comparison (old vs. new recommendation for a fixed evidence snapshot, asserting equivalence or an explicitly-reviewed intentional change); contract test extension for any newly-versioned threshold; existing `test_decision_safety_certification.py` continues passing unmodified in spirit (extend, don't weaken).

**Prohibited:** deleting `partner/decision.py`'s test suite instead of updating it; silently changing a recommendation threshold as a side effect of the refactor (any behavior change must be a deliberate, separately-reviewed decision, not a refactor accident).

---

### Sub-project 2: Reviewer scoring collapse

**Objective:** `reviewer/`'s three personas stop independently producing `structured_scoring` for Assessment. Scoring authority moves entirely to `evaluate_snapshot()`. Reviewer's remaining job is exactly what ADR-0012 already scoped for it: `founder_fluency`, `capability_slope`, `reframe` — narrative only, never a score input.

**Files to read fully before writing a task-level plan:**
- `backend/reviewer/engine.py` (1,657 lines) and `backend/reviewer/base.py` (1,290 lines) — find every place `structured_scoring` is produced and every consumer of it (the frontend's `AssessmentScorecard.tsx` is the main one, confirmed this session).
- `backend/services/scoring/*` (4,436 lines across 9 files) — determine exactly which layers (`extraction_layer`, `normalization_layer`, `consistency_layer`, `aggregation_layer`, `presentation_layer`, `scoring_engine`) are reviewer-only vs. shared with `evaluation_v2/prerequisites.py`. Only the reviewer-only layers are candidates for deletion after this sub-project; the policy-compilation layers (`policy_compiler.py`, `policy_store.py`) are shared and stay.
- `app-front-end/src/components/scoring/AssessmentScorecard.tsx` and `app-front-end/src/lib/reviewScoring.ts` — the frontend consumer; this sub-project has a frontend half (point Assessment at canonical `criteria` scores instead of `structuredScoring`).
- ADR-0012 (`docs/adr/0012-investment-read-is-narrative-not-score.md`) — the founder-fluency/capability-slope/reframe boundary this sub-project must respect and extend to the rest of reviewer's output.

**Acceptance criteria:**
- Assessment's dimension scores come from `evaluation.criteria` (canonical), not `structured_scoring` (legacy).
- Reviewer's three personas (Primary/Skeptical/Opportunist) still diverge on *evidence* — contradicting claims — not on independent scores, matching ADR-0012's stated intent.
- `services/scoring/` shrinks to only what canonical `evaluation_v2` needs; reviewer-only presentation/extraction layers are deleted, not left dormant.
- No regression in founder-fluency/capability-slope/reframe rendering (existing tests in `backend/tests/reviewer/` covering ADR-0012 continue passing).

**Required tests:** frontend component test confirming Assessment reads canonical criteria; backend test confirming reviewer no longer writes a `structured_scoring` recommendation input (only narrative fields); regression test that reviewer disagreement now surfaces as `MemoEvidenceCoverage: 'contradictory'` (already the mechanism, per this session's finding) rather than a since-removed `agreement` field.

**Prohibited:** re-adding a "reviewer agreement" concept to the canonical model — this session already established it's redundant with evidence coverage.

---

### Sub-project 3: Portfolio store consolidation — CLOSED, no changes (2026-08-17)

**Original objective:** One portfolio persistence path (`portfolio/repository.py`, canonical, asyncpg) instead of two (`portfolio/store.py`, legacy, Supabase-client). Written 2026-08-16.

**What investigation on 2026-08-17 found — the premise was stale:**

1. **`portfolio/store.py` is already on Postgres, not Supabase.** It reads/writes through `batch2_state`/`batch3_state` (`backend/batch2/repository.py`, `backend/batch3/repository.py`), both asyncpg, both in the provider-neutral migration tree (`db/migrations/20260811000015`, `...000016`). Local JSON is dev-fallback only. The "legacy Supabase-client" framing this sub-project was named for no longer describes the code.

2. **`repository.py` and `store.py` don't represent the same data.** `repository.py` owns exactly one canonical table, `canonical_portfolio_positions` (keyed by `opportunity_id`+`company_id`). `store.py` owns five distinct legacy collections — decisions, positions, rejections, watchlist, signals — plus agent_metrics, keyed by legacy `startup_id`. Checked the migrations directly: **no canonical table exists for rejections, watchlist, signals, or agent_metrics.** `repository.py`'s own `list_decision_history` already UNIONs `store.py`'s `portfolio_decisions` table alongside canonical `human_rulings` as one of three read sources — partial, read-side consolidation is already deliberately underway, not something to build from scratch. "Delete `store.py`" was never achievable without first designing four undesigned canonical concepts — a product decision, not this sub-project's to make.

3. **Every write path in `store.py` is dead in the product's current operating mode.** `add_to_portfolio`/`add_rejection`/`add_to_watchlist`/`add_signal`/`add_agent_metric` are reached exclusively through `ExecutionAgent`/`SignalTracker`/`FeedbackLoop`/`HealthMonitor` (`portfolio/execution.py`, `signals.py`, `feedback.py`, `health.py`), reached exclusively through `PortfolioEngine.run_cycle()`, reached exclusively through the periodic autonomous pipeline (`_user_agent_loop` in `api.py`) — gated behind `agent_config.partners_enabled` and off for the entire duration of this session (`active_agent_loops=0` in every log line, "Pipeline: OFF" in every UI screenshot). The live, verified product flow (on-demand dispatch — Equal1/Fire1/Vanta, all verified this session) only *reads* `portfolio_store` (`partner/decision.py`'s sector-concentration check, Sub-project 1 Task 4) — never writes to it. The product's current operating model is human-ruling-centric ("AWAITING YOUR RULING" is the primary UI state), not the autonomous accept/reject/watchlist model `ExecutionAgent` was built for.

**Decision (2026-08-17): close, no changes.** The data-migration risk this sub-project was written to address (Supabase vs. Postgres) is already resolved elsewhere. What's left — whether the dormant autonomous-pipeline subsystem should be deprecated, and what canonical rejections/watchlist/signals/agent-metrics should even mean — is a product-scope decision bigger than a consolidation task, out of scope here. Revisit only if the autonomous pipeline is reactivated as a product direction.

---

### Sub-project 4: Canonical evidence extraction — DONE (2026-08-17)

**Objective:** Give the canonical evidence layer its own retrieval/extraction capability (the spec's Phase 3 "evidence-planning stage" and "retrieval stage," never built) so it stops depending entirely on scout's narrative prose via the regex-based `canonical_scout_claims.py` bridge. Only once this exists does simplifying `scout/`'s four personas become possible without breaking the product's only sourcing mechanism.

**Detailed task-level plan:** [2026-08-17-canonical-evidence-extraction.md](2026-08-17-canonical-evidence-extraction.md) — three phases (A: evidence planning/gap computation, B: bounded retrieval with deterministic trust/verification, C: LLM extraction + re-evaluation), all tasks DONE, live-verified end-to-end against a real dispatch (Vercel) — a canonical criterion score moved off `null` for the first time all session.

**Two eligibility-gate blockers found and fixed while live-verifying, not caught by unit tests alone:** retrieved evidence defaulted to `trust_class=unknown`/`verification_state=unverified` (fixed with a deterministic official-domain + corroboration rule) and separately defaulted `source_quality=0.0` (fixed alongside it) — both silently below the active policy's eligibility thresholds regardless of extraction quality.

### Follow-on: Scout persona-shrink — investigated, closed no changes (2026-08-17)

**Original premise:** now that canonical evidence extraction can source and score claims independently, `scout/`'s four LLM personas (`MarketDrivenScout`/`BuilderTechnicalScout`/`PainPointScout`/`ContrarianScout`, `scout/scouts.py`) could be shrunk to cut redundant LLM cost.

**What investigation found — the premise doesn't hold on the live path.** Every on-demand dispatch already runs exactly **one** persona, not four: `pipeline_runner.py:1692` hardcodes `scout_type="market_driven"`, and `ScoutEngine.run_named_lookup` (`scout/engine.py:546-548`) selects only that one. The 4-persona parallel fan-out (`_select_scouts_for_cycle`, `engine.py:140-176`) only runs inside `run_cycle` — the periodic autonomous pipeline, which Sub-project 3 already established has been off for the entire session. There is no 4x cost on the dispatch path to shrink.

The one persona that does run per dispatch has no canonical equivalent and stays necessary: it's the sole source of the memo's narrative prose (`one_line`/`problem`/`solution`/`target_users`/`why_now`, all rendered directly by `memo_generator.py`) — canonical extraction produces scored claims, not narrative text, a different job entirely. Founder/company identity resolution (`resolver/company_resolver.py`, `resolver/founder_resolver.py`) is a wholly separate deterministic pathway that runs *before* the LLM Scout call and doesn't depend on it at all.

The one genuinely-now-redundant piece found: `canonical_scout_claims.py`'s regex bridge promotes only 4 narrow claim types (`funding_stage`, `est_tam`, `traction_revenue`, `product_capability`) from Scout's narrative text by string-matching. Sub-project 4's grounded extraction now produces better versions of overlapping claim types (a real evidence-linked score vs. a regex guess). Retiring/shrinking that bridge is a small, well-scoped task if ever wanted — not a persona cut. **Decision (2026-08-17): close, no changes** — same call as Sub-project 3, for the same reason (the assumed cost/duplication problem doesn't exist where assumed). The 3 dormant personas only matter if the periodic pipeline is ever reactivated, an out-of-scope product decision.

---

## Verification gate (applies to every sub-project)

Mirrors AGENTS.md's definition of done — run before calling any sub-project complete:

```bash
python3 -m pytest -o asyncio_mode=auto
cd app-front-end && npm run lint && npm test && npm run build && npm run check:bundle
```

Plus, for any sub-project touching a scored recommendation: a manual review of the golden-set comparison output, since a silent recommendation change is a product-safety issue (invariant 5), not just a test failure.

## Explicitly out of scope for this plan

- Phases 6–8 of the source spec (attention-triggered enrichment, Fund Intelligence, channel/outcome expansion) — not started, not blocking this consolidation.
- Any change to `meta/` — already correctly shadow-mode/proposal-only per Phase 0, not part of the duplication problem this plan addresses.
- Rewriting `services/scoring/policy_compiler.py` or `policy_store.py` — shared, working, not implicated in the duplication.
