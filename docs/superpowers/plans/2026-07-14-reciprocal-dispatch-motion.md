# Reciprocal Dispatch Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Dispatch close with the exact reverse of its opening choreography while restoring the stable Home → Flow row stagger.

**Architecture:** `dispatch.commandBarOpen` directly controls both Dispatch presence and spine/mobile-chrome visibility, allowing Framer Motion to retain the exiting Dispatch surface while chrome returns concurrently. `AppFrame` detects only bare↔full `chrome` prop changes and disables workspace position layout animation for that render, leaving Dispatch transitions synchronized.

**Tech Stack:** React 18, TypeScript, Framer Motion 10, Vitest, Vite

## Global Constraints

- Dispatch enter is `opacity: 0, y: 10` to `opacity: 1, y: 0`; exit is the exact reverse.
- Spine, mobile chrome, workspace, and Dispatch start their reverse motion concurrently on close.
- Each element uses the same duration and easing in both directions.
- Home → Flow must not inherit Dispatch workspace layout animation.
- Keep reduced-motion behavior and Dispatch internals unchanged.
- Do not touch unrelated concurrent working-tree edits.

---

## File Map

- Modify `app-front-end/tests/flow-chrome-choreography.test.ts`: assert reciprocal Dispatch motion, concurrent chrome return, and bare↔full layout isolation.
- Modify `app-front-end/src/components/AppFrame.tsx`: remove serialized Dispatch exit state, reverse the exit path, and scope layout animation away from Home → Flow.

### Task 1: Correct frame choreography test-first

**Files:**
- Modify: `app-front-end/tests/flow-chrome-choreography.test.ts`
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Test: `app-front-end/tests/flow-chrome-choreography.test.ts`

**Interfaces:**
- Consumes: `chrome`, `dispatch.commandBarOpen`, `AnimatePresence`, `chromeTransition`, and the existing Dispatch motion surface.
- Produces: `chromeModeChanged: boolean`, used only to disable workspace layout animation during bare↔full route changes.

- [x] **Step 1: Replace the serialized-motion regression expectations**

```ts
it('uses reciprocal Dispatch motion without disturbing Home to Flow geometry', () => {
  expect(appFrameSource).toContain('const chromeModeChanged = previousChrome.current !== chrome;');
  expect(appFrameSource).toContain("layout={chromeModeChanged ? false : 'position'}");
  expect(appFrameSource).toContain('const showSpine = !bareChrome && !dispatch.commandBarOpen;');
  expect(appFrameSource).toContain('const showMobileChrome = !isDesktop && !bareChrome && !dispatch.commandBarOpen;');
  expect(appFrameSource).toContain("exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 10 }}");
  expect(appFrameSource).not.toContain('dispatchExitPending');
  expect(appFrameSource).not.toContain('dispatchTransitionActive');
  expect(appFrameSource).not.toContain('onExitComplete={completeDispatchExit}');
});
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: FAIL because the current frame serializes chrome behind `dispatchExitPending`, always enables position layout animation, and exits Dispatch toward `y: -10`.

- [x] **Step 3: Replace Dispatch exit serialization with chrome-mode detection**

Near the other frame-level state, add:

```ts
const previousChrome = useRef(chrome);
const chromeModeChanged = previousChrome.current !== chrome;

useLayoutEffect(() => {
  previousChrome.current = chrome;
}, [chrome]);
```

Remove `previousDispatchOpen`, `dispatchExitPending`, `dispatchClosing`, `dispatchTransitionActive`, and `completeDispatchExit`.

- [x] **Step 4: Make chrome visibility follow logical Dispatch state immediately**

```ts
const showSpine = !bareChrome && !dispatch.commandBarOpen;
const showMobileChrome = !isDesktop && !bareChrome && !dispatch.commandBarOpen;
```

Framer Motion retains the removed Dispatch child for its exit, so this causes the spine/mobile chrome to mount and animate at the same moment that Dispatch begins exiting.

- [x] **Step 5: Scope workspace layout motion and reverse the Dispatch path**

```tsx
<motion.main
  layout={chromeModeChanged ? false : 'position'}
  transition={chromeTransition}
  className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-paper"
>
```

Change the presence surface to remove its exit-complete callback and use the reciprocal exit:

```tsx
<AnimatePresence initial={false}>
  {dispatch.commandBarOpen ? (
    <motion.div
      key="dispatch-takeover"
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 10 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
      })}
      className="absolute inset-0 z-20"
    >
      <DispatchCommandBar
        open
        onClose={dispatch.closeCommandBar}
        input={dispatch.input}
        setInput={dispatch.setInput}
        onSubmit={() => void dispatch.submit()}
        onCancel={dispatch.cancel}
        isBusy={dispatch.busy}
        message={dispatch.message}
        onClearMessage={dispatch.clearMessage}
        lookupPhase={dispatch.phaseLabel}
        progress={dispatch.progress}
        chips={dispatch.chips}
        onFocusChip={dispatch.focusChip}
        failure={dispatch.failure}
        onRetry={dispatch.dismissFailure}
        candidates={dispatch.candidates}
        needsWebsite={dispatch.needsWebsite}
        onPickCandidate={dispatch.pickCandidate}
        onRefineWebsite={dispatch.refineWithWebsite}
        rerun={
          dispatch.rerunTarget
            ? {
                name: dispatch.rerunTarget.scout.name,
                sector: dispatch.rerunTarget.scout.sector ?? null,
              }
            : null
        }
        onSubmitRerun={(context) => void dispatch.submitRerun(context)}
        result={
          dispatch.lookupDecided && dispatch.snapshotProps ? (
            <LookupResultSnapshot
              {...dispatch.snapshotProps}
              onOpenMemo={dispatch.openLookupMemo}
              className="w-full"
            />
          ) : null
        }
      />
    </motion.div>
  ) : null}
</AnimatePresence>
```

- [x] **Step 6: Run the focused test and verify GREEN**

Run:

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: 3 tests pass.

- [x] **Step 7: Run scoped and full frontend verification**

Run:

```bash
cd app-front-end && npm test -- src/components/__tests__/DispatchCommandBar.test.tsx tests/flow-chrome-choreography.test.ts
cd app-front-end && npm test
cd app-front-end && npm run lint
cd app-front-end && npm run build
```

Expected: scoped tests pass; the full suite, lint, and build exit successfully. If unrelated concurrent edits cause a failure, record the exact failing file and leave those edits untouched.

- [x] **Step 8: Review and commit only scoped files**

```bash
git diff --check
git add app-front-end/src/components/AppFrame.tsx app-front-end/tests/flow-chrome-choreography.test.ts docs/superpowers/plans/2026-07-14-reciprocal-dispatch-motion.md
git commit -m "fix(front): make dispatch motion reciprocal"
```

Expected: the commit excludes every unrelated concurrent working-tree edit.
