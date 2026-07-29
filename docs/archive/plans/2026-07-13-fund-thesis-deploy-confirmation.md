# Fund Thesis Deploy Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require an explicit full-screen before/after confirmation before deploying any fund-thesis change.

**Architecture:** Add pure mandate comparison and formatting helpers to the existing settings model, then render their output through a focused portal-based confirmation component. Split `SettingsPage` deployment into a validation/request gate and the existing deployment transaction so non-thesis changes still deploy directly while thesis changes pause for manual confirmation.

**Tech Stack:** React 18, TypeScript, Framer Motion, TanStack Query, Vitest, React Testing Library, Tailwind CSS.

## Global Constraints

- Any change to `FundConfiguration.mandate` requires confirmation; non-thesis changes do not.
- The first thesis publication requires confirmation and displays that no thesis is currently deployed.
- The modal must match the existing `AgentLogoutModal` and Dispatch visual language.
- Use Framer Motion only, honor reduced motion, trap focus, restore focus, and support Escape-to-cancel.
- The user must click **Yes, update fund thesis** before deployment begins; backdrop clicks do not dismiss.
- Runtime controls remain immediate-save and never use this confirmation.
- Preserve the existing deployment transaction, error reporting, and per-user API path.

---

### Task 1: Fund Thesis Comparison Model

**Files:**
- Modify: `app-front-end/src/settings/settingsModel.ts`
- Modify: `app-front-end/src/settings/__tests__/settingsNavigation.test.ts`

**Interfaces:**
- Consumes: `FundConfiguration`, its `mandate` field, and the string returned by `serializeDecisionConfig`.
- Produces: `FundThesisChange`, `FundThesisChangeSet`, and `getFundThesisChangeSet(draft, savedSnapshot, firstPublication)`.

- [ ] **Step 1: Write failing comparison tests**

Add tests that assert unchanged mandates return `null`, a changed mandate returns only changed display rows, arrays and numeric fields have readable values, first publication includes all populated rows with `No thesis currently deployed`, and malformed snapshots fail closed by requiring confirmation.

```ts
it('describes only changed fund-thesis fields', () => {
  const live = createDefaultFundConfiguration();
  const draft = {
    ...live,
    mandate: {
      ...live.mandate,
      preferredStages: ['Seed', 'Series A'],
      ownershipTarget: 12,
    },
  };

  expect(getFundThesisChangeSet(draft, serializeDecisionConfig(live), false)).toEqual({
    firstPublication: false,
    changes: [
      { key: 'preferredStages', label: 'Preferred stages', previous: 'Pre-seed, Seed', proposed: 'Seed, Series A' },
      { key: 'ownershipTarget', label: 'Ownership target', previous: '10%', proposed: '12%' },
    ],
  });
});

it('requires confirmation when the saved snapshot is malformed', () => {
  const draft = createDefaultFundConfiguration();
  expect(getFundThesisChangeSet(draft, '{bad json', false)?.changes.length).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Run the comparison tests and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts`

Expected: FAIL because `getFundThesisChangeSet` is not exported.

- [ ] **Step 3: Implement the pure comparison model**

Add the exported types and a fixed field-definition table covering `fundName`, `mandateName`, `preferredStages`, `geographies`, `customGeography`, `sectors`, `customSectors`, `excludedSectors`, `businessModels`, `checkSizeMin`, `checkSizeMax`, `ownershipTarget`, `minimumTraction`, and `thesisText`.

```ts
export interface FundThesisChange {
  key: keyof FundConfiguration['mandate'];
  label: string;
  previous: string;
  proposed: string;
}

export interface FundThesisChangeSet {
  firstPublication: boolean;
  changes: FundThesisChange[];
}

export function getFundThesisChangeSet(
  draft: FundConfiguration,
  savedSnapshot: string,
  firstPublication: boolean,
): FundThesisChangeSet | null {
  let saved: Partial<FundConfiguration> | null = null;
  try {
    saved = JSON.parse(savedSnapshot) as Partial<FundConfiguration>;
  } catch {
    saved = null;
  }
  const previous = saved?.mandate;
  const forceReview = firstPublication || previous == null;
  const changes = thesisFields.flatMap((field) => {
    const before = formatThesisValue(field.key, previous?.[field.key]);
    const after = formatThesisValue(field.key, draft.mandate[field.key]);
    if (!forceReview && before === after) return [];
    if (firstPublication && after === 'Not set') return [];
    return [{ key: field.key, label: field.label, previous: firstPublication ? 'No thesis currently deployed' : before, proposed: after }];
  });
  return changes.length ? { firstPublication, changes } : null;
}
```

