# Left rail density reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the desktop left rail's perceived density while preserving the current editorial styling, justified vertical spacing, and existing lookup/pipeline behavior.

**Architecture:** Keep the current left-rail layout in `MainLayout`, but simplify each section's internal composition. Convert the pipeline block to a split summary, convert desktop dispatch to a status-first idle shell that expands on intent or active state, and collapse mandate tags into one inline thesis line derived from existing thesis sources.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind utility classes, Framer Motion, existing Aethria design tokens and rail typography helpers

---

## File map

- Modify: `src/components/MainLayout.tsx`
  - Replace the current stacked pipeline presentation with the split-summary layout
  - Replace desktop mandate chip rendering with a single summary line
  - Pass the right props into desktop dispatch for the new status-first idle behavior
- Modify: `src/components/AgentDispatch.tsx`
  - Add an embedded compact idle presentation for desktop rail use
  - Preserve active lookup behavior and existing drawer behavior
- Create: `src/lib/railSummaries.ts`
  - Hold pure formatting helpers for the mandate summary line so `MainLayout` does not grow more string-shaping logic

## Constraints for execution

- Do not touch mobile-only rail summaries in `MainLayout`
- Do not change API contracts or lookup behavior
- Do not add new dependencies or a new test runner for this work
- Use `npm run lint`, `npm run build`, and browser verification as the validation stack for this frontend refactor

### Task 1: Add pure rail summary helpers

**Files:**
- Create: `src/lib/railSummaries.ts`
- Modify: `src/components/MainLayout.tsx`

- [ ] **Step 1: Create the mandate summary helper file**

Add `src/lib/railSummaries.ts`:

```ts
type MandateSummaryInput = {
  stages: string[];
  geos: string[];
  sectors: string[];
};

function pickFirst(items: string[]): string | null {
  const first = items.find((item) => item.trim().length > 0);
  return first ? first.trim() : null;
}

function dedupe(values: Array<string | null>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const value of values) {
    if (!value) continue;
    if (seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }

  return result;
}

export function buildMandateSummaryLine({
  stages,
  geos,
  sectors,
}: MandateSummaryInput): string | null {
  const ordered = dedupe([
    pickFirst(stages),
    pickFirst(geos),
    pickFirst(sectors),
  ]);

  return ordered.length > 0 ? ordered.join(' · ') : null;
}
```

- [ ] **Step 2: Wire the helper into `MainLayout`**

Update the imports near the top of `src/components/MainLayout.tsx`:

```ts
import { buildMandateSummaryLine } from '../lib/railSummaries';
```

Replace the desktop-rail-only tag-list dependency with a derived summary line near the current `thesisTagList` block:

```ts
  const mandateSummaryLine = useMemo(
    () =>
      buildMandateSummaryLine({
        stages: thesisTags.stages,
        geos: thesisTags.geos,
        sectors: thesisTags.sectors,
      }),
    [thesisTags.geos, thesisTags.sectors, thesisTags.stages],
  );
```

- [ ] **Step 3: Run lint to catch type or import mistakes**

Run:

```bash
npm run lint
```

Expected:

- Lint completes without new errors from `MainLayout.tsx` or `railSummaries.ts`

- [ ] **Step 4: Commit the helper extraction**

Run:

```bash
git add src/lib/railSummaries.ts src/components/MainLayout.tsx
git commit -m "refactor: extract rail mandate summary helper"
```

### Task 2: Refactor the pipeline overview into the split summary

**Files:**
- Modify: `src/components/MainLayout.tsx`

- [ ] **Step 1: Replace the current segmented `SystemTelemetryRail` markup**

Inside `SystemTelemetryRail` in `src/components/MainLayout.tsx`, replace the current `<article>` body with a quieter split-summary structure:

