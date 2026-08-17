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

## Phase B and C — not yet task-level planned

**Phase B (Retrieval stage):** bridge `retrieval_grounding.py`'s provider chain to `EvidenceRepository.ingest_artifact`, driven by the `evidence_plans` rows Phase A now produces. Needs to close four gaps found in investigation: unified canonical-URL + content-hash dedup (currently split across two inconsistent implementations, and canonical storage has no URL-based dedup at all); provider/query attribution reaching canonical storage (currently discarded before `ingest_artifact`); real cost gating (a reserve/settle ledger already exists in `monitoring/repository.py` but is wired to a hardcoded `$0`); independent failure storage on the canonical side (currently exists only in the ad-hoc retrieval cache).

**Phase C (Extraction stage):** an LLM-based extractor producing claims in the ~30 claim types the compiled policy actually requires (currently 100% gap — `canonical_scout_claims.py`'s 11 regex-derived claim types share zero overlap with what any criterion accepts). Reuse `Reviewer._call_llm_sync`'s schema-enforcement/retry pattern (`reviewer/base.py:675+`) rather than building extraction scaffolding from scratch.

Both phases block on Phase A shipping first, and their own task-level plans should be written once Phase A is verified live.
