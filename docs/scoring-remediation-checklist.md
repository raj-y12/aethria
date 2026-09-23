# Scoring Remediation — Checklist & Tracker

Historical decision log. The three-persona Reviewer, deterministic scorer, and
snapshot script cited below were retired in September 2026; their paths are
preserved here as references to the implementation assessed at the time.

**Companion to:** [`scoring-assessment-audit.md`](./scoring-assessment-audit.md)
**Purpose:** An incremental record of the former scoring architecture. Do **not** ship these as one change.
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
| Phase 2 — Canonical score (Workstream B) | ✅ 4 / 4 (P2.4: weighted_defensibility removed; confidence_adjusted_score kept—live in partner) |
| Phase 3 — Meaning fix (Layers 1–3) | ◑ P1.2+P3.2 ✅; P3.3 anchor rollout ✅; P3.4 qualitative flag (data + memo UI) ✅; P3.1 team-anchor ✅ — only prompt QUALITY (needs a model) outstanding |
| Phase 4 — Presentation vocabulary (Workstream C) | ◑ P4.2/P4.3/P4.4 ✅; P4.5 ✅; P4.1 drift-guard + rubric version-stamp ✅ — only runtime payload-derived band *thresholds* pending |
| Phase 5 — Calibration hardening (Layers 4–5) | ✅ P5.1 exemplars and P5.2 score-stability flag shipped; P5.3 ✅ |
| Phase 6 — Comparability completeness (Workstream A) | ✅ cohorts, stage isolation, sector TAM, and conservative sector component hooks shipped |
| Phase 7 — Outcome validity (Layer 6) | ◑ P7.1 ✅; P7.2 analysis-only until the verified outcome minimum is reached |

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

- [✅] **P1.2 — Abstain instead of `DEFAULT_SCORE = 5.0` (audit C2 + Layer 3).**
  **DONE (bundled with P3.2 — see Phase 3).** A standalone abstain fix was *unsafe*: the
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

- [✅] **P2.4 — Surface or delete dead signals (audit A5 — corrected).**
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

- [✅] **P1.2 + P3.2 (abstain framework + Market) — the core comparability fix.**
  The deterministic abstain framework is implemented and the Market dimension migrated:
  - **Extraction** (`extraction_layer.py`) no longer fabricates neutral labels
    (`urgency="important"`, `timing="neutral"`, `competition="moderate"`) when the
    source text is empty — it emits a missing signal instead.
  - **Aggregation** (`aggregation_layer.py`) excludes non-evidenced components and
    renormalizes over the evidenced ones; a dimension with **zero** evidence is flagged
    `unscored` (numeric placeholder kept so backend consumers don't crash, but the flag
    is the source of truth).
  - **Engine overall** excludes `unscored` dimensions, so a no-data dimension can no
    longer inflate or drag the headline.
  - **Frontend** renders `unscored` dimensions as "Not scored" (muted), never the
    placeholder number (`AssessmentDimensionStrip`, `ScoringDimension.unscored` type).
  - **Validation gate:** ✅ `all_missing` Market is now `unscored` and excluded
    (overall 3.96→3.35); the C2 headline bug is fixed — a no-evidence Market no longer
    outscores a verified-small one (golden `test_FIXED_unknown_market_is_unscored...`);
    154 backend tests pass with **zero ripple** into other suites; frontend tsc+eslint
    clean. Snapshot tool surfaces `unscored`.
  - **Model-dependent caveat:** this changes *deterministic* keyword-extraction
    fabrication only. The LLM-`structured_signals` path and prompt quality (real Layer
    1/2) still need model-in-the-loop evaluation.

