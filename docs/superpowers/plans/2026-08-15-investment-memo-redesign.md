# Investment Memo Decision-Brief Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the memo's contradictory, probability-styled verdict page with an honest decision brief that separates machine lean, evidence sufficiency, mandate fit, reviewer agreement, and the authoritative human ruling.

**Architecture:** Keep the existing immutable evaluation, evidence-ledger, and human-ruling APIs. Make canonical evaluation fail closed to its existing `insufficient_evidence` state before score-derived or critical-risk recommendations; project that state in the UI as `Blocked by evidence`, never as workflow `BLOCKED`. Build a pure frontend decision-brief view model that joins criterion claim IDs to evidence sources, conservatively labels provenance, removes internal diagnostics, and groups repeated risks. Let `OpportunityIntelligence` retain query ownership and render one primary decision/ruling surface directly below the masthead; move the legacy dossier into one secondary native disclosure.

**Tech Stack:** Python 3.12, Pydantic, pytest, React 19, TypeScript, TanStack Query, Vitest/Testing Library, existing CSS container queries.

**Spec:** `docs/archive/DESIGN-IS-2026-08-15-corgi-memo/04-handoff-prompt.md`

## Approved information architecture

```text
CURRENT                              TARGET
Masthead                             Masthead + actions
Categorical Partner verdict          Decision brief
The Read                              - status: Blocked / Ready / Recorded
Snapshot                              - machine lean, not final decision
Founder                               - mandate / evidence / agreement
Why Now                               - max 3 independent drivers
What Limits Conviction                - one deduplicated risk + gap surface
Assessment                            - inline claim provenance and sources
Path to a 9                           - human ruling controls and rationale
Competition / business model         Supporting analysis (one disclosure)
Thesis alignment                      - company / founder / timing
Risks (duplicate)                      - assessment / thesis / history
Appendix                              Evidence and decision history
Buried human ruling
```

## Phase 0: Documentation discovery and allowed APIs

Discovery is complete and source-verified. Implementers must copy the established patterns below rather than invent new contracts.

- Canonical non-decisive state: `backend/evaluation_v2/models.py` (`RecommendationState.INSUFFICIENT_EVIDENCE`).
- Policy-driven thresholds and safety rules: `backend/evaluation_v2/policy.py`, `backend/evaluation_v2/partner_rules.py`, `resources/config/partner_rules/v4.json`.
- Deterministic evaluator and immutable criterion claim references: `backend/evaluation_v2/service.py`, `backend/evaluation_v2/repository.py`.
- Claim/evidence/artifact provenance: `backend/evidence/models.py`, `backend/routers/evidence.py`, `app-front-end/src/api/evidence.ts`.
- Existing criterion-to-claim join: `app-front-end/src/components/institutional/ClaimEvidenceLedger.tsx`.
- Existing query and ruling ownership: `app-front-end/src/components/institutional/OpportunityIntelligence.tsx`, `HumanRulingComposer.tsx`.
- Existing modal focus trap, Escape, reduced-motion, print and error foundations: `app-front-end/src/components/InvestmentMemo.tsx`, `InvestmentMemoContent.tsx`, `InvestmentMemoContent.css`.

Anti-pattern guards:

- Do not add `BLOCKED` to persisted Partner, human-ruling, or authority workflow enums. `Blocked by evidence` is presentation of canonical `insufficient_evidence`.
- Do not change a threshold in Python or mutate a published policy file.
- Do not present recommendation, criterion, reviewer, or ruling confidence as a percentage.
- Do not call a reviewer/persona label or non-empty source string `evidence-backed`.
- Do not infer claim-to-source relationships from prose; use stored claim/evidence IDs only.
- Do not add endpoints, migrations, dependencies, fetches outside `src/api/`, or a second ruling path.
- Do not wholesale replace dirty overlapping files; preserve unrelated working-tree changes.

## Global Constraints

- Preserve the paper/Oxford/burgundy palette and Playfair Display/Instrument Sans/Space Mono role system.
- Preserve canonical action semantics: `advance` means continue diligence, not invest; final human ruling remains authoritative.
- Preserve immutable evaluation and ruling history; historical records are not rewritten.
- Missing, contradictory, malformed, or ungrounded decision-bearing evidence is non-decisive and requires human review.
- A complete, verified hard exclusion or critical risk may still produce `pass`.
- Every material displayed claim must expose one of: verified, reported, rule-derived, model-derived, or missing. `Verified` requires a verified evidence item and a source artifact.
- Primary drivers are capped at three; company risks appear once and exclude internal scoring/reviewer diagnostics.
- Closed supporting content must be absent from focus order; controls are at least 44px; on-screen prose is ragged-right; metadata meets WCAG AA contrast.
- Preserve all unrelated dirty-tree work. Do not commit, branch, push, or publish.

---

