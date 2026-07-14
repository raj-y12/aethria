# Home to Flow Chrome Stagger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the full 500 ms spine/workspace entrance from Home to Flow, then release the existing Flow queue stagger from the real chrome-animation completion event.

**Architecture:** `AppFrame` owns a transient `workspaceChromeReady` signal for bare→full chrome transitions and exposes it through `useAppFrame`. `FlowPage` forwards that signal to `WorkGrid`, whose existing variants remain hidden until ready and then run their current stagger; Dispatch motion remains unchanged.

**Tech Stack:** React 18, TypeScript, Framer Motion 10, Vitest, Vite

## Global Constraints

- Home → Flow uses the existing 500 ms `chromeTransition` and workspace `layout="position"` motion.
- The queue begins its existing `26 ms` row stagger only after `onAnimationComplete` fires.
- Existing empty-state, selected-memo, readout, and micro-interaction animations remain intact.
- Reduced motion releases Flow content immediately.
- Dispatch reciprocal motion remains unchanged.
- Do not touch unrelated concurrent working-tree edits.

---

### Task 1: Gate the existing Flow stagger on chrome completion

**Files:**
- Modify: `app-front-end/tests/flow-chrome-choreography.test.ts`
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Modify: `app-front-end/src/pages/FlowPage.tsx`
- Modify: `app-front-end/src/components/WorkGrid.tsx`
- Test: `app-front-end/tests/flow-chrome-choreography.test.ts`

**Interfaces:**
- Produces: `AppFrameContextValue.workspaceChromeReady: boolean`.
- Consumes: `WorkGridProps.entranceReady?: boolean`, defaulting to `true` for non-Flow consumers.

- [x] **Step 1: Write failing source-contract regressions**

Update the first choreography test to require:

```ts
expect(appFrameSource).toContain('workspaceChromeReady: boolean;');
expect(appFrameSource).toContain('const enteringFullChrome =');
expect(appFrameSource).toContain('onAnimationComplete={completeWorkspaceChromeEntrance}');
expect(appFrameSource).toContain('layout="position"');
expect(appFrameSource).not.toContain('chromeModeChanged');
expect(flowPageSource).toContain('workspaceChromeReady');
expect(flowPageSource).toContain('entranceReady={workspaceChromeReady}');
expect(workGridSource).toContain('entranceReady?: boolean;');
expect(workGridSource).toContain("animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}");
expect(workGridSource).toContain('staggerChildren: 0.026');
expect(workGridSource).not.toContain('autoSelectReady');
```

- [x] **Step 2: Run the focused test and verify RED**

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: FAIL because readiness is not exposed or consumed and the workspace currently disables layout motion on chrome-mode changes.

- [x] **Step 3: Add frame readiness lifecycle and context**

Add to `AppFrameContextValue`:

```ts
workspaceChromeReady: boolean;
```

Replace `chromeModeChanged` with:

```ts
const previousChrome = useRef(chrome);
const [workspaceChromeReady, setWorkspaceChromeReady] = useState(true);
const enteringFullChrome = previousChrome.current === 'bare' && chrome === 'full';
const resolvedWorkspaceChromeReady =
  reduceMotion || (!enteringFullChrome && workspaceChromeReady);
```

Replace the chrome-ref layout effect with:

```ts
useLayoutEffect(() => {
  const previous = previousChrome.current;
  previousChrome.current = chrome;

  if (reduceMotion || chrome === 'bare') {
    setWorkspaceChromeReady(true);
    return;
  }

  if (previous === 'bare') setWorkspaceChromeReady(false);
}, [chrome, reduceMotion]);

const completeWorkspaceChromeEntrance = useCallback(() => {
  setWorkspaceChromeReady(true);
}, []);
```

Add `workspaceChromeReady: resolvedWorkspaceChromeReady` to `contextValue`. Add `onAnimationComplete={completeWorkspaceChromeEntrance}` to both the mobile-chrome and spine motion elements. Restore the workspace prop:

```tsx
layout="position"
```

- [x] **Step 4: Forward readiness from Flow to WorkGrid**

Destructure readiness in `FlowPage`:

```ts
const {
  inlineDispatch,
  setPageOverlayOpen,
  openDispatch,
  openRerun,
  workspaceChromeReady,
} = useAppFrame();
```

Pass it to the existing `WorkGrid`:

```tsx
entranceReady={workspaceChromeReady}
```

- [x] **Step 5: Gate only existing WorkGrid variants**

Add to `WorkGridProps`:

```ts
entranceReady?: boolean;
```

Default it in the component arguments:

```ts
entranceReady = true,
```

Change both the populated-list and empty-state motion containers from their unconditional animate prop to:

```tsx
animate={reduceMotion || entranceReady ? 'visible' : 'hidden'}
```

Do not change the existing `staggerChildren: 0.026`, row variants, initial selection, memo reveal, or other motion components.

- [x] **Step 6: Run focused regression tests and verify GREEN**

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts src/components/__tests__/DispatchCommandBar.test.tsx
```

Expected: all selected tests pass.

- [x] **Step 7: Run complete frontend verification**

```bash
cd app-front-end && npm test
cd app-front-end && npm run lint
cd app-front-end && npm run build
```

Expected: tests, lint, and build exit successfully. Record but do not modify failures caused by unrelated concurrent edits.

- [x] **Step 8: Commit only scoped files**

```bash
git diff --check
git add app-front-end/src/components/AppFrame.tsx app-front-end/src/pages/FlowPage.tsx app-front-end/src/components/WorkGrid.tsx app-front-end/tests/flow-chrome-choreography.test.ts docs/superpowers/plans/2026-07-14-home-flow-chrome-stagger.md
git commit -m "fix(flow): sequence stagger after chrome entrance"
```

Expected: no unrelated working-tree file is staged.
