# Docket Row Redesign — "Annotated Dossier"

**Date:** 2026-06-12
**Scope:** The company rows in the Flow page docket (`WorkGrid` → `DocketCaseRow`). Filters/header (`DecisionQueueHeader`) and the Decision Stage are untouched.
**Goals:** Faster triage and a more premium feel, within the paper/oxford editorial language.

## 1. Row anatomy (ambient state)

Two-line entries replace the current single index line.

- **Margin column** (fixed ~96px, right-aligned, separated from the text block by a 2px hairline rule `oxford/10`):
  - The existing flat verdict chip (`VERDICT_CHIP_CLASS` + `DECISION_BADGE_CLASS` variant from `model.decisionVariant`): INVEST / PASS / MONITOR / awaiting / undecided / escalation ("Needs ruling").
  - The configured score below it (tabular numerals, 15px, `oxford/45` when unselected). Unscored rows show an em-dash.
- **Text block:**
  - Company name: 14px serif, `oxford/55`, hover `oxford/80`.
  - Second line: `oneLiner · sectorStage` (small sans, `oxford/50`, truncated to one line). Falls back to `sectorStage` alone when `oneLiner` is null.
- The row index number (`displayIndex`) is removed; the margin column is the new anchor.

## 2. Selection state ("open file")

The selected entry steps forward on every axis:

- Name: 14px → 22px, semibold, full oxford ink, slight negative tracking.
- Score: 15px → 24px, full ink.
- Chip: steps up to full size (9px, wider padding).
- Vertical padding expands (existing `queueRowPadding.selected` scale, increased to fit).
- A third line appears: the attention reason (`attentionDriver.label` / queue context detail), styled the same as the one-liner (muted sans, `oxford/50`) with a dotted hairline above — **no burgundy**; escalation color is carried by the chip alone.
- Background tint `paperDeep/35` and the 3px oxford spine bar remain as today.
- Transitions use the existing Framer Motion layout transitions (`QUEUE_ROW_LAYOUT_TRANSITION`, `QUEUE_ROW_SELECT_TRANSITION`); `prefers-reduced-motion` keeps instant swaps.

## 3. List structure

Unchanged: flat list, queue-priority sort, existing filter logic in `WorkGrid.tsx`. Only row rendering changes.

## 4. Code shape

- `DocketCaseRow.tsx` rewritten around the new anatomy.
- New small subcomponent `components/queue/DocketMarginColumn.tsx` (chip + score), replacing `QueueVerdictLine`'s role inside the row. `QueueVerdictLine` itself is left intact for other call sites.
- `DocketRowModel` contract unchanged — it already carries `oneLiner`, `sectorStage`, `decisionVariant`, `attentionDriver`, and score via `queueContext`.
- `buildRowAriaLabel` gains the score. Keyboard handling, refs, and `WorkGrid` integration unchanged.

## 5. Local fixture mode (step 0)

Supabase is restricted until the quota resets, and UI work needs data regardless:

- `src/fixtures/startups.ts`: ~12 hand-built `Startup` objects covering every row state — escalated/needs-ruling, INVEST, PASS, MONITOR, awaiting review, undecided, LOOKUP origin with weak resolution badge, missing one-liner, missing score, long-name truncation case.
- `fetchStartups()` / `fetchStartupDetail()` in `src/api/startups.ts` return fixtures when `import.meta.env.VITE_USE_FIXTURES === '1'`.
- Activation is opt-in per dev run: `VITE_USE_FIXTURES=1 npm run dev`.

**Production safety:** Vite statically replaces `import.meta.env.VITE_USE_FIXTURES` at build time; unless the variable is set in the build environment, the condition is constant-false and the fixture import is dead-code-eliminated from the bundle. Guard rail: CI/`npm run build` must not set the variable, and the fixture module must only be imported via dynamic `import()` inside the flag check so it never ships.

## 6. Verification

- Component tests for `DocketCaseRow` updated/added: renders all chip variants, em-dash for missing score, one-liner fallback, attention line only when selected, aria-label contents.
- Visual pass on the dev server (fixture mode) across all states, selected/unselected, reduced motion, and narrow widths.