### Task 1: Make canonical evaluation fail closed before decisive output

**Files:**
- Modify: `backend/evaluation_v2/service.py`
- Modify: `backend/tests/evaluation_v2/test_evaluator.py`
- Modify: `backend/tests/evaluation_v2/test_decision_safety_certification.py`
- Modify: `backend/tests/evaluation_v2/test_partner_rules_contract.py`
- Create: `docs/adr/0013-evidence-sufficiency-precedes-machine-recommendation.md`
- Modify: `docs/adr/README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `API.md`

- [x] **Step 1: Add failing evaluator tests.** Cover required criterion missing plus a grounded critical risk, a scored criterion with contradicting evidence, and an ungrounded/malformed decisive risk. Expect canonical `insufficient_evidence`, named gaps/change conditions, and `human_review_required=True`. Preserve tests proving a complete grounded hard exclusion or critical risk yields `pass`.

- [x] **Step 2: Run focused tests and record the red failures.**

```bash
python3 -m pytest -o asyncio_mode=auto \
  backend/tests/evaluation_v2/test_evaluator.py \
  backend/tests/evaluation_v2/test_decision_safety_certification.py \
  backend/tests/evaluation_v2/test_partner_rules_contract.py
```

- [x] **Step 3: Implement the smallest evaluator ordering change.** Determine completeness/contradiction/decisive-grounding from existing criterion results and configured policy. Select `INSUFFICIENT_EVIDENCE` before decisive and score-derived states when decision-bearing evidence is incomplete or contradictory. Do not introduce a threshold or new enum.

- [x] **Step 4: Document the invariant.** Record that recommendation is not ruling, evidence-blocked presentation maps to canonical `insufficient_evidence`, authority workflow `BLOCKED` remains reserved for execution blocks, and grounded exclusions remain decisive. Update current architecture/API descriptions without changing existing response fields.

- [x] **Step 5: Re-run focused tests and record green output.** Also run `python3 -m pytest -o asyncio_mode=auto backend/tests/evaluation_v2 -q`.

Verification checklist:

- Missing/contradictory decision evidence cannot return `advance` or `pass`.
- Grounded complete critical risks and hard exclusions still return `pass`.
- No threshold or policy JSON changed; partner-rules contract coverage is extended.
- No legacy or human-ruling enum changed.

---

### Task 2: Build the typed memo decision-brief model

**Files:**
- Create: `app-front-end/src/lib/memoDecisionBrief.ts`
- Create: `app-front-end/src/lib/__tests__/memoDecisionBrief.test.ts`
- Modify: `app-front-end/src/api/evaluations.ts`
- Modify: `app-front-end/src/api/evidence.ts`

- [x] **Step 1: Write the pure-helper tests first and confirm the missing module fails.** Cover canonical insufficient evidence; legacy/pass-like lean plus missing or contradictory evidence; separation of status, lean, mandate, coverage, agreement and ruling; absence of confidence percentages; max-three drivers; criterion claim/source joins; conservative provenance; semantic grouping of Corgi regulatory variants; and exclusion of `Gap >=4`/reviewer-spread diagnostics.

- [x] **Step 2: Add the backend's existing criterion fields to the frontend API type and normalizer.** Add `supporting_claim_ids`, `contradicting_claim_ids`, and `quality_flags` as additive arrays. Narrow existing assertion/verification strings only where it improves exhaustive mapping; do not change endpoints.

- [x] **Step 3: Implement a pure view model.** Produce typed status (`loading | ready_for_ruling | blocked | recorded | unavailable`), lean (`advance | monitor | pass | none`), mandate, evidence coverage, reviewer agreement, up to three independent drivers, one grouped risk/gap list, and claim-source provenance. Use stored IDs for joins and stable deterministic grouping; preserve the richest risk, maximum severity, and unioned sources.

- [x] **Step 4: Run the helper and API tests to green.**

```bash
cd app-front-end && npm test -- \
  src/lib/__tests__/memoDecisionBrief.test.ts \
  src/api/__tests__/evaluations.test.ts \
  src/api/__tests__/evidence.test.ts
