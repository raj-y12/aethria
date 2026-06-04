# Scoring Remediation — Checklist & Tracker

**Companion to:** [`scoring-assessment-audit.md`](./scoring-assessment-audit.md)
**Purpose:** A living, incremental tracker. Do **not** ship these as one change.
Work one task at a time, tick it only when its **Validation gate** passes.

---

## How to use this document

- Each task has: an **ID** (keyed to audit issues), the **files** it touches, a
  concrete **Validation gate** (how you prove it's done — a test, a grep, or a
  manual memo check), and **Depends on**.
- Update the **Status** marker as you go. Keep `Owner` / `PR` / `Date` current so the
  thread shows live state.
- A task is only `✅ Validated` when its gate has actually been run and passes — not
  when the code is written.

### Status legend

| Marker | Meaning |
|---|---|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Code complete, gate **not yet** run |
| `[✅]` | Validated — gate run and passing |
| `[⛔]` | Blocked (note blocker in the row) |

### Progress

| Phase | Done / Total |
|---|---|
| Phase 0 — Guardrails | ✅ 2 / 2 |
| Phase 1 — Stop the bleeding (highest severity, lowest effort) | ✅ 2 / 2 (P1.2 re-sequenced → Phase 3) |
| Phase 2 — Canonical score (Workstream B) | ✅ 3 / 4 (P2.4 split: surface→Phase 4, orphan-removal deferred) |
| Phase 3 — Meaning fix (Layers 1–3) | 0 / 4 |
| Phase 4 — Presentation vocabulary (Workstream C) | 0 / 5 |
| Phase 5 — Calibration hardening (Layers 4–5) | 0 / 3 |
| Phase 6 — Comparability completeness (Workstream A) | 0 / 3 |
| Phase 7 — Outcome validity (Layer 6) | 0 / 2 |

> Update these counts whenever a row flips to `[✅]`.

---

## Phase 0 — Guardrails (do first; protects every later change)

- [✅] **P0.1 — Snapshot current scoring behaviour as golden tests.**
  Characterization tests pin the EXACT current deterministic scores for representative
  fixtures (the existing suite only checked shape/bounds). Includes `KNOWN_ISSUE`
  locks that capture current buggy behavior (C2 missing→5.0, off-vocab→5.0, unknown
  outscores known-small) so remediation tasks must consciously flip them.
  - Files: `backend/tests/test_scoring_golden_snapshot.py` (new).
  - **Validation gate:** ✅ `pytest tests/test_scoring_golden_snapshot.py` → 18 passed;
    existing scoring suite still green (23 passed); a drifted score fails loudly with a
    pointer to update GOLDEN.
  - Depends on: —

- [✅] **P0.2 — Single comparison harness for before/after.**
  Dependency-light snapshot tool (no LLM/Supabase) renders deterministic scores for the
  same fixtures as stable, sorted JSON for diffing; `--payload` scores an arbitrary
  `{scout, review}` file.
  - Files: `backend/scripts/scoring_snapshot.py` (new).
  - **Validation gate:** ✅ two consecutive runs produce an empty `diff`;
    `--payload` mode scores a single company. Usage:
    `python scripts/scoring_snapshot.py > before.json` → change → `> after.json` → diff.
  - Depends on: —

  > Note: P0.1/P0.2 cover the **deterministic scoring layer** (the pure, highest-risk
  > surface for the upcoming changes). A frontend memo-render snapshot is deferred to
  > when Phase 4 (presentation) work begins, since that's the first phase that touches
  > the memo UI.

---

## Phase 1 — Stop the bleeding

> Highest severity, smallest changes. These remove active wrong/confusing output.

- [✅] **P1.1 — Fix the band mismatch (audit B1).** 🔴 highest severity
  Frontend `SCORE_BANDS` now mirrors the versioned rubric exactly (4-band:
  Weak 1–3 / Concerning 4–5 / Promising 6–7 / Strong 8–10); `getScoreBand`
  thresholds and the (previously false) "aligned" comment corrected.
  - **Decision (resolved):** canonical banding = the rubric's 4-band scale in
    `evaluation_rubric/v1.json` (versioned policy is the source of truth per
    CLAUDE.md). The richer 5-band UI scale was dropped to match the bands the
    reviewer actually scores against. Structural enforcement (derive from payload,
    no hand-mirror) is deferred to P4.1.
  - Files: `app-front-end/src/design-system/semantics.ts`.
  - **Validation gate:** ✅ node parity check — for every integer score 1–10 the
    frontend label equals the rubric label (previously `7`→"Strong" vs rubric
    "Promising"); `tsc --noEmit` clean; eslint clean.
  - Depends on: P0.1

