# Docket Row Redesign ("Annotated Dossier") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-line docket index rows in the Flow page with two-line "annotated dossier" rows (margin column: verdict chip + score; text block: name + one-liner), with a large "open file" selected state — plus a flag-gated local fixture mode so the UI can be built while Supabase is restricted.

**Architecture:** Frontend-only. Fixtures intercept `fetchStartups`/`fetchStartupDetail` in `src/api/startups.ts` behind `VITE_USE_FIXTURES` (dynamic import, dead-code-eliminated in prod). The row redesign rewrites `DocketCaseRow.tsx` around a new `DocketMarginColumn` subcomponent; `DocketRowModel`, `WorkGrid`, filters, and sorting are untouched.

**Tech Stack:** React + TypeScript + Tailwind + Framer Motion (existing). No test runner exists in `app-front-end` — verification is `tsc` + live visual checks against fixtures.

**Spec:** `docs/superpowers/specs/2026-06-12-docket-row-redesign-design.md`

---

### Task 1: Fixture data module

**Files:**
- Create: `app-front-end/src/fixtures/startups.ts`

- [ ] **Step 1: Create the fixture module**

The builder fills required `Startup`/`Scout` fields; each entry overrides only what defines its state. Chip-state rules (from `getDecisionBadgeVariant`): `human_resolution.decision` wins; then `partner.human_review_required === true` → escalation; then `partner.recommendation`; else `review ? 'undecided' : 'awaiting'`.

```ts
import type { Partner, Review, Startup } from '../types/startup';

/**
 * Hand-built dev fixtures covering every docket row state.
 * Served by src/api/startups.ts when VITE_USE_FIXTURES=1 (dev only —
 * the flag is statically false in production builds, so this module
 * is dead-code-eliminated).
 */

function review(overall: number, extra: Partial<Review> = {}): Review {
  return {
    market_score: overall,
    product_score: overall,
    technical_score: overall,
    execution_score: overall,
    defensibility_score: overall,
    overall_summary: 'Fixture review summary.',
    key_risks: ['Fixture risk one', 'Fixture risk two'],
    verdict: overall >= 7 ? 'STRONG' : overall >= 5 ? 'MEDIUM' : 'WEAK',
    ...extra,
  };
}

function partner(rec: Partner['recommendation'], extra: Partial<Partner> = {}): Partner {
  return {
    recommendation: rec,
    confidence: 0.8,
    decision_rationale: 'Fixture rationale.',
    next_action: 'Fixture next action.',
    ...extra,
  };
}

function fx(
  id: string,
  name: string,
  oneLine: string,
  sector: string,
  overrides: Partial<Startup> = {},
): Startup {
  return {
    id,
    scout: {
      id,
      scout_type: 'market_driven',
      name,
      one_line: oneLine,
      sector,
      why_now: 'Fixture timing thesis.',
      confidence: 0.7,
      funding_stage: 'Seed',
      location: 'Berlin',
      origin_type: 'scout',
    },
    timestamps: { discovered_at: '2026-06-01T09:00:00Z', first_seen_at: '2026-06-01T09:00:00Z' },
    ...overrides,
  };
}

export const fixtureStartups: Startup[] = [
  fx('fx-esc-vantor', 'Vantor Systems', 'Autonomous procurement agents for mid-market manufacturers', 'Industrial AI', {
    review: review(7.4, { reviewer_disagreement: true }),
    partner: partner('INVEST', { human_review_required: true }),
    unresolved_at: '2026-06-08T10:00:00Z',
    queue_reason: 'Reviewers split on defensibility — your ruling resolves it.',
  }),
  fx('fx-esc-brightloom', 'Brightloom AI', 'Demand forecasting copilot for grocery chains', 'Retail ML', {
    review: review(6.8, { reviewer_disagreement: true }),
    partner: partner('MONITOR', { human_review_required: true }),
    unresolved_at: '2026-06-10T10:00:00Z',
    queue_reason: 'Partner confidence below threshold.',
  }),
  fx('fx-invest-cobalt', 'Cobalt Health', 'Claims pre-adjudication for regional payers', 'Health fintech', {
    review: review(8.1),
    partner: partner('INVEST'),
  }),
  fx('fx-invest-helio', 'Heliograph', 'Grid-scale battery telemetry and warranty analytics', 'Energy', {
    review: review(7.9),
    partner: partner('INVEST', { human_review_required: true }),
    human_resolution: { decision: 'YES', resolved_at: '2026-06-09T12:00:00Z' },
  }),
  fx('fx-pass-ferrostack', 'Ferrostack', 'Edge GPU orchestration for robotics fleets', 'Infrastructure', {
    review: review(4.2),
    partner: partner('PASS'),
  }),
  fx('fx-pass-human', 'Quillwright', 'AI contract drafting for boutique law firms', 'Legal tech', {
    review: review(5.5),
    partner: partner('MONITOR', { human_review_required: true }),
    human_resolution: { decision: 'NO', resolved_at: '2026-06-07T12:00:00Z' },
  }),
  fx('fx-monitor-quill', 'Saltmarsh Robotics', 'Autonomous dredging for inland waterways', 'Climate robotics', {
    review: review(6.2),
    partner: partner('MONITOR'),
  }),
  fx('fx-awaiting-northbeam', 'Northbeam Optics', 'Photonic interconnects for AI datacenters', 'Semiconductors', {}),
  fx('fx-awaiting-lookup', 'Mistral Forge', 'On-prem fine-tuning appliances for banks', 'Enterprise AI', {
    scout: {
      id: 'fx-awaiting-lookup',
      scout_type: 'lookup',
      name: 'Mistral Forge',
      one_line: 'On-prem fine-tuning appliances for banks',
      sector: 'Enterprise AI',
      why_now: 'Fixture timing thesis.',
      confidence: 0.4,
      origin_type: 'lookup',
      lookup_id: 'fx-lookup-1',
      resolution_status: 'PARTIAL',
    },
  }),
  fx('fx-undecided-arcfin', 'Arcfin Labs', 'Real-time treasury hedging for marketplaces', 'Fintech', {
    review: review(7.0),
  }),
  fx(
    'fx-undecided-longname',
    'Extraordinarily Long Company Name Industries International Holdings',
    'A deliberately verbose one-line description engineered to overflow and verify truncation behaviour in narrow docket columns',
    'Stress testing',
    { review: review(6.5) },
  ),
  fx('fx-monitor-bare', 'Tidemill', '', 'Maritime SaaS', {
    review: review(6.0),
    partner: partner('MONITOR'),
  }),
];
```