Use `Not set` for empty values, comma-separated arrays, compact currency for check sizes, and a `%` suffix for ownership.

- [ ] **Step 4: Run tests and lint for GREEN**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts && npx eslint src/settings/settingsModel.ts src/settings/__tests__/settingsNavigation.test.ts --max-warnings 0`

Expected: all settings navigation tests pass and ESLint exits 0.

- [ ] **Step 5: Commit the comparison model**

```bash
git add app-front-end/src/settings/settingsModel.ts app-front-end/src/settings/__tests__/settingsNavigation.test.ts
git commit -m "feat(settings): describe fund thesis changes"
```

### Task 2: Full-Screen Thesis Confirmation Takeover

**Files:**
- Create: `app-front-end/src/settings/FundThesisConfirmationModal.tsx`
- Create: `app-front-end/src/settings/__tests__/FundThesisConfirmationModal.test.tsx`

**Interfaces:**
- Consumes: `FundThesisChange[]` from Task 1.
- Produces: default `FundThesisConfirmationModal` component with props `{ open, changes, firstPublication, busy, onCancel, onConfirm }`.

- [ ] **Step 1: Write failing modal behavior tests**

```tsx
render(
  <FundThesisConfirmationModal
    open
    changes={[{ key: 'sectors', label: 'Sectors', previous: 'Fintech', proposed: 'Climate' }]}
    firstPublication={false}
    busy={false}
    onCancel={onCancel}
    onConfirm={onConfirm}
  />,
);

expect(screen.getByRole('dialog', { name: /confirm fund thesis change/i })).toBeInTheDocument();
expect(screen.getByText('Fintech')).toBeInTheDocument();
expect(screen.getByText('Climate')).toBeInTheDocument();
expect(onConfirm).not.toHaveBeenCalled();
fireEvent.click(screen.getByRole('button', { name: /yes, update fund thesis/i }));
expect(onConfirm).toHaveBeenCalledTimes(1);
```

Also test Escape cancellation, `No thesis currently deployed` on first publication, busy-state disabling, initial focus inside the dialog, and focus restoration after close.

- [ ] **Step 2: Run modal tests and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/FundThesisConfirmationModal.test.tsx`

Expected: FAIL because the modal component does not exist.

- [ ] **Step 3: Implement the takeover using existing modal conventions**

Create a portal-based component using `AnimatePresence`, `motion`, `useFocusTrap`, and `usePrefersReducedMotion`. Use a full-paper takeover, restrained staggered entrance, scrollable comparison body, and bottom action region.

```tsx
interface FundThesisConfirmationModalProps {
  open: boolean;
  changes: FundThesisChange[];
  firstPublication: boolean;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function FundThesisConfirmationModal({
  open,
  changes,
  firstPublication,
  busy,
  onCancel,
  onConfirm,
}: FundThesisConfirmationModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(open, containerRef);

  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement as HTMLElement | null;
      requestAnimationFrame(() => confirmRef.current?.focus());
      return;
    }
    restoreFocusRef.current?.focus?.();
  }, [open]);

  useEffect(() => {
    if (!open || busy) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [busy, onCancel, open]);

  if (typeof document === 'undefined') return null;
  return createPortal(
    <AnimatePresence>{open ? (
      <motion.div ref={containerRef} role="dialog" aria-modal="true" aria-labelledby="fund-thesis-confirmation-title">
        <h1 id="fund-thesis-confirmation-title">Confirm fund thesis change</h1>
        <p>Scouts and Reviewers will use this proposed thesis after deployment.</p>
        <div aria-label="Fund thesis changes">
          {changes.map((change) => (
            <section key={change.key}>
              <h2>{change.label}</h2>
              <p><span>Currently live</span>{change.previous}</p>
              <p><span>Proposed</span>{change.proposed}</p>
            </section>
          ))}
        </div>
        <button ref={confirmRef} type="button" disabled={busy} onClick={onConfirm}>Yes, update fund thesis</button>
        <button type="button" disabled={busy} onClick={onCancel}>Go back</button>
      </motion.div>
    ) : null}</AnimatePresence>,
    document.body,
  );
}
```

The title must be `Confirm fund thesis change`; column labels must be `Currently live` and `Proposed`; buttons must be `Yes, update fund thesis` and `Go back`.

- [ ] **Step 4: Run modal tests and lint for GREEN**

