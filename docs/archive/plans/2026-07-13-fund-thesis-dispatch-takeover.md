# Fund Thesis Dispatch Takeover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the fund-thesis confirmation as a Dispatch-style full-screen takeover without changing its confirmation or deployment behavior.

**Architecture:** Keep `FundThesisConfirmationModal` as the existing portal-owned, focus-trapped dialog and replace only its visual composition. Reuse Dispatch's `paper-dot-grid`, centered full-height surface, reveal cadence, restrained comparison panel, and inline footer-action language; keep thesis change data and callbacks unchanged.

**Tech Stack:** React 18, TypeScript, React portals, Framer Motion, Tailwind CSS, Vitest, React Testing Library.

## Global Constraints

- Do not change thesis diff generation, Settings deployment logic, backend APIs, or persistence.
- Do not modify `DispatchCommandBar.tsx`.
- Preserve `role="dialog"`, `aria-modal`, labelled title, descriptive copy, focus trap, initial confirm focus, focus restoration, and Escape-to-cancel while idle.
- Keep one scrollable takeover surface; do not add nested scrolling.
- Use only Framer Motion and existing project tokens/classes.
- Leave the user's uncommitted `SystemBar.tsx` and `PortfolioPage.tsx` changes untouched.

---

### Task 1: Dispatch-Style Fund Thesis Takeover

**Files:**
- Modify: `app-front-end/src/settings/FundThesisConfirmationModal.tsx`
- Modify: `app-front-end/src/settings/__tests__/FundThesisConfirmationModal.test.tsx`

**Interfaces:**
- Consumes: existing `FundThesisConfirmationModalProps`, `FundThesisChange[]`, `useFocusTrap`, `usePrefersReducedMotion`, and `onCancel` / `onConfirm` callbacks.
- Produces: the same default `FundThesisConfirmationModal` export and unchanged prop contract.

- [ ] **Step 1: Add failing Dispatch-parity assertions**

Extend the existing modal tests with a source contract imported through Vite raw loading:

```tsx
import modalSource from '../FundThesisConfirmationModal.tsx?raw';

it('uses the Dispatch takeover composition', () => {
  expect(modalSource).toContain('paper-dot-grid');
  expect(modalSource).toContain('items-center justify-center');
  expect(modalSource).toContain('Fund thesis change');
  expect(modalSource).toContain('Confirm the new mandate');
  expect(modalSource).toContain('Confirm update');
  expect(modalSource).not.toContain('<header');
  expect(modalSource).not.toContain('<footer');
});
```

Update existing role queries only where the approved copy changes, keeping assertions for explicit confirm/cancel callbacks, busy disabling, first-publication copy, Escape handling, and focus behavior.

- [ ] **Step 2: Run the modal tests and verify RED**

Run:

```bash
cd app-front-end && npm test -- src/settings/__tests__/FundThesisConfirmationModal.test.tsx
```

Expected: FAIL because the current modal lacks `paper-dot-grid`, uses separate header/footer regions, and retains the old headline/action copy.

- [ ] **Step 3: Replace the framed modal with the Dispatch composition**

Keep the portal, `AnimatePresence`, focus effects, and callbacks. Replace the rendered takeover body with this hierarchy:

```tsx
<motion.div
  ref={containerRef}
  className="paper-dot-grid fixed inset-0 z-[9999] min-h-0 overflow-y-auto overscroll-contain bg-paper text-oxford"
  role="dialog"
  aria-modal="true"
  aria-labelledby="fund-thesis-confirmation-title"
  aria-describedby="fund-thesis-confirmation-description"
>
  <div className="relative z-10 flex min-h-full w-full flex-col items-center justify-center px-phi-6 py-phi-7">
    <motion.p className="type-label-section mb-phi-3 text-center">Fund thesis change</motion.p>
    <motion.h1
      id="fund-thesis-confirmation-title"
      className="type-display m-0 max-w-[15ch] text-center text-[clamp(28px,4vw,52px)] font-medium leading-[1.1] text-oxford"
    >
      Confirm the new mandate
    </motion.h1>
    <motion.p
      id="fund-thesis-confirmation-description"
      className="mt-phi-3 max-w-[48ch] text-center type-body text-oxford/60"
    >
      {firstPublication
        ? 'You are publishing your first fund thesis. Scouts and Reviewers will use it as soon as deployment completes.'
        : 'Scouts and Reviewers will use this mandate as soon as deployment completes. Review what changes before continuing.'}
    </motion.p>
    <motion.div className="mt-phi-7 w-full max-w-3xl border border-oxford/10 bg-paper">
      <div className="grid grid-cols-2 gap-x-phi-4 border-b border-oxford/[0.08] px-phi-5 py-phi-3 md:grid-cols-[minmax(9rem,22%)_minmax(0,1fr)_minmax(0,1fr)]">
        <span className="hidden md:block" aria-hidden />
        <p className="type-label-section text-oxford/55">Currently live</p>
        <p className="type-label-section text-oxford">Proposed</p>
      </div>
      {changes.map((change) => (
        <section
          key={change.key}
          className="grid gap-y-phi-2 border-b border-oxford/[0.06] px-phi-5 py-phi-4 last:border-b-0 md:grid-cols-[minmax(9rem,22%)_minmax(0,1fr)_minmax(0,1fr)] md:gap-x-phi-5"
          aria-labelledby={`thesis-change-${change.key}`}
        >
          <h2 id={`thesis-change-${change.key}`} className="col-span-2 type-body-emphasis md:col-span-1">
            {change.label}
          </h2>
          <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford/55">
            {change.previous}
          </p>
          <p className="whitespace-pre-wrap break-words type-body-sm leading-relaxed text-oxford">
            {change.proposed}
          </p>
        </section>
      ))}
    </motion.div>
    <motion.div className="mt-phi-7 flex flex-wrap items-center justify-center gap-x-1 gap-y-1">
      <button type="button" onClick={onCancel} disabled={busy}>Go back</button>
      <span aria-hidden>·</span>
      <button ref={confirmRef} type="button" onClick={onConfirm} disabled={busy}>
        {busy ? 'Updating fund thesis…' : 'Confirm update'}
      </button>
    </motion.div>
  </div>
</motion.div>
```

Render the action separator as a muted `·`. Give both visually compact action buttons `min-h-11` and visible focus rings. Keep `ref={confirmRef}` on `Confirm update`; when busy, show `Updating fund thesis…` and disable both actions.

The comparison panel retains `Currently live` / `Proposed` headings and maps `changes` exactly once. Use the existing three-column desktop grid and make each change a stacked labelled comparison on narrow screens. Long values retain `whitespace-pre-wrap break-words`.

- [ ] **Step 4: Run focused tests and lint for GREEN**

Run:

```bash
cd app-front-end && npm test -- src/settings/__tests__/FundThesisConfirmationModal.test.tsx src/settings/__tests__/deploymentConfirmation.test.ts && npx eslint src/settings/FundThesisConfirmationModal.tsx src/settings/__tests__/FundThesisConfirmationModal.test.tsx --max-warnings 0
```

Expected: all focused tests pass and ESLint exits 0.

- [ ] **Step 5: Commit the takeover**

```bash
git add app-front-end/src/settings/FundThesisConfirmationModal.tsx app-front-end/src/settings/__tests__/FundThesisConfirmationModal.test.tsx
git commit -m "style(settings): match thesis confirmation to dispatch"
```

### Task 2: Full Frontend Verification

**Files:**
- Verify only; no expected source changes.

**Interfaces:**
- Consumes: completed Dispatch-style thesis confirmation.
- Produces: fresh regression, lint, build, and repository-state evidence.

- [ ] **Step 1: Run the complete frontend test suite**

Run:

```bash
cd app-front-end && npm test
```

Expected: all Vitest files and tests pass with zero failures.

- [ ] **Step 2: Run lint and the production build**

Run:

```bash
cd app-front-end && npm run lint && npm run build
```

Expected: ESLint exits 0 and TypeScript/Vite build succeeds.

- [ ] **Step 3: Audit the working tree**

Run:

```bash
git diff --check && git status --short && git log --oneline -6
```

Expected: the takeover changes are committed on `main`; only the user's pre-existing `app-front-end/src/components/SystemBar.tsx` and `app-front-end/src/pages/PortfolioPage.tsx` changes remain uncommitted.