```tsx
  return (
    <article className="flex min-w-0 flex-col border border-oxford/[0.08]" aria-label="Pipeline overview">
      <div className="relative px-phi-4 py-phi-4">
        <div className="flex items-center justify-between gap-phi-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-oxford/40">
            Pipeline
          </p>

          <span className={`inline-flex shrink-0 items-center gap-phi-2 font-mono text-[10px] uppercase tracking-[0.10em] ${statusTone}`}>
            <span className={`h-1.5 w-1.5 shrink-0 rounded-none ${statusDot}`} aria-hidden />
            {pipelineLoopAlive && !pipelineHealthIssue ? 'Live' : statusLabel}
          </span>
        </div>

        <div className="mt-phi-4 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-phi-4">
          <div className="min-w-0">
            <p
              className={`font-mono text-[clamp(2rem,4vw,3rem)] font-bold leading-none tracking-[-0.04em] tabular-nums ${
                hasEscalations ? 'text-escalation' : 'text-oxford'
              }`}
              aria-live="polite"
            >
              {primaryValue.toLocaleString()}
            </p>
            <p className="mt-phi-2 font-mono text-[10px] uppercase tracking-[0.10em] text-oxford/42">
              {primaryLabel}
            </p>
          </div>

          <dl className="grid min-w-[7.5rem] gap-phi-2 text-right">
            <div className="grid grid-cols-[auto_auto] items-baseline justify-end gap-x-phi-3">
              <dt className="font-mono text-[10px] uppercase tracking-[0.10em] text-oxford/38">Total</dt>
              <dd className="font-mono text-[14px] font-semibold tabular-nums text-oxford">{totalCount.toLocaleString()}</dd>
            </div>
            <div className="grid grid-cols-[auto_auto] items-baseline justify-end gap-x-phi-3">
              <dt className="font-mono text-[10px] uppercase tracking-[0.10em] text-oxford/38">Decided</dt>
              <dd className="font-mono text-[14px] font-semibold tabular-nums text-oxford">{decidedCount.toLocaleString()}</dd>
            </div>
          </dl>
        </div>

        {pipelineHealthIssue ? (
          <div className="mt-phi-3 flex items-center justify-between gap-phi-3 border-t border-oxford/[0.075] pt-phi-3">
            <p className="min-w-0 truncate font-mono text-[9px] uppercase tracking-[0.08em] text-escalation/75">
              {stageSummary}
            </p>
            <button
              type="button"
              onClick={onToggleIssueHelp}
              className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-none border border-escalation/40 font-mono text-[10px] leading-none text-escalation hover:text-escalation/75 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-escalation/40"
              aria-label="Pipeline issue details"
              aria-expanded={showIssueHelp}
            >
              ?
            </button>
          </div>
        ) : (
          <p className="mt-phi-3 border-t border-oxford/[0.075] pt-phi-3 font-mono text-[9px] uppercase tracking-[0.08em] text-oxford/32">
            {stageSummary}
          </p>
        )}

        {showIssueHelp && pipelineHealthIssue ? (
          <span className="absolute right-phi-4 top-[calc(100%+8px)] z-20 w-56 border border-field-border bg-paper p-phi-3 text-left normal-case tracking-normal type-label-section leading-phi text-oxford shadow-sm">
            Pipeline has a problem and may not process updates right now.
            <button
              type="button"
              onClick={onOpenSettings}
              className="mt-phi-2 block type-meta text-oxford/35 hover:text-oxford btn-interaction"
            >
              Open settings →
            </button>
          </span>
        ) : null}
      </div>
    </article>
  );
```

- [ ] **Step 2: Remove obsolete sub-panel classes and labels**

Delete the old:

- `Pipeline overview` header row
- separate `Pipeline status` strip
- separate `Total / Decided` footer grid that reads as an extra panel

Keep:

- `primaryLabel`
- `primaryValue`
- `statusLabel`
- `stageSummary`
- issue help behavior

- [ ] **Step 3: Build the app to verify the rail still compiles cleanly**

Run:

```bash
npm run build
```

Expected:

- Vite build completes successfully
- No JSX or type errors from `SystemTelemetryRail`

- [ ] **Step 4: Commit the pipeline refactor**

Run:

```bash
git add src/components/MainLayout.tsx
git commit -m "refactor: simplify pipeline rail summary"
```

### Task 3: Convert desktop dispatch to status-first idle behavior

**Files:**
- Modify: `src/components/AgentDispatch.tsx`
- Modify: `src/components/MainLayout.tsx`

- [ ] **Step 1: Add an explicit compact embedded mode to `AgentDispatch` props**

Update the prop type in `src/components/AgentDispatch.tsx`:

```ts
interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isBusy: boolean;
  message: string | null;
  onClearMessage?: () => void;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
  alwaysOpen?: boolean;
  embeddedIdleMode?: 'full' | 'statusFirst';
}
```

- [ ] **Step 2: Add a compact embedded idle shell**

Inside `AgentDispatch`, derive the mode and idle visibility:

```ts
  const mode = embeddedIdleMode ?? 'full';
  const lookupMessage = message ? formatLookupMessage(message) : null;
  const isActive = isBusy || !!lookupMessage;
  const showCompactEmbeddedIdle = alwaysOpen && mode === 'statusFirst' && !isActive && !isExpanded;
```

Add a compact renderer above the existing `alwaysOpen` branch:

```tsx
function EmbeddedIdleSummary({
  onOpen,
}: {
  onOpen: () => void;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-phi-3">
        <span className={railEditorial.label}>Dispatch</span>
        <span className={`${railEditorial.meta} text-oxford/42`}>Idle</span>
      </div>
      <p className={`${railEditorial.body} -mt-phi-1 text-oxford/58`}>
        No lookup in flight.
      </p>
      <button
        type="button"
        onClick={onOpen}
        className="mt-phi-2 inline-flex items-center gap-phi-2 font-mono text-[11px] uppercase tracking-[0.08em] text-oxford/55 hover:text-oxford btn-interaction"
      >
        Run lookup <span aria-hidden>→</span>
      </button>
    </div>
  );
}
```

Then branch the render:

```tsx
      {alwaysOpen ? (
        showCompactEmbeddedIdle ? (
          <EmbeddedIdleSummary onOpen={() => setExpanded(true)} />
        ) : (
          <div className="min-w-0">
            <DispatchPanelBody
              inputRef={inputRef}
              input={input}
              setInput={setInput}
              onSubmit={onSubmit}
              onCancel={onCancel}
              isBusy={isBusy}
              lookupMessage={lookupMessage}
              onClearMessage={onClearMessage}
              lookupPhase={lookupPhase}
              variant="embedded"
            />
          </div>
        )
      ) : (
```

- [ ] **Step 3: Make expansion state work for desktop embedded mode**

Adjust the effects in `AgentDispatch` so the embedded compact mode expands on intent and auto-expands for activity:

```ts
  useEffect(() => {
    if (isExpanded && inputRef.current) inputRef.current.focus();
  }, [isExpanded]);

  useEffect(() => {
    if (alwaysOpen && mode === 'full') {
      setExpanded(true);
      return;
    }

    if (isBusy || message) setExpanded(true);
  }, [alwaysOpen, isBusy, message, mode]);
```

This preserves:

- always-open full mode for mobile / existing behavior where needed
- compact idle state for the desktop rail
- active-state auto expansion

- [ ] **Step 4: Pass the compact mode from the desktop rail call site**

In the desktop left rail `AgentDispatch` usage inside `MainLayout.tsx`, add:

```tsx
<AgentDispatch
  input={lookupInput}
  setInput={setLookupInput}
  onSubmit={() => void handleLookupSubmit()}
  onCancel={handleLookupCancel}
  isBusy={lookupWorking}
  message={lookupMessage}
  onClearMessage={() => setLookupMessage(null)}
  lookupPhase={lookupPhaseLabel}
  alwaysOpen
  embeddedIdleMode="statusFirst"
/>
```

Do not change the mobile/header `AgentDispatch` invocation.

- [ ] **Step 5: Run lint to verify state and prop changes**

Run:

```bash
npm run lint
```

Expected:

- No prop-type or hook dependency errors
- No unused-branch or unreachable-code errors in `AgentDispatch.tsx`

- [ ] **Step 6: Commit the dispatch refactor**

Run:

```bash
git add src/components/AgentDispatch.tsx src/components/MainLayout.tsx
git commit -m "refactor: add compact desktop dispatch state"
```

### Task 4: Replace desktop mandate chips with the inline thesis line

**Files:**
- Modify: `src/components/MainLayout.tsx`

- [ ] **Step 1: Replace the desktop mandate chip wall**

In the desktop mandate section of `src/components/MainLayout.tsx`, replace:

```tsx
                  {hasThesisTags && (
                    <div className="mt-phi-3 flex max-h-[4.9rem] flex-wrap gap-phi-2 overflow-hidden">
                      {thesisTagList.map((t, i) => (
                        <span
                          key={`mandate-${i}-${t}`}
                          className={`bg-registerTint px-phi-2 py-phi-1 ${railEditorial.meta} text-oxford/45`}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
```

with:

```tsx
                  {mandateSummaryLine ? (
                    <p className={`mt-phi-2 ${railEditorial.meta} text-oxford/50 uppercase`}>
                      {mandateSummaryLine}
                    </p>
                  ) : null}
```

- [ ] **Step 2: Slightly de-emphasize the live marker if it competes with the fund name**

If the current live marker still feels too loud after the chip removal, reduce it without deleting it:

```tsx
                        <span
                          className={`${railEditorial.meta} uppercase text-oxford/32`}
                        >
                          Live
                        </span>
```

Keep the signal dot only if it still balances visually with the quieter text block.

- [ ] **Step 3: Leave the mobile mandate card untouched unless the desktop-only change forces a shared helper reuse**

Only reuse `mandateSummaryLine` on mobile if it falls out cleanly. Do not let the desktop rail refactor spill into mobile presentation work.

- [ ] **Step 4: Build to verify the mandate section still compiles**

Run:

```bash
npm run build
```

Expected:

- Build passes
- No remaining references to desktop-only `thesisTagList` where it is no longer needed

- [ ] **Step 5: Commit the mandate presentation change**

Run:

```bash
git add src/components/MainLayout.tsx
git commit -m "refactor: simplify desktop mandate summary"
```

### Task 5: Visual verification and cleanup

**Files:**
- Modify: `src/components/MainLayout.tsx`
- Modify: `src/components/AgentDispatch.tsx`
- Create if needed: no new files

- [ ] **Step 1: Start the dev server with the required env available**

Run:

```bash
npm run dev -- --host 127.0.0.1
```

Expected:

- Vite serves the app locally
- If the app still requires `VITE_CLERK_PUBLISHABLE_KEY`, provide the local env before manual verification

- [ ] **Step 2: Verify the desktop rail visually in the browser**

Check these states manually:

- normal desktop width
- narrower desktop width
- pipeline issue state if reproducible
- lookup idle state
- lookup active state
- long mandate summary

Acceptance checklist:

- pipeline reads as one block, not stacked sub-panels
- dispatch no longer dominates the rail when idle
- mandate no longer renders as a tag wall
- overall rail still preserves the editorial tone and justified spacing

- [ ] **Step 3: Run the final validation commands**

Run:

```bash
npm run lint
npm run build
```

Expected:

- Both commands succeed

- [ ] **Step 4: Commit final polish**

Run:

```bash
git add src/components/MainLayout.tsx src/components/AgentDispatch.tsx src/lib/railSummaries.ts
git commit -m "feat: reduce left rail density"
```

## Self-review

- Spec coverage check:
  - quiet stack preserved: covered in Tasks 2, 3, and 4
  - pipeline split summary: covered in Task 2
  - dispatch status-first: covered in Task 3
  - mandate inline thesis line: covered in Task 4
  - validation requirements: covered in Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or "implement later" text remains
  - every file path and command is explicit
- Type consistency:
  - `mandateSummaryLine` is the single desktop summary value
  - `embeddedIdleMode` controls compact desktop dispatch behavior