- [⛔] **P1.2 — Abstain instead of `DEFAULT_SCORE = 5.0` (audit C2 + Layer 3).**
  **RE-SEQUENCED → bundled with P3.2.** A standalone abstain fix is *unsafe*: the
  extraction layer fabricates neutral labels (`urgency="important"`,
  `timing="neutral"`, `competition="moderate"`) for no-evidence components, so they
  pass `_has_concrete_evidence`. Excluding only the truly-missing components and
  renormalizing weights makes an all-missing company's Market score go **up** (5.78 →
  6.55), the opposite of the intent. Abstain only works once extraction emits facts /
  `unscored` instead of fabricated labels (P3.2). Verified empirically 2026-06-04.
  - Depends on: P3.2 (extraction emits facts, not fabricated labels)

- [✅] **P1.3 — Stop truncating the digit on low confidence (audit B5).**
  Removed the `Math.round(score)` low-confidence path; the digit is always
  `toFixed(1)`. Low confidence is now signalled by a non-destructive cue
  (`memoScoreBriefScore--lowConfidence`: dimmed + dotted underline + tooltip),
  never by changing the number.
  - Files: `app-front-end/src/components/scoring/AssessmentDimensionStrip.tsx`,
    `app-front-end/src/components/InvestmentMemoContent.css`.
  - **Validation gate:** ✅ a low-confidence 7.5 renders as `7.5` (no rounding path
    remains); `tsc --noEmit` clean; eslint clean.
  - Depends on: —

---

## Phase 2 — Canonical score (Workstream B)

> One overall, one formula, reproducible from the dimensions shown.

- [✅] **P2.1 — Implement defensibility's resolved role (audit A3).**
  Defensibility excluded from the canonical overall. Added
  `OVERALL_SCORE_DIMENSIONS = (market, product, technical, execution)`; the engine's
  `_compute_overall_score`/`_compute_overall_confidence` now iterate only those four,
  so the engine overall is identical to `utils.scoring.compute_overall_score`
  (immune to whatever per-dimension weights flow in). Dimension scores unchanged.
  - Files: `backend/config/scoring_config.py`, `backend/services/scoring/scoring_engine.py`,
    `backend/tests/test_scoring_golden_snapshot.py` (GOLDEN updated + invariant test).
  - **Validation gate:** ✅ engine overall == 4-dim mean for all fixtures
    (strong_saas 6.28→7.26); new `test_overall_is_four_dimension_mean_excluding_defensibility`;
    91+ scoring/partner/reviewer tests green; partner decisions unchanged (they already
    used the 4-dim `compute_overall_score`).
  - Depends on: P0.1

- [✅] **P2.2 — Single `overall_score` source (audit A4).**
  Backend already canonical (4-dim `compute_overall_score`, now matched by the engine
  via P2.1). Fixed the frontend fallback in `reviewScoring.ts` which synthesised a
  5-dim mean — now a 4-dim mean (defensibility excluded), preferring the
  backend-computed value.
  - Files: `app-front-end/src/lib/reviewScoring.ts`.
  - **Validation gate:** ✅ frontend fallback excludes defensibility and matches the
    backend definition; `tsc`/eslint clean.
  - Depends on: P2.1

- [✅] **P2.3 — Dimensions reconcile to the overall, with a printed caption (audit B4).**
  Data invariant holds (overall == mean of the 4 drivers, pinned by golden test).
  Added a memo caption: "Overall = mean of Market, Product, Technical, Execution.
  Defensibility is a separate moat signal and is not averaged in."
  - Files: `app-front-end/src/components/scoring/ScoreOverview.tsx`.
  - **Validation gate:** ✅ averaging the 4 driver dimensions reproduces the overall;
    caption states inclusion explicitly; `tsc`/eslint clean.
  - Note: visually separating the defensibility tile from the 4 driver tiles in
    `AssessmentDimensionStrip` is folded into the Phase 4 presentation pass.
  - Depends on: P2.2

- [~] **P2.4 — Surface or delete dead signals (audit A5 — corrected).**
  **Correction:** `confidence_adjusted_score` is NOT dead — `partner/decision.py:654`
  uses it for grey-zone decisions (A5 referred to *memo UI* only). Action split:
  - `confidence_adjusted_score`: **surface** in the memo → folded into Phase 4 (it is a
    live, meaningful conviction signal; deleting would break partner grey-zone logic).
  - `weighted_defensibility_score`: the float *output* field is unconsumed (frontend
    has zero refs; partner never reads it), BUT it is **not** a pure dead field — at
    `reviewer/engine.py:271` the same `weighted_def` computation (skeptical reviewer
    counted 1.5×) actively **sets the published `defensibility_score`**. So removing
    it changes defensibility scores; it is a behavior change, not a cleanup.
    **Deferred** to a focused, test-gated change that decides whether the 1.5×-skeptical
    weighting of defensibility should remain (touches `reviewer/engine.py`, `api.py`,
    `models.py`, `utils/adapters.py`).
  - Depends on: P2.1; coordinate with Phase 4.