- [ ] **Step 2: Type-check**

Run: `cd app-front-end && npx tsc -b --noEmit`
Expected: clean exit (0). If `Scout`/`Review`/`Partner` required fields changed, fix the builder, not the types.

- [ ] **Step 3: Commit**

```bash
git add app-front-end/src/fixtures/startups.ts
git commit -m "feat(front): dev fixture startups covering all docket row states"
```

---

### Task 2: Flag-gate the API client

**Files:**
- Modify: `app-front-end/src/api/startups.ts:9-25` (`fetchStartups`, `fetchStartupDetail`)

- [ ] **Step 1: Add the fixture gate**

At the top of `fetchStartups()` and `fetchStartupDetail()`:

```ts
export async function fetchStartups(): Promise<Startup[]> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups;
  }
  const res = await authedFetch(`${API_BASE}/api/startups`, { headers: { Accept: 'application/json' } });
  // ... unchanged
}

export async function fetchStartupDetail(startupId: string): Promise<Startup | null> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups.find((s) => s.id === startupId) ?? null;
  }
  // ... unchanged
}
```

Dynamic `import()` keeps fixtures out of the production module graph; Vite inlines `VITE_USE_FIXTURES` at build time so the branch is dead code unless the env var is set for that build.

- [ ] **Step 2: Verify in the browser**

Run dev server with `VITE_USE_FIXTURES=1` (via preview tools or `VITE_USE_FIXTURES=1 npm run dev`), sign in, open the Flow page.
Expected: 12 fixture companies in the docket; escalated rows sorted toward the top; no `/api/startups` request for the list (check network).

- [ ] **Step 3: Verify production build drops fixtures**

Run: `cd app-front-end && npm run build && ! grep -ri "Vantor Systems" dist/assets/`
Expected: build succeeds, grep finds nothing (exit 0 for the negated grep).

- [ ] **Step 4: Commit**

```bash
git add app-front-end/src/api/startups.ts
git commit -m "feat(front): VITE_USE_FIXTURES gate serves dev fixtures from the API client"
```

