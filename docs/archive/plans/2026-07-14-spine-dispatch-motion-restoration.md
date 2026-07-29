# Spine and Dispatch Motion Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore synchronized spine/workspace motion and give the Dispatch takeover a sequenced fade-and-lift exit.

**Architecture:** `AppFrame` remains the owner of application-chrome choreography. It tracks the brief Dispatch exit lifecycle, renders the takeover through `AnimatePresence`, delays spine/mobile-chrome return until exit completion, and restores position-only layout animation on the workspace.

**Tech Stack:** React 18, TypeScript, Framer Motion 10, Vitest, Vite

## Global Constraints

- Keep `dispatch.commandBarOpen` as the logical open-state source of truth.
- Do not change Dispatch's internal lookup views, progress stages, result presentation, or focus behavior.
- Use the existing Framer Motion dependency, design-system motion tokens, and reduced-motion helper.
- Do not change spine dimensions, navigation, typography, or global motion tokens.
- Preserve the unrelated untracked critique file in `.impeccable/critique/`.

---

## File Map

- Modify `app-front-end/tests/flow-chrome-choreography.test.ts`: encode the restored workspace animation, Dispatch presence/exit, and chrome sequencing as regression expectations.
- Modify `app-front-end/src/components/AppFrame.tsx`: own Dispatch exit state, presence animation, and delayed chrome return; restore workspace position layout motion.

### Task 1: Lock the restored frame choreography with a failing regression test

**Files:**
- Modify: `app-front-end/tests/flow-chrome-choreography.test.ts`
- Test: `app-front-end/tests/flow-chrome-choreography.test.ts`

**Interfaces:**
- Consumes: the source-level choreography contract already used by this regression file.
- Produces: assertions that require `layout="position"`, `dispatchTransitionActive`, `AnimatePresence.onExitComplete`, and the Dispatch `y: -10` exit state.

- [x] **Step 1: Replace the obsolete final-geometry assertion with the restored motion contract**

```ts
it('restores synchronized workspace motion and sequences chrome after Dispatch exits', () => {
  expect(appFrameSource).toContain('layout="position"');
  expect(appFrameSource).toContain('transition={chromeTransition}');
  expect(appFrameSource).toContain('dispatchTransitionActive');
  expect(appFrameSource).toContain('onExitComplete={completeDispatchExit}');
  expect(appFrameSource).toContain("exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -10 }}");
});
```

- [x] **Step 2: Run the focused test and confirm the regression is red**

Run:

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: FAIL because `AppFrame.tsx` currently omits `layout="position"`, Dispatch presence exit handling, and `dispatchTransitionActive`.

### Task 2: Implement frame-owned Dispatch exit sequencing and restore spine motion

**Files:**
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Test: `app-front-end/tests/flow-chrome-choreography.test.ts`

**Interfaces:**
- Consumes: `dispatch.commandBarOpen`, `chromeTransition`, `transitionOrReduced`, `tokens.motion`, and the existing `DispatchCommandBar` props.
- Produces: `dispatchTransitionActive: boolean` and `completeDispatchExit(): void`, used only inside `AppFrame` to gate chrome visibility and finish the presence exit.

- [x] **Step 1: Add frame-level exit lifecycle tracking after `useDispatchLookup`**

Restore `useLayoutEffect` and `useRef` in the React import, then add:

```ts
const previousDispatchOpen = useRef(dispatch.commandBarOpen);
const [dispatchExitPending, setDispatchExitPending] = useState(false);
const dispatchClosing = previousDispatchOpen.current && !dispatch.commandBarOpen;

useLayoutEffect(() => {
  if (dispatch.commandBarOpen) {
    setDispatchExitPending(false);
  } else if (previousDispatchOpen.current) {
    setDispatchExitPending(true);
  }
  previousDispatchOpen.current = dispatch.commandBarOpen;
}, [dispatch.commandBarOpen]);

const dispatchTransitionActive =
  dispatch.commandBarOpen || dispatchClosing || dispatchExitPending;
const completeDispatchExit = useCallback(() => {
  setDispatchExitPending(false);
}, []);
```

This render-time `dispatchClosing` guard prevents a one-frame spine flash before the layout effect records the exit.

- [x] **Step 2: Gate workspace chrome on the complete Dispatch transition**

Replace the two visibility expressions with:

```ts
const showSpine = !bareChrome && !dispatchTransitionActive;
const showMobileChrome = !isDesktop && !bareChrome && !dispatchTransitionActive;
```

- [x] **Step 3: Restore the earlier synchronized workspace position animation**

Update the workspace element to:

```tsx
<motion.main
  layout="position"
  transition={chromeTransition}
  className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-paper"
>
```

- [x] **Step 4: Render Dispatch through a keyed presence surface**

Replace the always-mounted `DispatchCommandBar` call with this structure, retaining every existing prop unchanged inside it:

```tsx
<AnimatePresence initial={false} onExitComplete={completeDispatchExit}>
  {dispatch.commandBarOpen ? (
    <motion.div
      key="dispatch-takeover"
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -10 }}
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

The wrapper owns only takeover enter/exit motion; `DispatchCommandBar` continues to own dialog semantics, focus trap, keyboard handling, and content.

- [x] **Step 5: Run the focused test and confirm it is green**

Run:

```bash
cd app-front-end && npm test -- tests/flow-chrome-choreography.test.ts
```

Expected: 3 tests pass.

- [x] **Step 6: Run component regressions for Dispatch and app-frame behavior**

Run:

```bash
cd app-front-end && npm test -- src/components/__tests__/DispatchCommandBar.test.tsx tests/flow-chrome-choreography.test.ts
```

Expected: all selected tests pass with no warnings or failures.

- [x] **Step 7: Run complete frontend verification**

Run:

```bash
cd app-front-end && npm test && npm run lint && npm run build
```

Expected: Vitest exits with zero failures, ESLint exits with zero warnings/errors, and TypeScript/Vite build exits successfully.

- [x] **Step 8: Review the final diff and commit the implementation**

Run:

```bash
git diff --check
git diff -- app-front-end/src/components/AppFrame.tsx app-front-end/tests/flow-chrome-choreography.test.ts
git add app-front-end/src/components/AppFrame.tsx app-front-end/tests/flow-chrome-choreography.test.ts docs/superpowers/plans/2026-07-14-spine-dispatch-motion-restoration.md
git commit -m "fix(front): restore spine and dispatch transitions"
```

Expected: no whitespace errors; the commit includes only the two frontend files and this plan.
