# Reviewer Scoring Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `reviewer/`'s three personas stop independently producing `structured_scoring` as the thing Assessment renders. Canonical `evaluate_snapshot()` becomes the score authority the frontend reads. Reviewer's remaining job is narrative only: `founder_fluency`, `capability_slope`, `reframe` (ADR-0012).

**Architecture:** Ponytail lens: reuse the canonical criteria endpoint that already exists rather than building a new one from scratch; don't delete a `services/scoring/` file that's still load-bearing for something other than Assessment.

**Tech Stack:** Python 3.12, Pydantic, TypeScript/React (app-front-end). No new dependencies.

## Global Constraints

Same as the master plan — [2026-08-16-legacy-canonical-consolidation.md](2026-08-16-legacy-canonical-consolidation.md#global-constraints). Notably: invariant 5 (fail closed) is directly load-bearing for this sub-project — see "What was found" below, this is not a mechanical data-source swap.

---

## What was found reading `reviewer/engine.py` (1,657 lines), `reviewer/base.py` (1,290 lines), `services/scoring/*` (9 files, ~4,346 lines), and the frontend consumer, in full

**The master plan's scope was too small.** It assumed Partner was already effectively canonical-only for scoring after Sub-project 1, and that Assessment just needed to be repointed at a different data source. Neither is true.

### 1. Partner still has three live, independent dependencies on Reviewer's raw scores

Confirmed in `partner/decision.py`, all running **before or independent of** the canonical-recommendation override Sub-project 1 added:

| Dependency | Where | What breaks if removed carelessly |
|---|---|---|
| `avg_score`/`grey_zone_score` computed from `structured_scoring`/raw `*_score` fields | `_avg_score_and_dims` (decision.py:370-402), called decision.py:887 | Drives `grey_zone_active` (decision.py:891-899) — the LLM deep-dive escalation trigger. Not gated by canonical_recommendation. |
| Evidence-coverage fail-closed gate — reads `structured_scoring[dim]["unscored"]` directly | decision.py:946-964 | Forces MONITOR/PASS + `human_review_required=True` when dimensions are unscored. **This is invariant 5 (fail closed) in the code.** Runs regardless of canonical recommendation. |
| `reviewer_disagreement` (from `review_output.get("reviewer_disagreement")`) | decision.py:1087, used decision.py:1353 | Triggers LLM escalation on persona disagreement. |

`partner/engine.py:190-217` forwards all of `structured_scoring`, `reviewer_disagreement`, `score_variance`, and the raw `*_score` fields into the payload `decide()` receives — this is a real, intentional data flow, not dead wiring.

### 2. The master plan's "evidence contradiction already covers disagreement" hypothesis is false in code today

`reviewer_disagreement`/`score_variance`/`derived_verdict`/`consensus_verdict` are all computed in `_compute_consensus` (engine.py:351-379) and `_derive_verdict_from_scores` (engine.py:828-870) purely from the three personas' raw numeric scores. The contradiction gate (`_guard_review_output` → `apply_contradiction_gate`, engine.py:755-766) is a **separate mechanism** applied to narrative text — it does not feed any of these four fields. If this sub-project removes per-persona scoring, these four fields have no replacement unless one is built.

### 3. `services/scoring/` ownership (confirmed by import graph, not assumption)

| File | Classification |
|---|---|
| `extraction_layer.py`, `normalization_layer.py`, `consistency_layer.py`, `aggregation_layer.py`, `confidence_discount.py`, `presentation_layer.py`, `scoring_engine.py`, `__init__.py` | **Reviewer-only** — delete-candidates once nothing in reviewer/ needs them |
| `policy_compiler.py`, `policy_store.py` | **Shared** — `evaluation_v2/prerequisites.py` imports both directly. Must stay. |
| `policy_upgrade.py`, `legacy_policy_compat.py` | **Orthogonal** — standalone CLI/migration utility (`scripts/upgrade_published_policy.py`), not imported by reviewer/ or evaluation_v2/. Out of scope for this sub-project either way. |

Complication: `policy_compiler.py` (shared, must stay) imports `EXPECTED_COMPONENTS` from `extraction_layer.py` (reviewer-only, delete-candidate). That one constant needs to move somewhere shared before `extraction_layer.py` can be deleted.

`presentation_layer.py` is called directly from `api.py` (`serialize_scoring_presentation`), not only via `reviewer/engine.py` — confirm that call site is itself reviewer-flow-only before deleting.

### 4. Frontend: canonical criteria are reachable today, but the shape doesn't match what Assessment needs

`GET /api/opportunities/{id}/evaluation` (`routers/evaluations.py:28-36`) already returns canonical `criteria: CriterionAssessment[]`, and the frontend already fetches it (`api/evaluations.ts::fetchCurrentEvaluation`) — but only for the masthead/decision-brief (`useMemoDecisionBrief.ts:47-53`), not for `AssessmentScorecard`.

`CriterionAssessment` (`api/evaluations.ts:20-31`) is materially thinner than `StructuredScoring`/`ScoringDimension` (`types/startup.ts:242-345`) which `AssessmentScorecard.tsx` renders: no `overall_score`, no per-dimension `components`, no band/label, no dispersion, and `criterion` is a free string, not the fixed 5-key `market/execution/product/technical/defensibility` set `AssessmentScorecard` expects. Closing this gap is either a backend payload extension or a new endpoint, plus a new frontend adapter (parallel to `reviewScoring.ts`).

`founder_fluency`/`capability_slope`/`reframe` are confirmed already isolated from the scoring path (base.py:358-385, 1167-1176) — untouched by this sub-project.

---

## Open product decision — needs your call before Task 3 can be written

The master plan's acceptance criteria ("Assessment reads canonical criteria, reviewer only produces narrative") is achievable for the **frontend display swap** (Tasks 1-2 below) without touching Partner. But Partner's three dependencies in §1 are a live fail-closed safety mechanism and an escalation trigger, not legacy cruft — removing per-persona `structured_scoring` production would silently break them unless each gets an explicit canonical replacement:

- **Evidence-coverage fail-closed gate**: canonical criteria already carry `evidence_sufficiency`/`missing_evidence`/`quality_flags` per criterion (`CriterionAssessment`) — this looks like a reasonable replacement signal, but "what counts as unscored/insufficient" is a threshold decision, same category as invariant 3 (versioned config, not a Python literal).
- **Grey-zone LLM escalation trigger**: currently `avg_score` near a threshold. A canonical replacement (e.g. `evaluation.confidence` or a criteria-quality aggregate) needs to be picked deliberately — this changes when Aethria spends money on an LLM call (invariant 8).
- **`reviewer_disagreement` escalation**: currently persona score variance. No canonical equivalent exists yet; this sub-project would need to either build one or accept losing this trigger, which is a product call, not an implementation detail.

**I'm not resolving these by default.** Recommend: land Tasks 1-2 (frontend swap, additive, zero risk to Partner) now, then bring the three replacement-signal decisions above back to you as a scoped follow-up (Tasks 3+) once you've said what each should be.

---

### Task 1 + 2: Point Assessment at canonical criteria — DONE (merged into one task)

**What changed vs. the plan:** Task 1 (extend the payload) turned out to be unnecessary. Reading `AssessmentScorecard.tsx`'s actual render path (renderRow, lines 111-135) found it already has a fallback for exactly canonical's shape: when `components` is empty, it renders `reasoning` bullets instead (`allDrivers.length === 0 ? cleanReasoningList(dimension.reasoning) : []`). And the DB confirms `criterion_assessments.criterion` values already ARE the fixed 5-key set (`market/product/technical/execution/defensibility`), verified live against Fire1's row. `overall_score`/`overall_confidence` are computed client-side as the mean of the 4 driver dimensions (matching `AssessmentScorecard`'s own documented convention — Defensibility excluded, it's a moat signal). No backend change needed.

**Files:**
- Created: `app-front-end/src/lib/canonicalScoring.ts` — `canonicalCriteriaToStructuredScoring()`, the adapter from `EvaluationRecord`/`CriterionAssessment[]` to `StructuredScoring`. `components: {}` always (canonical has no per-component breakdown), `unscored` when `score == null`, `overall_dispersion: null` (no persona spread in a single evaluator).
- Modified: `app-front-end/src/hooks/useMemoDecisionBrief.ts` — exposed the already-fetched `evaluation: EvaluationRecord | undefined` in the hook's return (React Query dedupes the identical query key, zero extra fetches).
- Modified: `app-front-end/src/components/InvestmentMemoContent.tsx` — `structuredScoring` now prefers `canonicalCriteriaToStructuredScoring(canonicalEvaluation)`, falls back to the legacy `normalizeStructuredScoring(displayStartup?.review)` when no canonical evaluation exists yet. `scoringPresentation` (a legacy narrative layer keyed to reviewer's own dimension values) is nulled out whenever canonical scoring is active — it would otherwise show numbers that don't match.
- Test: `app-front-end/src/lib/__tests__/canonicalScoring.test.ts` (new, 4 tests) — null-when-empty, 5-key mapping, unscored-when-null-falls-back-to-reasoning, unscored drivers excluded from the overall mean (not averaged in as 0).

**Prohibited (respected):** did not touch `reviewScoring.ts`'s legacy path — `productChromeMappers.ts:58`, `adverseRegister.ts:139`, `fundConfiguration.ts:638-642` still read `structured_scoring` directly and are unaffected.

**Verification:**
- [x] `npx tsc --noEmit` — clean, whole repo.
- [x] `npm run lint` — clean.
- [x] `npm test` — 464/464 passed (frontend suite).
- [x] `npm run build` + `npm run check:bundle` — clean, budget passed.
- [x] **Live-verified in the browser** against Fire1 (real dispatch, no test/mock data): Assessment now shows "Not scored — No supporting evidence — excluded from the overall" for all 5 dimensions, matching Fire1's actual canonical `criterion_assessments` rows (`score: null, evidence_sufficiency: 'insufficient'` for all 5 — canonical evaluation ran early and found nothing yet). Confirmed via network tab that `GET /api/opportunities/{id}/evaluation` is the live data source. No console errors. The Reviewer Split panel below (Default 4.9, Skeptical 2.0 — legacy per-persona narrative) correctly stayed untouched, confirming only the scorecard swapped.

**Investigated 2026-08-17 — root cause confirmed, not a sequencing bug.** No opportunity in the database has a non-null canonical criterion score. Initial hypothesis ("canonical evaluate() runs too early, before Reviewer") was checked and is **wrong** — re-sequencing would not fix this. Confirmed by reading every call site:

1. `persist_scout_claims` (`pipeline_runner.py:651-653`) is called **exactly once** in the entire pipeline, right after Scout. Nothing writes canonical claims after that point, at any pipeline stage.
2. Reviewer's own gap-retrieval evidence (`enrich_scout_for_reviewer_llm`, `utils/reviewer_gap_retrieval.py:216`) is explicitly excluded from ever becoming a canonical claim — its own docstring: *"Do not persist; deterministic scoring should use the original scout dict."* It only ever feeds the Reviewer LLM's own prompt. So even a full, successful Reviewer run never backfills canonical claims — moving `evaluate()`'s call site later in the pipeline would see the exact same claims it sees today.
3. `derive_scout_claims` (`canonical_scout_claims.py:68`) itself only extracts a narrow set of claim types (`funding_stage`, `market_size`, `traction_revenue`, `product_capability`, competition, commercial) — each gated on both the Scout field being populated *and* a keyword-matcher finding literal supporting text in a retrieved source. No claim type exists for team/execution/technical signals directly.

**Decision (2026-08-17):** leave as designed. Matches the vault's own Architecture note — "canonical coverage is partial by design... missing coverage falls back safely." Assessment showing "Not scored" more often under canonical than legacy Reviewer scoring is the system being honestly uncertain, not broken. Revisit only if this causes real product pain in practice.

---

### Tasks 3+ — blocked

Not written yet. Depends on your answers to the three replacement-signal questions above. Once you decide what the evidence-coverage gate, grey-zone trigger, and disagreement trigger read from canonically, I'll write the task-level plan for: replacing those three Partner dependencies, then removing per-persona `structured_scoring` production from `reviewer/engine.py`/`base.py`, then deleting the reviewer-only `services/scoring/` files (after carving `EXPECTED_COMPONENTS` out of `extraction_layer.py` into a shared location `policy_compiler.py` can still import from).