---

### Task 3: DocketMarginColumn component

**Files:**
- Create: `app-front-end/src/components/queue/DocketMarginColumn.tsx`

- [ ] **Step 1: Create the component**

Reuses `DecisionBadge` (chip size is unified product-wide — selection prominence comes from score/name/padding, not chip scale). Escalation copy is "NEEDS RULING" per the design, via the label override.

```tsx
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import DecisionBadge from '../DecisionBadge';

interface DocketMarginColumnProps {
  variant: DecisionBadgeVariant;
  score: number;
  prominent: boolean;
}

/** Fixed left margin column of a docket row: verdict chip over configured score. */
export default function DocketMarginColumn({ variant, score, prominent }: DocketMarginColumnProps) {
  const hasScore = Number.isFinite(score) && score > 0;
  return (
    <div className="flex w-[96px] shrink-0 flex-col items-end gap-1.5 border-r-2 border-oxford/10 pr-3.5 text-right">
      <DecisionBadge variant={variant} label={variant === 'escalation' ? 'NEEDS RULING' : undefined} />
      <span
        className={`tabular-nums transition-all duration-150 ${
          prominent ? 'text-[24px] leading-none text-oxford' : 'text-[15px] leading-none text-oxford/45'
        }`}
        aria-hidden={!hasScore}
      >
        {hasScore ? score.toFixed(1) : '—'}
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd app-front-end && npx tsc -b --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add app-front-end/src/components/queue/DocketMarginColumn.tsx
git commit -m "feat(front): DocketMarginColumn — verdict chip + score margin"
```

---

### Task 4: Rewrite DocketCaseRow

**Files:**
- Modify: `app-front-end/src/components/queue/DocketCaseRow.tsx` (full rewrite of the body; props/ref contract unchanged)
- Modify: `app-front-end/src/components/queue/queueRowShared.ts:48-61` (`buildRowAriaLabel`)

- [ ] **Step 1: Rewrite the row**

Keeps: `forwardRef` button, spine bar, `paperDeep/35` selected tint, padding animation via Framer Motion, reduced-motion behavior, focus ring. Removes: `displayIndex` rendering and `QueueVerdictLine` usage. Adds: margin column, two-line text block, selected-only attention line.

```tsx
import { forwardRef } from 'react';
import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../../hooks';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import DocketMarginColumn from './DocketMarginColumn';
import { buildRowAriaLabel, type DocketRowModel } from './queueRowShared';
import {
  QUEUE_ROW_LAYOUT_TRANSITION,
  QUEUE_ROW_SELECT_TRANSITION,
} from './queueRowMotion';
import { queueRowPadding } from '../../design-system/density';

interface DocketCaseRowProps {
  model: DocketRowModel;
  isSelected: boolean;
  rowIndex?: number;
  onClick: () => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  /** @deprecated Queue uses monochrome type; kept for call-site compatibility. */
  badges?: VerdictBadgeConfig[];
}

/**
 * Annotated dossier row: a fixed margin column (verdict chip + score) against
 * a two-line text block (name, one-liner · sector). Selection is the "open
 * file" — name and score step up in size and ink, and the attention reason
 * appears as a third line in the same muted voice as the one-liner.
 */
const DocketCaseRow = forwardRef<HTMLButtonElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const { startup, decisionVariant, queueContext, attentionDriver } = model;

  const spineVisible = isSelected;
  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;

  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected + 4;

  const metaLine = [model.oneLiner, model.sectorStage].filter(Boolean).join(' · ');
  const attentionLine = attentionDriver.detail ?? attentionDriver.label;

  return (
    <motion.button
      ref={ref}
      type="button"
      layout={!reduceMotion}
      transition={layoutTransition}
      aria-pressed={isSelected}
      aria-label={buildRowAriaLabel(model, isSelected)}
      onClick={onClick}
      onKeyDown={onKeyDown}
      initial={false}
      animate={{
        paddingTop: isSelected ? selectedPadding : ambientPadding,
        paddingBottom: isSelected ? selectedPadding : ambientPadding,
      }}
      className={`group relative block w-full min-w-0 cursor-pointer border-0 bg-transparent px-phi-0 text-left font-sans focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
        isSelected ? 'bg-paperDeep/35' : ''
      }`}
    >
      <motion.span
        className="absolute left-0 top-0 bottom-0 block"
        aria-hidden
        initial={false}
        animate={{
          top: isSelected ? 10 : 9,
          bottom: isSelected ? 10 : 9,
          width: spineVisible ? 3 : 0,
          backgroundColor: spineVisible ? '#001433' : 'transparent',
          opacity: spineVisible ? 1 : 0,
        }}
        transition={selectTransition}
      />

      <div className="flex items-start gap-phi-3">
        <DocketMarginColumn
          variant={decisionVariant}
          score={queueContext.configuredScore}
          prominent={isSelected}
        />

        <div className="min-w-0 flex-1">
          <span
            className={`block min-w-0 truncate font-sans transition-all duration-150 ${
              isSelected
                ? 'text-[22px] font-semibold leading-[1.2] tracking-[-0.015em] text-oxford'
                : 'text-[clamp(14px,1.15vw,16px)] font-normal leading-[1.3] tracking-[-0.01em] text-oxford/55 group-hover:text-oxford/80'
            }`}
          >
            {startup.scout.name}
          </span>
          {metaLine ? (
            <span
              className={`mt-1 block min-w-0 truncate text-[12px] leading-[1.45] ${
                isSelected ? 'text-oxford/[0.62]' : 'text-oxford/50'
              }`}
            >
              {metaLine}
            </span>
          ) : null}
          {isSelected && attentionLine ? (
            <span className="mt-2 block border-t border-dotted border-oxford/15 pt-2 text-[12px] leading-[1.45] text-oxford/50">
              {attentionLine}
            </span>
          ) : null}
        </div>
      </div>
    </motion.button>
  );
});

export default DocketCaseRow;
```

