# Explicit Flow Memo Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the Flow memo closed on ordinary entry and open it only from a row click or explicit memo deep link.

**Architecture:** `FlowPage.selectedStartup` remains the sole memo-open state. Remove the unused first-row auto-selection contract from `WorkGrid`; retain the existing row-click handler and `?open=<id>` effect, so the current memo reveal runs only after an explicit selection.

**Tech Stack:** React 18, TypeScript, Framer Motion 10, Vitest, Vite

## Global Constraints

- Ordinary Flow entry leaves `selectedStartup` null.
- Row clicks and `?open=<id>` deep links continue to open the memo.
- Do not add a timer or delayed automatic selection.
- Preserve Home → Flow chrome timing, WorkGrid stagger, and memo reveal motion.
- Do not touch unrelated concurrent working-tree edits.

---

### Task 1: Remove automatic memo selection test-first

**Files:**
- Modify: `app-front-end/tests/flow-chrome-choreography.test.ts`
- Modify: `app-front-end/src/pages/FlowPage.tsx`
- Modify: `app-front-end/src/components/WorkGrid.tsx`
- Test: `app-front-end/tests/flow-chrome-choreography.test.ts`

**Interfaces:**
- Removes: `WorkGridProps.autoSelectFirst?: boolean` and `WorkGridProps.onAutoSelect?: (startup: Startup) => void`.
- Preserves: `onStartupClick(startup)` and the existing `searchParams.get('open')` selection path.

- [x] **Step 1: Replace the auto-selection regression with explicit-selection requirements**

```ts
it('keeps the memo closed until a row or deep link explicitly selects a deal', () => {
  expect(flowPageSource).toContain('const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);');
  expect(flowPageSource).toContain("const openId = searchParams.get('open');");
  expect(flowPageSource).toContain('onStartupClick={handleStartupClick}');
  expect(flowPageSource).not.toContain('autoSelectFirst=');
  expect(flowPageSource).not.toContain('onAutoSelect=');
  expect(flowPageSource).not.toContain('handleAutoSelect');
  expect(workGridSource).not.toContain('autoSelectFirst');
  expect(workGridSource).not.toContain('onAutoSelect');
  expect(workGridSource).not.toContain('top of the current view takes the canvas');
});
```

- [x] **Step 2: Run the focused test and verify RED**

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: FAIL because Flow still passes the desktop auto-selection props and WorkGrid still selects the first visible row in a layout effect.

- [x] **Step 3: Remove Flow's automatic-selection wiring**

Delete this callback from `FlowPage`:

```ts
const handleAutoSelect = useCallback((startup: Startup) => {
  setSelectedStartup(startup);
}, []);
```

Remove these props from `WorkGrid`:

```tsx
autoSelectFirst={isDesktop}
onAutoSelect={handleAutoSelect}
```

Keep `handleStartupClick`, the `?open=<id>` effect, and the existing memo motion element unchanged.

- [x] **Step 4: Remove WorkGrid's automatic-selection API and effect**

Remove these interface properties:

```ts
autoSelectFirst?: boolean;
onAutoSelect?: (startup: Startup) => void;
```

Remove `autoSelectFirst` and `onAutoSelect` from the component arguments. Delete the layout effect that calls `onAutoSelect?.(first)`. If no other layout effect remains, remove `useLayoutEffect` from the React import.

- [x] **Step 5: Run focused tests and verify GREEN**

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts src/components/__tests__/DispatchCommandBar.test.tsx
```

Expected: all selected tests pass.

- [x] **Step 6: Run complete frontend verification**

```bash
cd app-front-end && npm test
cd app-front-end && npm run lint
cd app-front-end && npm run build
```

Expected: tests, lint, and build exit successfully. Record but do not modify failures from unrelated concurrent edits.

- [x] **Step 7: Commit only scoped files**

```bash
git diff --check
git add app-front-end/src/pages/FlowPage.tsx app-front-end/src/components/WorkGrid.tsx app-front-end/tests/flow-chrome-choreography.test.ts docs/superpowers/plans/2026-07-14-explicit-flow-memo-selection.md
git commit -m "fix(flow): require explicit memo selection"
```

Expected: no unrelated working-tree file is staged.
