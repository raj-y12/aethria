# Canonical Evidence Extraction Implementation Plan (Sub-project 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the canonical evidence layer its own retrieval/extraction capability (spec §9.3-9.5) so it stops depending entirely on Scout's narrow regex-based claim extraction. Split into three independently shippable phases — this document covers **Phase A** in task-level detail; Phases B and C are scoped but not yet broken into tasks.

**Architecture:** Ponytail lens: reuse `EvidenceRepository.create_plan()` (already exists, unused by anything but a manual API endpoint) rather than building new persistence; reuse `evaluation_prerequisites.policy.criteria` (already computed, already threaded to this call site via Sub-project 1) rather than re-deriving the compiled policy; no LLM call in Phase A — it's a deterministic gap comparison, matching invariant 8 ("no model call where a rule works").

**Tech Stack:** Python 3.12, Pydantic, asyncpg. No new dependencies.

## Global Constraints

Same as the master plan — [2026-08-16-legacy-canonical-consolidation.md](2026-08-16-legacy-canonical-consolidation.md#global-constraints). Notably: this phase must be best-effort exactly like the canonical-evaluate() bridge it sits next to — a failure here must never fail an otherwise-healthy dispatch (invariant 5 reads the other way here: silence about a diagnostic gap is acceptable, breaking a working lookup over a diagnostic feature is not).

---

## What was found investigating §9.3-9.5 before writing this plan

Full findings live in the session's investigation (two parallel Explore agents, 2026-08-17). Summary:

- **§9.3 Evidence-planning**: `EvidencePlanRecord`/`evidence_plans` table/`EvidenceRepository.create_plan()` all exist and work (`backend/evidence/repository.py:257-307`). The only caller is `backend/routers/evidence.py::create_evidence_plan`, a manual endpoint that takes `missing_evidence`/`search_questions` straight from the request body. **Zero planning logic exists anywhere** — nothing computes what's actually missing.
- **§9.4 Retrieval**: out of scope for Phase A. A reusable provider chain exists (`retrieval_grounding.py`) but bridging it to canonical `ingest_artifact` with real dedup/attribution/cost-gating/failure-storage is Phase B.
- **§9.5 Extraction**: out of scope for Phase A. Zero LLM-based extraction exists; `canonical_scout_claims.py`'s regex matchers produce 11 claim types against a required set of 30+, with zero overlap. This is Phase C.
- **Key discovery informing Phase A's design**: `evaluate_snapshot()` (`evaluation_v2/service.py:402-416`) already computes a *coarse* missing signal — `missing_evidence=[rule.criterion]`, i.e. just the criterion name ("market") when nothing scored it. It does **not** say which of that criterion's specific required `claim_types` (e.g. `tam`, `growth_rate`, `urgency`, `timing`, `competition`) are absent. Phase A's real, non-redundant job is producing that fine-grained gap — the input a useful `search_questions` list needs — not re-deriving what evaluate() already tells us at the criterion level.
- **Wiring point found**: `pipeline_runner.py:1791-1817`, the exact same best-effort `try`/`except` block Sub-project 1 added for the early canonical-evaluate() bridge. `evaluation_prerequisites.policy.criteria` (the compiled policy, already loaded at this point) has everything needed per dimension: `CriterionRule.criterion` (dimension/criterion name) and `CriterionRule.claim_types` (the full accepted-claim-type list for that criterion, per `evaluation_v2/models.py:34-38`).

---

### Task 1: Add a current-claim-types query to EvidenceRepository — DONE

**Files:**
- Modify: `backend/evidence/repository.py` — new method, placed after `get_ledger` (line 356).
- Test: `backend/tests/evidence/test_evidence_repository.py` (check if this file exists first; create alongside existing evidence repository tests if not — mirror their fixture/pool pattern).

**Interfaces:**
- Produces: `async def list_current_claim_types(self, *, user_id: str, opportunity_id: str) -> set[str]` — the distinct `claim_type` values among that opportunity's `status='current'` claims.

**Implementation:**
```python
async def list_current_claim_types(self, *, user_id: str, opportunity_id: str) -> set[str]:
    uid = require_user_id(user_id, context="EvidenceRepository.list_current_claim_types")
    async with self.pool.acquire() as conn:
        rows = await conn.fetch(
            "select distinct claim_type from public.claims "
            "where user_id = $1 and opportunity_id = $2 and status = 'current'",
            uid, opportunity_id,
        )
    return {str(row["claim_type"]) for row in rows}
```

**Acceptance:** Returns an empty set for an opportunity with no claims (not an error); returns only `status='current'` claim types (withdrawn/superseded/contradicted excluded, matching how `evaluate_snapshot()`'s own snapshot query treats claim status).

---

### Task 2: Write the deterministic gap-computation function — DONE

**Files:**
- Create: `backend/evidence/planning.py`
- Test: `backend/tests/evidence/test_planning.py` (new — pure function, no DB, no mocks needed beyond constructing an `EvaluationPolicy`/`CriterionRule` fixture)

**Interfaces:**
- Consumes: `policy: EvaluationPolicy` (from `evaluation_v2.models`), `current_claim_types: set[str]` (from Task 1).
- Produces: `compute_missing_evidence(policy, current_claim_types) -> tuple[list[str], list[str]]` — returns `(missing_evidence, search_questions)`, both ready for `EvidenceRepository.create_plan(...)`'s existing parameters.

**Implementation:**
```python
"""Deterministic evidence-plan computation (spec §9.3). No model call —
compares the compiled policy's required claim types against what the
tenant currently has, matching evaluate_snapshot()'s own claim_type-in-list
check (evaluation_v2/service.py:364) so the same rule decides both what
"missing" means and what evaluate() will actually score."""

from __future__ import annotations

from evaluation_v2.models import EvaluationPolicy


def compute_missing_evidence(
    policy: EvaluationPolicy, current_claim_types: set[str],
) -> tuple[list[str], list[str]]:
    missing_evidence: list[str] = []
    search_questions: list[str] = []
    for rule in policy.criteria:
        if any(claim_type in current_claim_types for claim_type in rule.claim_types):
            continue
        missing_evidence.append(rule.criterion)
        wanted = ", ".join(rule.claim_types)
        search_questions.append(
            f"What evidence establishes {rule.criterion} for this company? "
            f"(any of: {wanted})"
        )
    return missing_evidence, search_questions
```

**Acceptance:**
- A criterion with at least one matching current claim type is not reported missing.
- A criterion with zero matching claim types is reported missing, with a search question listing its full accepted claim-type set.
- Empty `current_claim_types` produces one missing entry + one search question per criterion in the policy — no crash, no special-casing.

**Required tests:** `backend/tests/evidence/test_planning.py` — covers: all-covered policy returns empty lists; fully-uncovered policy returns one entry per criterion; a criterion satisfied by its *second* listed claim_type (not its first) still counts as covered — proves the check is "any," not "first," matching `evaluate_snapshot()`'s own `any(...)`-shaped membership test.

---

### Task 3: Wire the plan computation into the dispatch pipeline — DONE

**Files:**
- Modify: `backend/pipeline_runner.py:1791-1817` — inside the existing best-effort `try` block, immediately after `canonical_criteria = canonical_evaluation.get("criteria")` (line 1804).

**Implementation:**
```python
                    canonical_criteria = canonical_evaluation.get("criteria")
                    try:
                        current_claim_types = await EvidenceRepository(postgres_pool).list_current_claim_types(
                            user_id=user_id, opportunity_id=canonical_admission.opportunity_id,
                        )
                        missing_evidence, search_questions = compute_missing_evidence(
                            evaluation_prerequisites.policy, current_claim_types,
                        )
                        if missing_evidence:
                            await EvidenceRepository(postgres_pool).create_plan(
                                user_id=user_id,
                                opportunity_id=canonical_admission.opportunity_id,
                                trigger_type="dispatch",
                                missing_evidence=missing_evidence,
                                search_questions=search_questions,
                            )
                    except Exception:
                        logger.exception(
                            "[%s] Evidence-plan computation failed opportunity_id=%s",
                            user_id[:12],
                            canonical_admission.opportunity_id,
                        )
```

**Imports to add** (top of `pipeline_runner.py`, alongside the existing `EvaluationRepository`/`EvaluationLifecycleError` imports): `from evidence.repository import EvidenceRepository` (check whether already imported elsewhere in the file first — it's used by `_admit_named_lookup_before_review` per earlier session reads, so this may already be imported), `from evidence.planning import compute_missing_evidence`.

**Deliberately not doing in this task:** executing retrieval against the plan (Phase B), skipping plan creation when `missing_evidence` is empty is intentional — an empty/no-op plan is noise, not signal.

**Acceptance:** A dispatch where every criterion has a matching claim creates no plan (silent, correct — nothing to plan for). A dispatch matching tonight's live pattern (Fire1/Vanta — zero claims, all 5 criteria missing) creates one `evidence_plans` row with 5 entries in `missing_evidence` and 5 corresponding `search_questions`. A failure in this block (e.g. postgres hiccup) is logged and does not fail the dispatch — same contract as the canonical-evaluate() bridge beside it.

**Correction found during implementation:** no dedicated pytest exists for `_run_on_demand_lookup_inner` (the function this wiring lives in) — not for this addition, and not for Sub-project 1's identically-shaped canonical-evaluate() bridge beside it either. That precedent (full regression suite + live dispatch, not a new unit harness for this large integration-style function) is what this task followed instead.

---

### Task 4: Full verification gate — DONE

- [x] `python3 -m pytest -o asyncio_mode=auto backend/tests/evidence/test_planning.py -v` — 4/4 passed.
- [x] Full backend suite — 2224 passed (2220 before + 4 new), 43 failed (same pre-existing Postgres-container failures as before this change, zero new failures), 21 skipped.
- [x] `python3 -c "import api"` — clean.
- [x] **Live-verified** against a real dispatch (linear.app, no test/mock data): an `evidence_plans` row was created with `trigger_type="dispatch"`, `missing_evidence=["defensibility","execution","market","product","technical"]` (all 5 — Linear's opportunity had zero claims matching any required claim_type, consistent with the session's earlier 0/25-coverage finding), and 5 corresponding `search_questions`, each listing the specific claim types that would satisfy that criterion. Confirmed via direct DB query and a clean backend log (all 200s, no tracebacks) that the dispatch itself completed normally — Phase A is additive only, nothing else changed.

---

## Phase B: Retrieval stage — task-level plan

**Objective:** when Phase A's dispatch-triggered plan has non-empty `missing_evidence`, actually go retrieve something for it — inline, synchronous, bounded — before the dispatch finishes, and store what's found as canonical evidence artifacts.

### Architecture decision — inline/synchronous, not a background job (2026-08-17)

Two designs were considered:

1. **Async background job.** Reuse the existing but never-enqueued `JobType.EVIDENCE_REFRESH` job (`backend/jobs/handlers.py::evidence_refresh_handler`) and `MonitoringRepository.reserve_and_enqueue` (already builds a reservation + enqueues + notifies the worker in one call — real, working plumbing, just never triggered). Matches current real dispatch latency (already 1-3 minutes, well past the spec's 45s target) — adding more synchronous work would compound an already-blown budget.
2. **Inline, synchronous, bounded.** The spec's own §9.13 critical-path budget table (lines 649-658) buckets "Parallel retrieval and source probes" at 12s as one line item *within* the 45s median target for the first recommendation — the reference architecture's literal intent is retrieval as part of the interactive path, not deferred.

**Decision: inline.** Rationale (user's own words): there's no point deferring retrieval to an async follow-up if the user already saw and reacted to the first, incomplete evaluation — a silent later improvement nobody is told about isn't a real improvement. Matches the spec's literal target architecture, not just current practice.

**Important scope boundary to set correctly:** Phase B alone retrieves and stores *artifacts* (`evidence_artifacts`/`evidence_items`) — it does not produce *claims*. `evaluate_snapshot()` only ever reads claims. So Phase B, even fully shipped, will not visibly change any score or recommendation by itself — that only happens once Phase C (extraction: artifacts → typed claims) also ships. Phase B's payoff is that when Phase C ships, the evidence to extract from will already be there; shipping B before C is still worth doing (each is independently testable and reviewable), but say so plainly rather than implying B alone closes the loop.

### What was found investigating the four gaps

- **Dedup**: `EvidenceRepository.ingest_artifact` already dedups by `(user_id, content_hash, access_class)` at the DB level (`on conflict ... do nothing`, `evidence/repository.py:83`) — sufficient for Phase B's minimal bar. Full canonical-URL dedup (closing the "two inconsistent normalizers" gap between `retrieval_grounding.py`'s merge dedup and `retrieval_cache.py`'s cache dedup) is a real but separable refinement, not blocking — noted as a follow-up, not built here.
- **Attribution**: `EvidenceArtifactInput`/`evidence_artifacts` has no `retrieval_provider`/`retrieval_query` columns at all — real gap, needs a migration (Task 1).
- **Cost gating**: `CostController` (`portfolio/cost_control.py`) is LLM-token/call-shaped (`{"scout":..., "reviewer":..., "partner":...}` budgets) — Scout's own retrieval calls already bypass it entirely (`scout/base.py:935,1120` call `retrieve_source_pack_merged` directly, ungated). Retrofitting a dollar-based reservation system onto Phase B would be inventing a pattern nothing else in the codebase follows. Decision: bound by **count** (few queries, few artifacts — matching the spec's 12s budget), same as Scout already does. Real dollar-based gating stays a known, named gap — not a false-complete solution.
- **Failure storage**: `retrieval_cache.persist_failure` (`utils/retrieval_cache.py:110-116`) already exists and needs no new schema — reusable as-is for a canonical-triggered query that returns nothing.
- **Async-safety** (found during this investigation, not in the original four): `retrieval_cache.py`'s internal `_run_async` calls `asyncio.run()`, which raises if called from a thread that already has a running event loop. Calling `retrieve_source_pack`/`_merged` directly from `pipeline_runner.py` (already inside an async function, already inside a running loop) would crash. **Must wrap the call in `asyncio.to_thread(...)`.**
- **Reusable ingestion pattern**: `canonical_scout_claims.py::persist_scout_claims` (lines 120-145) already does exactly the "source dict → `EvidenceArtifactInput`/`EvidenceItemInput` → `ingest_artifact`" conversion Phase B needs — content hashing, trust/access class defaulting, prompt-injection detection. Mirror it rather than reinventing; it has the same attribution gap (no provider/query fields passed through either), confirming Task 1 is a real, shared gap, not something Phase B invents new.

---

### Task 1: Add retrieval attribution to canonical evidence storage — DONE

**Files:**
- Create: `db/migrations/20260817000001_evidence_artifact_retrieval_attribution.sql`
- Modify: `backend/evidence/models.py` — `EvidenceArtifactInput`/`EvidenceArtifactRecord`.

**Migration:**
```sql
alter table public.evidence_artifacts
  add column if not exists retrieval_provider text,
  add column if not exists retrieval_query text;
```

**Model change:**
```python
class EvidenceArtifactInput(_TenantModel):
    ...
    retrieval_provider: Optional[str] = Field(default=None, max_length=100)
    retrieval_query: Optional[str] = Field(default=None, max_length=500)
```

**Modify `EvidenceRepository.ingest_artifact`** (`evidence/repository.py:60-143`) — add `retrieval_provider`/`retrieval_query` to the insert column list and values tuple (both the `insert` and the two `select`/`fetchrow` fallback paths already return `*`, so no read-path change needed).

**Acceptance:** an artifact ingested via Scout's existing `persist_scout_claims` path (which won't pass these fields) still works — both new columns nullable, no behavior change for existing callers.

**Verification:**
- [x] Migration applied against the real dev Postgres via `python3 scripts/migrate_postgres.py` — `Applied migrations: 20260817000001`. Confirmed both columns exist.
- [x] Verified `ingest_artifact` directly against real Postgres both ways: without attribution (mirrors `persist_scout_claims`'s existing calls) → `retrieval_provider`/`retrieval_query` both `None`, no error; with attribution → both fields round-trip correctly. Test rows cleaned up after.
- [x] Full backend suite: 2224 passed (unchanged from before this task), 43 pre-existing failures (unchanged), zero regressions.
- [x] `python3 -c "import api"` — clean.
- [x] `tests/evidence/` — 14/14 passed, including the existing model-contract test (`test_artifact_and_item_contracts_are_tenant_scoped_and_bounded`), confirming the new optional fields didn't break any existing contract assertion.

---

### Task 2: Write the bounded retrieval-execution function — DONE (with a corrected design)

**Files:**
- Create: `backend/evidence/retrieval.py`
- Test: `backend/tests/evidence/test_retrieval.py`

**Interfaces:**
```python
async def execute_evidence_plan(
    *,
    user_id: str,
    company_id: str,
    opportunity_id: str,
    plan: EvidencePlanRecord,
    evidence_repository: Any,
    company_name: str,
) -> dict[str, int]:
    """Bounded, synchronous (from the caller's perspective) retrieval against a
    plan's search_questions. Ingests found sources as canonical evidence
    artifacts/items; does not produce claims (Phase C's job). Bounded by count,
    not dollar cost -- matches how Scout's own retrieval is already ungated."""
```

**Implementation sketch:**
```python
from utils.retrieval_grounding import retrieve_source_pack_merged
from utils.retrieval_cache import persist_failure
from evidence.models import (
    AccessClass, ArtifactType, EvidenceArtifactInput, EvidenceItemInput,
    TrustClass, VerificationState,
)
from evidence.service import detect_prompt_injection
import asyncio, hashlib

MAX_QUERIES = 3  # bounds this to the spec's ~12s retrieval budget

async def execute_evidence_plan(*, user_id, company_id, opportunity_id, plan, evidence_repository, company_name):
    queries = [f"{company_name} {q}" for q in plan.search_questions[:MAX_QUERIES]]
    if not queries:
        return {"artifacts_ingested": 0, "queries_run": 0}
    pack = await asyncio.to_thread(
        retrieve_source_pack_merged,
        queries=queries, user_id=user_id, max_per_query=4, max_total_sources=plan.max_artifacts,
    )
    sources = pack.get("sources") or []
    if not sources:
        await asyncio.to_thread(
            persist_failure, user_id=user_id, query=queries[0], category=None,
            time_range=None, days=None, provider=str(pack.get("provider") or ""),
            diagnostics=pack.get("provider_diagnostics") or [],
        )
        return {"artifacts_ingested": 0, "queries_run": len(queries)}
    ingested = 0
    for source in sources:
        content = str(source.get("snippet") or "").strip()
        if not content:
            continue
        await evidence_repository.ingest_artifact(
            EvidenceArtifactInput(
                user_id=user_id, company_id=company_id, opportunity_id=opportunity_id,
                artifact_type=ArtifactType.WEB_PAGE, source_uri=source.get("url"),
                title=source.get("title"), content_hash=hashlib.sha256(content.encode()).hexdigest(),
                trust_class=TrustClass.UNKNOWN, access_class=AccessClass.PUBLIC,
                untrusted_input=True, prompt_injection_detected=detect_prompt_injection(content),
                retrieval_provider=str(pack.get("provider") or ""), retrieval_query=queries[0],
            ),
            items=[EvidenceItemInput(
                user_id=user_id, item_type="retrieval_excerpt", normalized_value={},
                display_excerpt=content[:2000], source_locator=source.get("url"),
                verification_state=VerificationState.UNVERIFIED,
            )],
        )
        ingested += 1
    return {"artifacts_ingested": ingested, "queries_run": len(queries)}
```

**Prohibited:** do not attempt claim extraction here — display_excerpt/normalized_value stay raw; turning this into typed claims is Phase C, not this task.

**Corrections found during implementation (the sketch above is what was planned, not what shipped):**

1. **The manual `persist_failure` call was wrong and got removed.** `retrieve_source_pack`/`retrieve_source_pack_merged` (`retrieval_grounding.py:375-393`) already call `cache.persist_success`/`cache.persist_failure` *internally*, non-fatally, on every call — Task 2's sketch would have duplicated that. `evidence/retrieval.py` as shipped has no manual failure-persistence call at all; it just returns `{"artifacts_ingested": 0, "queries_run": N}` when `sources` is empty and lets the already-existing internal mechanism handle bookkeeping.
2. **New gap found, out of scope for this task**: `api.py` (the actual running server process) never calls `configure_retrieval_cache(...)` — only `run_system.py` (the standalone worker script) does. So in the live app today, the process-wide `_RETRIEVAL_CACHE` singleton stays `None`, and `persist_success`/`persist_failure` silently no-op (they're gated behind `if cache:`). Retrieval itself still works correctly either way — this only means cache-layer success/failure bookkeeping isn't actually happening in the live process right now. Not fixed here (it's a pre-existing gap in `api.py`'s startup sequence, not something this task touched or broke) — flagged as a real follow-up.
3. `persist_failure` also turned out to be a **method on a `RetrievalCache` instance**, not a standalone function as the sketch imported it — moot given point 1, but worth recording so a future reader doesn't hit the same wrong import.

**Files as actually shipped:**
- `backend/evidence/retrieval.py` — `execute_evidence_plan()`, matching the interface above; internals differ from the sketch per the corrections.
- `backend/tests/evidence/test_retrieval.py` (new, 4 tests) — sources found → ingested with attribution and the empty-snippet source skipped; zero sources → zero artifacts, no error (not "persist_failure called," corrected per above); queries capped at `MAX_QUERIES` regardless of a longer plan; an empty plan (`missing_evidence`/`search_questions` both `[]`) skips the retrieval call entirely — `retrieve_source_pack_merged` never invoked.

**Verification:**
- [x] `tests/evidence/test_retrieval.py` — 4/4 passed.
- [x] Full backend suite: 2228 passed (2224 + 4 new), 43 pre-existing failures (unchanged), zero regressions.

---

### Task 3: Wire it inline into the dispatch pipeline — DONE

**Files:**
- Modify: `backend/pipeline_runner.py` — inside the same best-effort block Phase A added (right after `create_plan(...)` succeeds).

**Implementation:**
```python
                        if missing_evidence:
                            plan = await EvidenceRepository(postgres_pool).create_plan(
                                user_id=user_id,
                                opportunity_id=canonical_admission.opportunity_id,
                                trigger_type="dispatch",
                                missing_evidence=missing_evidence,
                                search_questions=search_questions,
                            )
                            await execute_evidence_plan(
                                user_id=user_id,
                                company_id=canonical_admission.company_id,
                                opportunity_id=canonical_admission.opportunity_id,
                                plan=plan,
                                evidence_repository=EvidenceRepository(postgres_pool),
                                company_name=company,
                            )
```
(`create_plan`'s return value wasn't captured before — Phase A discarded it. Task 3 captures it since Task 2's function needs the plan's `max_artifacts`/`search_questions`.)

**Import to add:** `from evidence.retrieval import execute_evidence_plan`.

**Deliberately not doing:** re-running `EvaluationRepository.evaluate()` after retrieval. Phase B alone produces artifacts, not claims — re-evaluating now would produce an identical `insufficient_evidence` result (nothing new to score against) and just add latency for no visible change. Re-evaluation after evidence work belongs with Phase C, once there's something new for it to find.

**Acceptance:** a dispatch with missing evidence now takes measurably longer (bounded to ~3 queries) and produces new `evidence_artifacts`/`evidence_items` rows for the opportunity. A dispatch with no missing evidence is unaffected (no retrieval call at all — `execute_evidence_plan` only runs inside `if missing_evidence:`). A retrieval failure (provider down, zero results) does not fail the dispatch — same best-effort contract as everything else in this block.

Shipped exactly as sketched — `plan = await create_plan(...)` now captures the return value (previously discarded), and `execute_evidence_plan(...)` is called immediately after with it.

**Verification:**
- [x] Full backend suite: 2228 passed (unchanged from Task 2 — no new tests for this wiring, matching Phase A's Task 3 precedent: no dedicated pytest exists for `_run_on_demand_lookup_inner`, verified via full suite + live dispatch instead), 43 pre-existing failures, zero regressions.
- [x] `python3 -c "import api"` — clean.
- [x] **Live-verified** against a real dispatch (notion.so, no test/mock data). Confirmed the full sequence: `evidence_plans` row created at 10:39:36 with all 5 criteria missing → `execute_evidence_plan` ran and ingested **5 new `evidence_artifacts`** at 10:39:44 (8s later — real Exa retrieval, not instant/mocked), each with `retrieval_provider='exa'` and a real `retrieval_query` populated. The 11 other artifacts on the same opportunity (Scout's own pre-existing ingestion, same timestamp as the plan) correctly have `retrieval_provider=None` — confirms Task 1's "existing callers unaffected" held in production, not just in tests. Clean backend log, no tracebacks, dispatch completed successfully (slower than before, as expected).
- [x] **Honest limitation found in the live data, not a bug**: all 5 ingested artifacts show the *same* `retrieval_query` (the first of the 3 capped queries), even though `retrieve_source_pack_merged` runs all 3 queries and merges their results into one flat `sources` list before this code sees them — there's no per-source query mapping in the merged pack to attribute more precisely. The data is genuinely retrieved, real evidence; only the query-attribution field's precision is coarser than ideal (says "found by the market query" for a source that may have actually surfaced via the product or technical query). Not fixed here — recording it honestly rather than overclaiming what the attribution field means today.

---

## Phase C — not yet task-level planned

An LLM-based extractor producing claims in the ~30 claim types the compiled policy actually requires (currently 100% gap — `canonical_scout_claims.py`'s 11 regex-derived claim types share zero overlap with what any criterion accepts). Reuse `Reviewer._call_llm_sync`'s schema-enforcement/retry pattern (`reviewer/base.py:675+`) rather than building extraction scaffolding from scratch. Once Phase C ships, Task 3's "deliberately not doing" re-evaluation note above should be revisited — that's the point at which re-running `evaluate()` after evidence work actually has something new to find.

Blocks on Phase B shipping first — task-level plan to be written once Phase B is verified live.