- [ ] **Step 2: Add score to the aria label**

In `queueRowShared.ts`, inside `buildRowAriaLabel`, after the `rec` line:

```ts
const score = queueContext.configuredScore;
const parts = [
  startup.scout.name,
  startup.scout.location?.trim(),
  model.sectorStage || 'Unknown sector',
  attentionDriver.label,
  Number.isFinite(score) && score > 0 ? `Score ${score.toFixed(1)}` : '',
  rec ? `Recommendation ${rec}` : '',
  isSelected ? 'Selected case' : '',
  'Press Enter to open memo',
].filter(Boolean);
```

- [ ] **Step 3: Type-check and check for orphaned imports**

Run: `cd app-front-end && npx tsc -b --noEmit`
Expected: clean. If `WorkGrid.tsx` imports `QueueVerdictLine` or motion constants only used by the old row, leave them — `QueueVerdictLine` stays for other call sites; only remove imports that `tsc`/lint flag as unused **within DocketCaseRow.tsx**.

- [ ] **Step 4: Commit**

```bash
git add app-front-end/src/components/queue/DocketCaseRow.tsx app-front-end/src/components/queue/queueRowShared.ts
git commit -m "feat(front): annotated dossier docket rows with open-file selection"
```

---

### Task 5: Visual verification and polish pass

**Files:** none new — fixes land in the files above.

- [ ] **Step 1: Run the dev server in fixture mode and verify each state**

With `VITE_USE_FIXTURES=1`, on the Flow page verify against the fixture set:
- All six chip variants render (INVEST, PASS, MONITOR, AWAITING REVIEW, PENDING DECISION, NEEDS RULING).
- Unscored rows (`fx-awaiting-northbeam`, `fx-awaiting-lookup`) show the em-dash.
- `fx-monitor-bare` (no one-liner) shows sector only — no stray "·".
- The long-name fixture truncates on one line at narrow widths (resize to ~1024px).
- Selecting a row: name 22px full ink, score 24px, padding expands, attention line appears with dotted rule; deselecting reverts.
- Keyboard: arrow/enter behavior unchanged; focus ring visible.
- Reduced motion (OS setting or devtools emulation): state swaps are instant, no layout animation.

- [ ] **Step 2: Screenshot evidence**

Capture the docket with one selected escalated row and several ambient rows; share with the user.

- [ ] **Step 3: Fix anything off, re-verify, commit**

```bash
git add -A app-front-end/src
git commit -m "polish(front): docket row spacing/truncation fixes from visual pass"
```

(Skip the commit if the visual pass needed no changes.)