---

## Phase 3 — Meaning fix (Layers 1–3 core)

> Move judgment from the model into evidence + rules. Roll out **per dimension**.

- [ ] **P3.1 — Behaviorally-anchored criteria for ONE dimension as the pattern (Layer 1).**
  Start with Team/Execution or Technical. Replace adjective labels with
  evidence-bound conditions.
  - Files: `backend/config/scoring_config.py` (rubric block),
    `resources/config/evaluation_rubric/v1.json`.
  - **Validation gate:** the chosen dimension's labels are each defined by checkable
    conditions; a reviewer can point at the evidence that fired the score; golden
    tests updated and reviewed.
  - Depends on: P0.1

- [ ] **P3.2 — Extraction emits facts + citations for that dimension (Layer 2).**
  LLM returns atomic cited facts; a deterministic rule maps facts → label → score.
  - Files: `backend/services/scoring/extraction_layer.py`,
    `backend/services/scoring/normalization_layer.py`.
  - **Validation gate:** the dimension's score is derived in code from extracted
    facts (not an LLM-chosen label); the same facts always yield the same score;
    citations are present.
  - Depends on: P3.1

- [ ] **P3.3 — Roll the pattern across remaining fact-derivable components.**
  Apply P3.1–P3.2 to the ~70% that is fact-derivable (tam, traction, team, retention,
  data advantage, …).
  - **Validation gate:** each migrated component has criteria + fact-derived scoring;
    a coverage note lists which components are now rules-based vs still qualitative.
  - Depends on: P3.2

- [ ] **P3.4 — Mark qualitative dimensions as qualitative (Layer 5 partial).**
  Technical/Defensibility components with no objective anchor are explicitly labelled
  qualitative in the data and the UI.
  - Files: scoring config, memo components.
  - **Validation gate:** the memo visibly distinguishes an evidence-backed Market 8
    from a qualitative Defensibility 8.
  - Depends on: P3.3

---

## Phase 4 — Presentation vocabulary (Workstream C)

> One scale, one set of words per axis, methodology visible.

- [ ] **P4.1 — One banded scale, rubric-derived, version-stamped.**
  Frontend imports/derives bands from the policy payload; memo shows the rubric
  version it was scored under.
  - Files: `semantics.ts`, memo components, `evaluation_rubric/v1.json`.
  - **Validation gate:** changing the rubric changes the memo bands with no frontend
    edit; memo displays `scored under rubric vX`.
  - Depends on: P1.1

- [ ] **P4.2 — Distinct words per axis (audit B2).**
  Dimension band, panel verdict, and decision never share a word.
  - Files: `semantics.ts` (`SCORE_BANDS`, `QUALITY_LABELS`, `DECISION_LABELS`).
  - **Validation gate:** no single word appears in two of the three vocabularies; a
    test asserts disjoint label sets.
  - Depends on: P4.1

- [ ] **P4.3 — One conviction scale end-to-end (audit B3).**
  Grid and memo use the same scale; kill the `78/10` interpolation hazard.
  - Files: `QueueVerdictLine`, `InvestmentMemoContent.tsx:911`.
  - **Validation gate:** the same startup shows the same conviction value/format in
    grid and memo; no `/10` is ever applied to a 0–100 field.
  - Depends on: P2.2

- [ ] **P4.4 — One confidence treatment (audit B5).**
  Collapse the three confidence representations into one consistent model;
  conviction and confidence are clearly separate axes.
  - Files: `reviewScoring.ts:21-25`, `ConfidenceIndicator.tsx`, memo components.
  - **Validation gate:** confidence is shown one way throughout; no second "score"
    competes with the overall.
  - Depends on: P1.3

- [ ] **P4.5 — Expose methodology, stop censoring it (audit B6/A6).**
  Render the evidence trail (Layers 1–2) and rubric version in a deliberate
  "How this was scored" block; keep stripping only genuine debug strings.
  - Files: `reviewScoring.ts:180-212` (`sanitizeReasoning`), memo components.
  - **Validation gate:** an analyst can answer "why is this a 7?" from the memo
    alone; legitimate weights/rubric text are shown while `normalize_`/`_extract_`/
    `policy_hash` debug strings stay hidden.
  - Depends on: P3.2

---

## Phase 5 — Calibration hardening (Layers 4–5)

