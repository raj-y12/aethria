# Reviewer Audit Remediation — Findings and Sequencing

**Date:** 2026-08-17. Follow-on to the Aug 15 design audit
(`docs/archive/DESIGN-IS-2026-08-15-reviewer-section/`, 7/30, verdict REDESIGN) and
today's Sub-project 4 work. Findings below are freshly verified against the
current codebase, not a restatement of the Aug 15 doc — several of its citations
have since moved or changed.

## Findings, as found

1. **The three reviewer "personas" are still undisclosed.** Live-verified today
   (Manna Air Delivery): "Default 5.0 · Skeptical 4.7 · Opportunist 4.9" rendered
   as a panel with no disclosure that all three are one model over one shared
   evidence packet, differentiated only by prompt posture (`reviewer/skeptical.py:11-19`
   — *"if data is missing, assume the worst"* — vs. `reviewer/opportunist.py:11-18`
   — *"give benefit of doubt... be more generous"*). Unchanged since Aug 15.

2. **`services/reviewer_resolution.py`'s `apply_resolution_to_primary` is provably
   dead compute in the governed (live) path.** Traced the exact call order in
   `reviewer/engine.py`:
   - `_blend_numeric_scores_into_primary` (`engine.py:472-488`) sets
     `primary["market_score"]` etc. from `resolve_governed_scoring_traces` —
     the real, authoritative governed trace — and returns.
   - `apply_resolution_to_primary` (`engine.py:1159-1161`) immediately overwrites
     those same fields with a second, independently-computed conservative blend.
   - `_refresh_derived_after_dimension_changes` → `_project_governed_trace`
     (`engine.py:1162`, `558-581`) immediately overwrites them back to the
     governed trace.
   Net effect of the middle step: zero, every time, for every company, provably.
   Runs on every review regardless.

3. **`resolution_notes` / `disagreement_summary` are zombie fields.** Computed by
   the dead call above, persisted to the DB, typed all the way to the frontend
   (`app-front-end/src/types/startup.ts:443-445`), read by nothing. Confirmed
   while building today's "personas diverged" flag (which reads a *different*,
   real signal — `structured_scoring[dim].components.persona_resolution` from
   `evaluation_v2/governed_scoring.py` — instead).

4. **"N% evidenced" still measures the wrong thing.** It's the percentage of
   rubric criteria that didn't hit a missing-data fallback, not verified evidence
   or source coverage (`reviewer/engine.py:50-71` computes it; rendered live today
   in `InvestmentMemoContent.tsx`'s `hasPanel` fallback block with that exact
   framing, unlabeled as such).

5. **Today's own `score_band`/`score_justification` fix (`c1e792d8`) has an
   unvalidated gap.** `evidence/extraction.py` checks the model's claimed
   `score_band` is one of `{"high","mid","low"}` but never cross-checks it
   against the actual `criterion_score` or the rubric's numeric band ranges — a
   model could claim `"high"` for a 6.0 when the rubric's high band starts at 8,
   and nothing catches the contradiction.

6. **73% of dimension-slots are still scored by the system items 1-4 describe.**
   Today's backfill moved canonical coverage from 2% to 27% (`docs/archive/plans/2026-08-16-legacy-canonical-consolidation.md`,
   Sub-project 2 section). The majority of what's on screen today still goes
   through the undisclosed-persona / dead-resolution / mislabeled-coverage path.
   Not a discrete task — a status to keep checking as coverage grows organically.

7. **Two separately-maintained renderers for the same reviewer-row list.**
   `AssessmentScorecard.tsx`'s built-in reviewer panel (lines ~276-307) and
   `InvestmentMemoContent.tsx`'s `hasPanel` fallback block (lines ~724-750) are
   mutually exclusive (`hasScorecard ? ... : hasPanel ? ...`) but implement
   near-identical row rendering independently — confirmed still diverging (only
   the fallback renders `coverage`).

8. **No accessibility or state coverage.** No reviewer-specific empty/loading/
   error states; no `aria-controls` on the expand/collapse buttons; no keyboard
   or focus-contrast tests. `AssessmentScorecard.test.tsx` (added today) covers
   exactly the one flag built today, nothing else. Unchanged since Aug 15.

## Sequencing — smallest safe fix first, redesign-scale work last

| # | Item | Why here | Effort | Risk |
|---|---|---|---|---|
| 1 | **Delete #2 + #3** — the dead `apply_resolution_to_primary` call and its zombie output fields | Pure deletion, zero behavioral change (already proven to have zero effect), immediate clarity. Free. | Trivial | None — deleting code with no observable effect |
| 2 | **Fix #5** — cross-validate `score_band` against the actual score and rubric range | Protects the credibility of the fix shipped an hour ago before it ships more broadly. Small, scoped, additive. | Small | Low |
| 3 | **Fix #4** — relabel or correctly compute "% evidenced" | Small, scoped, immediate honesty win on a currently-live misleading number. | Small | Low |
| 4 | **Fix #1** — disclose the three personas as shared-evidence AI lenses with named postures | Bigger than 1-3 but still primarily copy/labeling + a small structural note, not a redesign. Highest trust impact of the remaining items. | Medium | Low-medium (copy + minor component change) |
| 5 | **Consolidate #7** — one reviewer-row renderer, not two | Real work, touches shared rendering paths on both branches of the conditional. Do after 1-4 are stable so there's less moving underneath it. | Medium | Medium |
| 6 | **#8** — states, a11y, tests | Legitimate but lowest urgency relative to correctness/honesty fixes above. Broad, open-ended scope — do last, and likely as its own follow-on plan rather than one task. | Large | Low (additive, but time-consuming) |
| — | **#6** | Not a task — a metric to keep checking as coverage grows organically (already tracked in the Sub-project 2 vault note). | — | — |

**Not sequenced as a task at all:** the full Aug 15 redesign scope (disagreement
matrix, drill-down, full IA rework). Items 1-5 above address the audit's Honest
and As-little-design-as-possible failures without committing to that larger,
riskier redesign. Revisit the full redesign only if these targeted fixes turn
out insufficient.

## Status

- [x] Item 1 — remove the zombie `resolution_notes`/`disagreement_summary` fields.
  **Correction made while implementing:** `apply_resolution_to_primary`'s score
  mutation is not universally dead as first described — it's the real fallback
  when there's no active thesis (`_refresh_derived_after_dimension_changes`
  reads, not overwrites, `primary[score]` in that branch). Only overwritten by
  the governed trace when a thesis is active. The call itself was kept; only
  its two unread output fields were removed. `abb8adba`.
- [x] Item 2 — `score_band` is now always computed deterministically from the
  score and the rubric's numeric ranges, never trusted from the model's own
  claim. `abb8adba`.
- [x] Item 3 — relabelled "% evidenced" → "% data coverage" in both renderers,
  with a code comment on what the metric actually measures. `abb8adba`.
- [x] Item 4 — added a one-line disclosure ("One model, one evidence packet,
  three prompted postures — not independent reviews.") to both reviewer-row
  renderers, plus a per-row tooltip naming each persona's actual instructed
  posture. `abb8adba`.
- [ ] Item 5 — consolidate the two reviewer-row renderers.
- [ ] Item 6 — states/a11y/test coverage.

Verified: full backend suite (same 39 pre-existing Postgres-container failures,
zero regressions), full frontend suite (469/469), `tsc`, `eslint --max-warnings
0`, production build, and `check:bundle` all clean after items 1-4.