```

Verification checklist:

- No view-model field is named confidence or formatted as a percentage.
- `verified` is impossible without a verified evidence item and source artifact.
- Rule/model outputs remain labeled as derivations.
- Internal process diagnostics never enter company risks.
- Inputs are immutable and output ordering is deterministic.

---

### Task 3: Replace the primary memo hierarchy with one decision/ruling surface

**Files:**
- Create: `app-front-end/src/components/memo/MemoDecisionBrief.tsx`
- Create: `app-front-end/src/components/memo/__tests__/MemoDecisionBrief.test.tsx`
- Modify: `app-front-end/src/components/institutional/OpportunityIntelligence.tsx`
- Modify: `app-front-end/src/components/institutional/RecommendationPanel.tsx`
- Modify: `app-front-end/src/components/institutional/__tests__/OpportunityIntelligence.test.tsx`
- Modify: `app-front-end/src/components/InvestmentMemoContent.tsx`
- Modify: `app-front-end/src/components/InvestmentMemoContent.css`
- Modify: `app-front-end/src/components/memo/__tests__/InvestmentMemoSections.test.ts`

- [x] **Step 1: Add failing presentation tests.** Assert one primary `Decision brief` region distinguishes status from machine lean, removes confidence percentages, renders provenance/source links, groups repeated risks once, excludes internal diagnostics, includes the human ruling action in the same work surface, and keeps read-only evidence visible while hiding the composer.

- [x] **Step 2: Implement the presentational brief and integrate it with existing query ownership.** `OpportunityIntelligence` assembles the pure view model from evaluation/evidence/rulings and renders the brief, evidence disclosure/history, and the existing `HumanRulingComposer`. Loading/unavailable/error states must name the missing link and never fall back to a categorical legacy verdict.

- [x] **Step 3: Reorder the memo.** Render the canonical decision workspace immediately after the masthead. Remove the visible legacy dossier opening, duplicate `What Limits Conviction`/Risks surfaces, probability-like thesis/partner confidence copy, and sticky ruling jump. Wrap company, founder, timing, assessment, thesis and appendix material in one native secondary `details` disclosure so closed content is absent from keyboard focus.

- [x] **Step 4: Implement the responsive/accessibility CSS.** Use one column at and below 760px; prevent score/provenance/source collisions; set 44px minimum controls; raise microcopy size/contrast; make screen prose ragged-right with no auto-hyphenation; keep reduced-motion and print behavior; hide ruling controls in print while retaining status, lean and provenance.

- [x] **Step 5: Run component tests and build checks.**

```bash
cd app-front-end && npm test -- \
  src/components/memo/__tests__/MemoDecisionBrief.test.tsx \
  src/components/institutional/__tests__/OpportunityIntelligence.test.tsx \
  src/components/institutional/__tests__/HumanRulingComposer.test.tsx \
  src/components/memo/__tests__/InvestmentMemoSections.test.ts
cd app-front-end && npm run lint && npm run build && npm run check:bundle
```

Verification checklist:

- The first substantive region after the masthead is `Decision brief`.
- One visible recommendation vocabulary and one company-risk surface exist.
- Human action, rationale, status and evidence are in one working region.
- No `partner confidence`, thesis confidence percentage, generic `evidence-backed`, `Path to a 9`, sticky ruling jump, or duplicated conviction list remains in the primary narrative.
- Disclosure buttons preserve `aria-expanded`/native semantics; closed content is not tabbable.

---

### Task 4: Responsive, state, regression and repository verification

**Files:**
- Modify only if verification exposes a task-scoped defect in files above.

- [x] **Step 1: Exercise the required states.** Loading, unavailable/error, blocked, ready-for-ruling, recorded, read-only, expanded/collapsed, focus-visible, disabled, reduced-motion and print.

- [x] **Step 2: Check desktop and 520, 666, 680, 729 and 760px containers.** Verify no horizontal overflow or intersecting rectangles; actions and rationale remain usable; source links and risk provenance wrap; supporting content cannot receive focus while closed.

- [x] **Step 3: Run anti-pattern checks.** Confirm the primary rendering has no confidence percentage, generic evidence-backed label, legacy ruling path, duplicate risk renderer, or screen justification/hyphenation.

```bash
rg -n "partner confidence|% confidence|evidence-backed|Path to a 9|Make your ruling|text-align:\s*justify|hyphens:\s*auto" \
  app-front-end/src/components app-front-end/src/lib
```

- [x] **Step 4: Run the full repository verification gate and record actual output.**

```bash
python3 -m pytest -o asyncio_mode=auto
cd app-front-end && npm run lint && npm test && npm run build && npm run check:bundle
cd web-front-end && npm run lint && npm run build && npm run check:bundle && npm run check:marketing
git diff --check
```

- [x] **Step 5: Review the diff against the approved audit.** Confirm every changed line traces to this plan, unrelated dirty-tree changes remain intact, and all public/tenant/policy invariants are preserved.

## Cutover and legacy handling

- Existing immutable canonical evaluations and rulings remain readable. New evaluations use the corrected fail-closed ordering.
- Persisted legacy Partner `INVEST | PASS | MONITOR` values are not rewritten. When canonical evidence is incomplete, a legacy value may appear only as a subordinate machine lean under `Blocked by evidence`.
- If no canonical opportunity/evaluation link exists, show `Unavailable` plus the named connection gap; do not manufacture a decision from legacy memo prose.
- The old visual dossier is retired from the primary render in this change, not kept behind a long-lived feature flag. Supporting legacy company analysis remains reachable in one disclosure until its data is natively claim-linked.