Run: `cd app-front-end && npm test -- src/settings/__tests__/FundThesisConfirmationModal.test.tsx && npx eslint src/settings/FundThesisConfirmationModal.tsx src/settings/__tests__/FundThesisConfirmationModal.test.tsx --max-warnings 0`

Expected: all modal tests pass and ESLint exits 0.

- [ ] **Step 5: Commit the confirmation component**

```bash
git add app-front-end/src/settings/FundThesisConfirmationModal.tsx app-front-end/src/settings/__tests__/FundThesisConfirmationModal.test.tsx
git commit -m "feat(settings): add thesis confirmation takeover"
```

### Task 3: Gate the Existing Deployment Transaction

**Files:**
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Create: `app-front-end/src/settings/__tests__/deploymentConfirmation.test.ts`

**Interfaces:**
- Consumes: `getFundThesisChangeSet` and `FundThesisConfirmationModal` from Tasks 1 and 2.
- Produces: deploy-request behavior where thesis changes pause and non-thesis changes continue directly.

- [ ] **Step 1: Extract and test the deploy decision as a pure helper**

Add `getDeploymentConfirmation` to `settingsModel.ts` so the page behavior can be tested without rendering the entire authenticated settings route.

```ts
export function getDeploymentConfirmation(
  draft: FundConfiguration,
  savedSnapshot: string,
  hasActiveThesis: boolean,
): FundThesisChangeSet | null {
  return getFundThesisChangeSet(draft, savedSnapshot, !hasActiveThesis);
}
```

In `deploymentConfirmation.test.ts`, verify a memo-only edit returns `null`, a scoring-only edit returns `null`, a mandate edit returns a change set, and no active thesis forces a first-publication change set.

- [ ] **Step 2: Run the deploy-decision test and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/deploymentConfirmation.test.ts`

Expected: FAIL because `getDeploymentConfirmation` is not exported.

- [ ] **Step 3: Connect the confirmation state to SettingsPage**

Add `thesisConfirmation` state, rename the existing async transaction to `performDeploy`, and add a synchronous request gate.

```tsx
const [thesisConfirmation, setThesisConfirmation] = useState<FundThesisChangeSet | null>(null);

const requestDeploy = () => {
  const nextErrors = getDeploymentValidationErrors();
  if (nextErrors.length) {
    setErrors(nextErrors);
    return;
  }
  const confirmation = getDeploymentConfirmation(
    draft,
    savedSnapshot,
    thesisSummary != null,
  );
  if (confirmation) {
    setThesisConfirmation(confirmation);
    return;
  }
  void performDeploy();
};
```

All deploy buttons and spine refs call `requestDeploy`. Render `FundThesisConfirmationModal` beside the page shell. `onCancel` clears the state. `onConfirm` clears the state and invokes `performDeploy` once. Keep validation in `performDeploy` as a defensive final gate or share one validation helper so confirmation can never bypass validation.

- [ ] **Step 4: Run focused settings tests, lint, and build**

Run: `cd app-front-end && npm test -- src/settings/__tests__/deploymentConfirmation.test.ts src/settings/__tests__/FundThesisConfirmationModal.test.tsx src/settings/__tests__/settingsNavigation.test.ts src/settings/__tests__/OperationsStrip.test.tsx && npm run lint && npm run build`

Expected: focused tests pass, ESLint exits 0, and Vite production build succeeds.

- [ ] **Step 5: Commit the deployment gate**

```bash
git add app-front-end/src/settings/settingsModel.ts app-front-end/src/settings/SettingsPage.tsx app-front-end/src/settings/__tests__/deploymentConfirmation.test.ts
git commit -m "feat(settings): confirm thesis before deployment"
```

### Task 4: Full Verification and Workspace Audit

**Files:**
- Verify only; no expected source edits.

**Interfaces:**
- Consumes: the complete confirmation flow from Tasks 1–3.
- Produces: fresh evidence that the frontend is shippable without disturbing unrelated working-tree changes.

- [ ] **Step 1: Run the entire frontend test suite**

Run: `cd app-front-end && npm test`

Expected: every Vitest file and test passes with zero failures.

- [ ] **Step 2: Run lint and production build**

Run: `cd app-front-end && npm run lint && npm run build`

Expected: ESLint exits 0 and TypeScript/Vite production build succeeds.

- [ ] **Step 3: Audit the final diff and repository state**

Run: `git diff --check && git status --short && git log --oneline -8`

Expected: no whitespace errors; feature files are committed; pre-existing edits to `app-front-end/src/components/SystemBar.tsx` and `app-front-end/src/pages/PortfolioPage.tsx` remain unstaged and untouched.
