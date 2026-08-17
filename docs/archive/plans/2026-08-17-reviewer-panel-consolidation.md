# Reviewer Panel Consolidation — Task-Level Plan

Item #5 of `docs/archive/plans/2026-08-17-reviewer-audit-remediation.md`. Items 1-4
shipped (`abb8adba`). This is the next one.

## What's actually there (verified against current source, not the Aug 15 audit)

Two call sites render the reviewer-row list, and they've already diverged:

- `AssessmentScorecard.tsx` (lines ~298-332) — its own built-in panel: head shows
  `"Reviewers split"` (flag) or `"Reviewer panel"` (plain label) plus a spread line
  with verdict and a "conviction diverges" hint when spread ≥ 2; renders rows with
  name+posture tooltip, score, `take`.
- `InvestmentMemoContent.tsx`'s `hasPanel` branch (lines ~737-762) — a separate,
  simpler head (`"Split"`/`"Aligned"` + optional verdict tag, no spread line, no
  conviction-diverges hint); renders rows with name+posture tooltip, score,
  **`coverage`** (AssessmentScorecard's rows never show this), `take`.

They are mutually exclusive per render (`hasScorecard ? <AssessmentScorecard/> :
hasPanel ? <fallback/> : ...`), never both on screen at once — the Aug 15 audit's
literal claim of simultaneous duplication was already stale by the time it was
re-checked today, but the underlying problem it named is real: two independently
maintained implementations of the same row list, now visibly different (only the
fallback shows `coverage`; only the built-in panel shows the spread/conviction
line).

**Why both call sites are still needed — not a "delete one" situation.**
`hasScorecard` requires `config.memo.includeScoreReasoning` (a real, per-fund
config toggle, `fundConfiguration.ts:235`, defaults `true`) AND `structuredScoring`
being present. A fund that disables score reasoning, or an opportunity with no
`structuredScoring` yet, still needs *some* way to show reviewer rows —
`AssessmentScorecard` can't render at all without a `StructuredScoring` object (its
dimension rows index into `scoring[dim.key]`). So the fallback's reason to exist is
real. What's not needed is two separate implementations of the row list itself.

## Plan

**New file:** `app-front-end/src/components/scoring/ReviewerPanel.tsx` — extracted
from `AssessmentScorecard.tsx`'s existing block (the more complete of the two: keep
its head design — split flag / spread line / conviction-diverges hint — rather than
the fallback's simpler "Split"/"Aligned" text, since consolidating should not lose
information).

```ts
export type ReviewerPanelProps = {
  rows: ScorecardReviewerRow[];
  consensus: ScorecardReviewerConsensus;
  renderNumbers?: (value: unknown) => ReactNode;
};
export default function ReviewerPanel({ rows, consensus, renderNumbers = identity }: ReviewerPanelProps) { ... }
```

Moves in: the `REVIEWER_POSTURES` map (currently duplicated in both
`AssessmentScorecard.tsx` and `InvestmentMemoContent.tsx`), the disclosure line, the
head, and the row list including `coverage` (added to `ScorecardReviewerRow` — it's
already on `InvestmentMemoContent.tsx`'s local row type, just needs surfacing on the
shared one).

**Modify:**
- `AssessmentScorecard.tsx` — replace its inline panel block (lines ~298-332) with
  `<ReviewerPanel rows={reviewerRows} consensus={reviewerConsensus} renderNumbers={renderNumbers} />`.
- `InvestmentMemoContent.tsx` — replace the `hasPanel` branch's inline block (lines
  ~737-762) with the same `<ReviewerPanel .../>` call. Delete the now-unused local
  `REVIEWER_POSTURES` map (item #10 duplicated it here as an interim measure,
  explicitly pending this task).

**Files to read in full before touching:** both blocks in their entirety (already
done for this plan), `ScorecardReviewerRow`/`ScorecardReviewerConsensus` types
(`AssessmentScorecard.tsx:23-37`), the CSS classes referenced (`memoScorePanel`,
`memoConsensusHead`, `memoConsensusFlag`, `memoConsensusLabel`, `memoConsensusSpread`,
`memoScoreSub`, `memoConsensusList`, `memoConsensusRow`, `memoConsensusName`,
`memoConsensusScore`, `memoConsensusCoverage`, `memoConsensusTake`) in
`InvestmentMemoContent.css` to confirm both call sites can share them without a
visual regression in either location.

## Acceptance criteria

- Exactly one implementation of the reviewer-row list exists in the codebase.
- Both call sites render through it; behavior at each call site is preserved or
  improved (the fallback gains the spread/conviction line; nothing currently shown
  is lost — `coverage` survives into the shared component).
- `AssessmentScorecard.test.tsx`'s existing 5 tests continue passing unmodified
  (same props, same rendered output) or are updated only if the extraction changes
  a DOM structure they assert on.
- A new focused test file for `ReviewerPanel.tsx` covering: split flag, spread
  line + conviction-diverges hint, coverage rendering, posture tooltip.
- `tsc --noEmit`, `eslint --max-warnings 0`, full frontend test suite, production
  build, `check:bundle` all clean.

## Explicitly not in scope

- No change to *when* each call site renders (`hasScorecard`/`hasPanel` conditions
  untouched) — that's product behavior (which fund config shows what), not this
  task's concern.
- No visual redesign beyond reconciling the two heads to one design.
- Item #6 (states/a11y) — separate, later task.