- [◑] **P3.1 — Behaviorally-anchored criteria for ONE dimension (Layer 1).**
  Implemented as the worked pattern for `execution.team_execution`: the reviewer prompt
  now defines each label (`weak/decent/credible_team/strong/elite`) by **checkable
  evidence conditions** (e.g. elite = a founder with a prior venture-backed exit), tells
  the model to cite the evidence it used, and to **omit the signal when there's no
  evidence** (reinforces abstain). The anchor vocabulary matches the deterministic
  normalizer exactly (guard test).
  - Files: `backend/reviewer/base.py` (`_evidence_anchors_block`),
    `backend/tests/test_scoring_golden_snapshot.py` (parity guard).
  - **Validation gate:** ✅ prompt assembles; anchor labels == normalizer vocabulary;
    128 reviewer/scoring tests pass. ⏳ **prompt QUALITY** (does the model produce better
    team labels?) needs a model — validate by running the branch locally with a key.
  - **Follow-up:** roll the same evidence-anchored structure out to the other components.

- [✅] **P3.2 — Abstain rolled out across ALL dimensions.**
  Every component extractor now abstains (emits a missing signal) when its source text
  is empty, instead of fabricating a low/neutral label. So a dimension with no evidence
  is flagged `unscored` and excluded from the overall, across Market/Execution/Product/
  Technical/Defensibility.
  - Files: `backend/services/scoring/extraction_layer.py` (~18 extractors).
  - **Validation gate:** ✅ `all_missing` → every dimension unscored, overall `None`
    (a no-data company is honestly unscored, not a fabricated mid score);
    `structured_signals` → product/technical/defensibility unscored; `strong_saas`
    unchanged. Revealed the old system **under-scored** sparse companies by fabricating
    low labels (weak_thin 4.34→4.69). 151 backend tests pass; frontend renders
    "Not scored" for the realistic partial-data case.
  - ✅ **Off-vocabulary labels now abstain too.** `_map_label` returns an
    `UNRECOGNIZED_LABEL` sentinel (NaN) for a label outside a component's vocabulary;
    the engine converts it to a no-evidence component (placeholder score, value/label
    cleared) so aggregation excludes it instead of scoring a silent 5.0. No NaN leaks to
    consumers. (`test_FIXED_off_vocabulary_label_is_unrecognized_not_five_C2`.) The
    realistic trigger — the *LLM* emitting an off-vocab label in `structured_signals` —
    is what you'd confirm with a model; the deterministic exclusion is proven here.
  - **Remaining follow-up:** the abstain fires on *empty source text*; extending it to
    "evidence-present-but-keyword-miss" (vs the current substantive low reads) needs
    real-payload / model evaluation.

- [✅] **P3.3 — Roll the pattern across remaining fact-derivable components.**
  The single-component (team_execution) anchor block is now a catalog-driven
  `COMPONENT_EVIDENCE_ANCHORS` covering all 12 fact-derivable label components
  (traction, team, gtm, competition, pain_alignment, complexity, scalability,
  data_advantage, network_effects, switching_costs, proprietary_data, barriers) — each
  with checkable evidence conditions, rendered compactly to respect prompt-cost limits.
  Value components (tam/growth_rate/growth_velocity/retention) are threshold-scored and
  flagged as "give a number"; qualitative components are flagged qualitative.
  - Files: `backend/reviewer/base.py` (catalog + `_evidence_anchors_block`),
    `backend/config/scoring_config.py` (classification SSOT),
    `backend/tests/test_scoring_golden_snapshot.py` (`test_p33_evidence_anchors_match_normalizer_vocabulary`).
  - **Coverage note (rules-based vs qualitative):** 12 fact-derived (anchored) + 4 value
    (threshold) = 16 rules-based; 9 qualitative (`market.urgency`, `market.timing`,
    `execution.operational_velocity`, `product.value_prop`, `product.differentiation`,
    `product.ux`, `technical.engineering_quality`, `technical.architecture`,
    `defensibility.brand`). Partition is exhaustive over the 25 components.
  - **Validation gate:** ✅ every anchor label is a recognized normalizer label;
    classification partitions all 25 components exactly once; prompt assembles; 270
    backend tests pass. ⏳ prompt QUALITY (does the model produce better labels?) needs a
    model — same caveat as P3.1.
  - Depends on: P3.2