- [ ] **P5.1 — Reference exemplars in the scoring prompt (Layer 4).**
  One canonical worked example per label; use prompt caching.
  - Files: `backend/reviewer/base.py`, scoring prompt builders.
  - **Validation gate:** prompt contains fixed exemplars; cache-hit confirmed; a
    repeat-scoring drift test shows reduced variance vs baseline.
  - Depends on: P3.1

- [ ] **P5.2 — Label-stability measurement (Layer 5).**
  Score judgment-heavy dimensions N× / across personas; disagreement → low confidence
  + flag, not false precision.
  - Files: reviewer engine, `reviewer_resolution.py`.
  - **Validation gate:** a high-variance case is flagged low-confidence rather than
    averaged into a precise number.
  - Depends on: P3.4

- [ ] **P5.3 — Persona display honesty (audit A2).**
  Present persona rows as qualitative lenses, not three independent authoritative
  votes; show what actually drove the published number.
  - Files: `InvestmentMemoContent.tsx` reviewer detail/consensus sections.
  - **Validation gate:** the memo no longer implies three independent scorers produced
    the headline; the published number's provenance is clear.
  - Depends on: P2.2

---

## Phase 6 — Comparability completeness (Workstream A)

- [ ] **P6.1 — Stage cohorts (audit C4).**
  Score against a stated stage cohort; print it ("Execution 7 — strong *for Seed*").
  - Files: scoring config, extraction (stage), memo components.
  - **Validation gate:** the same evidence yields the cohort-appropriate framing; the
    memo states the cohort; within-cohort comparability is preserved.
  - Depends on: P3.3

- [ ] **P6.2 — Remove stage-word contamination of traction (audit §5 coupling).**
  `"seed"/"pre_revenue"/"growth"` must not hard-map into traction labels.
  - Files: `normalization_layer.py:104-107`.
  - **Validation gate:** a stage word in the payload no longer sets the traction
    score; traction is driven by traction evidence only.
  - Depends on: P3.2

- [ ] **P6.3 — Sector benchmarks (audit C5).**
  Anchor TAM/complexity/competition to sector-relative references.
  - Files: `config/scoring_config.py`, normalization.
  - **Validation gate:** an identical TAM yields sector-appropriate Market scores; the
    memo notes the sector benchmark used.
  - Depends on: P3.3

---

## Phase 7 — Outcome validity (Layer 6, long horizon)

- [ ] **P7.1 — Persist the structured evidence + score trail per decision.**
  Store facts, labels, scores, rubric version for every memo so future calibration is
  possible.
  - Files: storage layer, `supabase/migrations/` (new migration).
  - **Validation gate:** every scored startup has a retrievable, versioned scoring
    trail.
  - Depends on: P3.2

- [ ] **P7.2 — Outcome → anchor recalibration loop.**
  Map scores to outcomes (advanced / died / marked up) and re-fit anchors to be
  predictive.
  - Files: `backend/meta/calibrator.py` (extend), analysis tooling.
  - **Validation gate:** a documented recalibration run adjusts anchors based on
    realized outcomes, with before/after predictive metrics.
  - Depends on: P7.1, volume of outcomes

---

## Decision log

> Record the irreversible calls here as you make them, so they aren't relitigated.

| Date | Decision | Made by | Notes |
|---|---|---|---|
| 2026-06-04 | **Canonical banding = rubric 4-band** (Weak/Concerning/Promising/Strong). Frontend mirrors it; structural derive-from-payload deferred to P4.1. | Claude (delegated) | Versioned policy is SSOT per CLAUDE.md. Unblocked P1.1 (done). |
| 2026-06-04 | **Defensibility = risk/moat modifier, EXCLUDED from canonical overall.** Canonical overall = mean(market, product, technical, execution). | Claude (delegated) | Matches the existing partner decision (4-dim `compute_overall_score`), so INVEST/PASS thresholds stay stable; avoids defensibility's systematic low default (~2.35) tanking every overall; resolves A3 three-way conflict. Memo shows 4 driver tiles (which average to the overall) + defensibility as a separate labelled moat signal (B4). |
| 2026-06-04 | **Stage handling = labelled cohorts** (keep absolute anchors; capture + display the stage cohort; judge maturity-dependent criteria within cohort). | Claude (delegated) | Stage-relative anchors would break the absolute scale that makes cross-company comparison possible. Implement in Phase 6. |
| 2026-06-04 | **P1.2 re-sequenced to bundle with P3.2.** | Claude (delegated) | Standalone abstain backfires due to extraction fabricating neutral labels (5.78→6.55). See P1.2 row. |

---

## Open decisions that block work

All three original architectural forks are now **RESOLVED** (see decision log,
2026-06-04): banding = rubric 4-band; defensibility = risk modifier (out of overall);
stage = labelled cohorts. No open blockers remain; remaining work is execution.