- [✅] **P3.4 — Mark qualitative dimensions as qualitative (Layer 5 partial).**
  Components with no objective anchor are classified `QUALITATIVE_COMPONENTS` (SSOT in
  `scoring_config.py`); the scoring engine stamps `qualitative: True` on those components
  in its output, and the reviewer prompt frames them honestly ("judgment; prefer null
  over a guess"). The `qualitative` flag flows to the memo so an evidence-backed 8 is
  distinguishable from a qualitative 8.
  - Files: `backend/config/scoring_config.py`, `backend/services/scoring/scoring_engine.py`,
    `backend/reviewer/base.py`, `backend/tests/test_scoring_golden_snapshot.py`
    (`test_p34_qualitative_components_are_flagged_in_engine_output`).
  - **Validation gate:** ✅ (data) qualitative components carry the flag, fact-derived /
    value components do not; 275 backend tests pass. ✅ (UI) the flag is threaded through
    `ScoringDriverRow` and rendered as a "qualitative" marker on driver rows in
    `DimensionCard`; methodology copy explains it; tsc/eslint clean.
  - Files (UI): `app-front-end/src/types/startup.ts`, `src/lib/scoringRationale.ts`,
    `src/components/scoring/DimensionCard.tsx`, `src/components/InvestmentMemoContent.css`.
  - Depends on: P3.3

---

## Phase 4 — Presentation vocabulary (Workstream C)

> One scale, one set of words per axis, methodology visible.

- [◑] **P4.1 — One banded scale, rubric-derived, version-stamped.**
  Structural guard added: a pytest parity test reads the frontend `SCORE_BANDS` and the
  canonical rubric and fails CI on any drift (so the B1 fix can't silently regress).
  - Files: `backend/tests/test_frontend_band_parity.py` (new).
  - **Validation gate:** ✅ parity test passes; an intentional mismatch fails loudly.
  - ✅ **Rubric version stamp added:** `ScoreOverview` now renders the rubric/policy
    version (`policy_version_id` → `policy_hash` fallback) in the "How this was scored"
    block; tsc/eslint clean.
  - **Remaining:** derive the band *thresholds* from the policy payload at runtime (no
    hand-mirror) — a deeper wire change; the drift-guard test keeps the hand-mirror safe
    until then.
  - Depends on: P1.1

- [✅] **P4.2 — Distinct words per axis (audit B2).**
  `QUALITY_LABELS.MEDIUM` was "Promising but incomplete" — "Promising" is also a
  dimension band. Changed to "Watchlist-grade". The three vocabularies (dimension
  bands / verdict labels / decision labels) are now word-disjoint.
  - Files: `app-front-end/src/design-system/semantics.ts`.
  - **Validation gate:** ✅ node disjointness check — no verdict/decision label shares
    a word with any dimension band; `tsc`/eslint clean.
  - Follow-up: the compact reviewer rows still render the raw verdict enum
    (`STRONG`/`WEAK`, all-caps) which differs from the title-case band words only by
    register; mapping those to `QUALITY_LABELS` is deferred (compact-row layout risk).
  - Depends on: P1.1

- [✅] **P4.3 — One conviction scale end-to-end (audit B3).**
  Grid and memo use the same scale; kill the `78/10` interpolation hazard.
  - Files: `QueueVerdictLine`, `InvestmentMemoContent.tsx:911`.
  - **Validation gate:** the same startup shows the same conviction value/format in
    grid and memo; no `/10` is ever applied to a 0–100 field.
  - Depends on: P2.2

- [✅] **P4.4 — One confidence treatment (audit B5).**
  Collapse the three confidence representations into one consistent model;
  conviction and confidence are clearly separate axes.
  - Files: `reviewScoring.ts:21-25`, `ConfidenceIndicator.tsx`, memo components.
  - **Validation gate:** confidence is shown one way throughout; no second "score"
    competes with the overall.
  - Depends on: P1.3

- [✅] **P4.5 — Expose methodology (audit B6/A6).**
  `sanitizeReasoning`'s `INTERNAL_REASONING_PATTERNS` was over-aggressive — it stripped
  legitimate methodology prose ("Normalization", "Aggregation", "Weight 30%",
  "Evidence: complete", "Component weights", "Policy inputs", "Rule engine",
  "Missing-data rule:", "extracted from"). Relaxed to strip ONLY genuine code/debug
  identifiers (`normalize_`/`_extract_`/`classify_`/`policy_hash`/`policy_version`/
  `source_components`/module names/scout-payload plumbing). Methodology weights and
  rubric/aggregation language now render, so an analyst can answer "why a 7?".
  - Files: `app-front-end/src/lib/reviewScoring.ts` (`INTERNAL_REASONING_PATTERNS`).
  - **Validation gate:** ✅ legitimate weights/rubric/evidence-status text is shown;
    `normalize_`/`_extract_`/`policy_hash` strings stay hidden; `tsc --noEmit` clean;
    eslint clean.
  - **Remaining:** the deliberate "How this was scored" block that renders the Layer 1–2
    evidence trail + rubric version inline is folded with P4.1's version-stamp work.
  - Depends on: P3.2

---

## Phase 5 — Calibration hardening (Layers 4–5)

- [✅] **P5.1 — Reference exemplars in the scoring prompt (Layer 4).**
  One canonical worked example per label is rendered from the existing component anchors.
  - Files: `backend/reviewer/base.py`, scoring prompt builders.
  - **Validation gate:** prompt contains fixed exemplars; cache-hit confirmed; a
    repeat-scoring drift test shows reduced variance vs baseline.
  - Depends on: P3.1

- [✅] **P5.2 — Label-stability measurement (Layer 5).**
  Reviewer score variance is retained and, when the compiled policy limit is exceeded,
  the field is marked unstable and reviewer disagreement is raised rather than hidden
  behind a precise-looking consensus.
  - Files: reviewer engine, `reviewer_resolution.py`.
  - **Validation gate:** a high-variance case is flagged low-confidence rather than
    averaged into a precise number.
  - Depends on: P3.4

- [✅] **P5.3 — Persona display honesty (audit A2).**
  Added a provenance note at the top of the Reviewer-detail section: "Persona lenses, not
  independent scorers. The published score is computed deterministically from extracted
  evidence; these reads show how each lens weighs the same case." The persona rows remain
  for the shape-of-disagreement signal, but no longer read as three authoritative votes
  producing the headline.
  - Files: `app-front-end/src/components/InvestmentMemoContent.tsx`,
    `app-front-end/src/components/InvestmentMemoContent.css`.
  - **Validation gate:** ✅ memo states the published number's provenance (deterministic,
    not a 3-persona average); tsc/eslint clean.
  - Depends on: P2.2

---

## Phase 6 — Comparability completeness (Workstream A)

- [◑] **P6.1 — Stage cohorts (audit C4).**
  Backend done: `resolve_stage_cohort` maps the scout `funding_stage` to a canonical
  cohort (pre_seed/seed/series_a/series_b_plus/unknown); the engine surfaces
  `stage_cohort` + `stage_cohort_label` in its trace (now typed on `StructuredScoring`
  and copied through `reviewScoring.ts`). Scores stay absolute (decision log) — the
  cohort is display context only.
  - Files: `backend/config/scoring_config.py`, `backend/services/scoring/scoring_engine.py`,
    `app-front-end/src/types/startup.ts`, `app-front-end/src/lib/reviewScoring.ts`,
    `backend/tests/test_scoring_golden_snapshot.py` (`test_p61_stage_cohort_is_captured_and_labelled`).
  - **Validation gate:** ✅ cohort captured + labelled; same evidence in different cohorts
    yields identical absolute scores (cohort is framing, not a multiplier); rendered in
    the memo as an "Assessed as <cohort>-stage" context line (`ScoreOverview`); 275
    backend pass; tsc/eslint clean.
  - Depends on: P3.3

- [✅] **P6.2 — Remove stage-word contamination of traction (audit §5 coupling).**
  Removed the four stage-word synonyms (`seed`/`pre_revenue`/`pre-revenue`/`growth`)
  from `_LABEL_SYNONYMS`; a stage word now abstains (`UNRECOGNIZED_LABEL` → excluded
  from aggregation) instead of hard-mapping into traction (`seed→early_adoption`,
  `growth→scaling`). Traction is driven only by traction evidence.
  - Files: `normalization_layer.py` (synonyms block), `tests/test_scoring_golden_snapshot.py`
    (`test_FIXED_stage_word_does_not_set_traction_score_P62`).
  - **Validation gate:** ✅ stage words → `is_unrecognized`; genuine traction labels still
    score; end-to-end a `traction:"seed"` structured signal is excluded (`unrecognized_label`),
    not scored. 268 backend tests pass, zero ripple.
  - Depends on: P3.2

- [◑] **P6.3 — Sector benchmarks (audit C5).**
  TAM is now scored against sector-relative thresholds: `SECTOR_TAM_THRESHOLDS` +
  `resolve_tam_benchmark(sector)` route `normalize_tam(value, thresholds)` so an
  identical $1B TAM scores lower for fintech (capital-heavy) than dev-tools. The chosen
  benchmark label rides on the trace (`sector_tam_benchmark`, typed + copied through).
  Absolute scale preserved; default benchmark == prior behavior (zero ripple for
  sector-less fixtures).
  - Files: `backend/config/scoring_config.py`, `backend/services/scoring/normalization_layer.py`,
    `backend/services/scoring/scoring_engine.py`, frontend types/lib,
    `backend/tests/test_scoring_golden_snapshot.py` (`test_p63_identical_tam_scores_by_sector_benchmark`).
  - **Validation gate:** ✅ same $1B TAM → dev-tools Market.tam > fintech Market.tam;
    benchmark label emitted and rendered in the memo ("Market graded vs <benchmark>",
    `ScoreOverview`); 275 backend pass; tsc/eslint clean. Component adjustments for
    `market.competition` and `technical.complexity` are now policy-only, bounded to
    +/-1, and default to no-op so no existing scores move without explicit policy data.
  - Depends on: P3.3

---

## Phase 7 — Outcome validity (Layer 6, long horizon)

- [✅] **P7.1 — Persist the structured evidence + score trail per decision.**
  **Append-only** `public.scoring_trails` table (facts/labels/component scores in `trail`
  jsonb + rubric/policy version, overall, stage cohort, sector benchmark), indexed for
  the per-startup read and the P7.2 calibration scan, RLS-locked to the service role.
  Separate table (not a JSONB column on the churny `startups` row) preserves history and
  avoids re-adding the write amplification a prior migration removed.
  `SupabaseStartupsStorage.record_scoring_trail` inserts the trace; the reviewer engine
  calls it once per startup after the primary review is finalized (best-effort — a
  trail-write failure can never break a review; no-op on file-storage dev backends).
  - Files: `supabase/migrations/20260604000002_scoring_trail.sql`,
    `backend/legacy_supabase/storage.py` (`record_scoring_trail`),
    `backend/reviewer/engine.py` (`_persist_scoring_trail` + call site),
    `backend/tests/test_scoring_trail_write.py` (new).
  - **Validation gate:** ✅ migration **APPLIED to aethria-prod** (`scoring_trails` exists,
    RLS-locked, indexed — advisor only flags `rls_enabled_no_policy` INFO, the DB-wide
    convention for this service-role-only schema); insert writes the denormalized columns
    + full trace; DB error returns False without raising; 275 backend tests pass. Live
    rows populate on the next pipeline review run.
  - Depends on: P3.2

- [◑] **P7.2 — Outcome → anchor recalibration loop.**
  An analysis-only helper now accepts an explicit score/outcome join, excludes unverified
  or disputed observations, and returns no proposals below a caller-supplied verified
  sample minimum. It never guesses identity matches or mutates live policy. Re-fitting
  remains pending sufficient verified outcomes.
  - Files: `backend/meta/calibrator.py` (extend), analysis tooling.
  - **Validation gate:** analysis readiness is documented and fail-closed; a predictive
    before/after recalibration run remains pending verified outcome volume.
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
