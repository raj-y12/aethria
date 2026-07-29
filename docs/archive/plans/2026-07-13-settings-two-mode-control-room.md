# Settings Two-Mode Control Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate immediate runtime controls from deployable investment policy, add clear Decision and Administration modes, and make decision thresholds directly adjustable.

**Architecture:** `SettingsPage` remains the route-level state owner and keeps the decision draft alive across tabs. A focused `OperationsStrip` owns independent optimistic PATCH state for four runtime switches, while `DecisionThresholdsPanel` gains pointer and keyboard sliders that reuse the existing threshold clamping functions. Administration is a read-only register assembled from existing settings, thesis, and agent-status responses.

**Tech Stack:** React 18, TypeScript, TanStack Query 5, Tailwind CSS 3, Vitest, Testing Library

## Global Constraints

- Keep the existing `/v1/settings` route; add no backend or database changes.
- Pass all API traffic through the existing typed modules under `src/api/`.
- Keep cost-budget editing to `cost_budget.enabled`; do not change numeric ceilings.
- Preserve Aethria's paper/Oxford palette, square geometry, Figtree/Playfair/Space Mono typography, and existing interaction utilities.
- Use plain labels and visible explanations; a user must understand whether a change saves immediately or requires deployment.
- Use no new runtime dependency.
- Preserve the decision draft across tab changes and keep operations out of the decision pending list.

---

## File map

- Create `app-front-end/src/settings/OperationsStrip.tsx`: four immediate-save switches with independent optimistic state, request state, success reconciliation, and rollback messaging.
- Create `app-front-end/src/settings/__tests__/OperationsStrip.test.tsx`: behavioral tests for payloads, disabled states, cache reconciliation, and failures.
- Modify `app-front-end/src/settings/DecisionThresholdsPanel.tsx`: draggable and keyboard-operable three-handle ladder plus exported score-conversion helper.
- Create `app-front-end/src/settings/__tests__/DecisionThresholdsPanel.test.tsx`: conversion, keyboard, ARIA, and shared-draft tests.
- Modify `app-front-end/src/settings/SettingsPage.tsx`: tabs, grouped navigation, decision-only deployment, relocated sensitivity, Administration register, and simplified pending state.
- Create `app-front-end/src/settings/__tests__/settingsNavigation.test.ts`: pure navigation metadata and pending-state coverage without mounting the route-level `AppFrame` integration.

---

### Task 1: Immediate-save operations strip

**Files:**
- Create: `app-front-end/src/settings/OperationsStrip.tsx`
- Create: `app-front-end/src/settings/__tests__/OperationsStrip.test.tsx`

**Interfaces:**
- Consumes: `Settings`, `patchSettings`, `useQueryClient`, `storageUnavailable: boolean`, and `onSettingsChange(next: Settings): void`.
- Produces: default `OperationsStrip` component. It sends a complete `agent_config` or `cost_budget` nested object in a partial top-level settings PATCH.

- [ ] **Step 1: Write the failing optimistic-save tests**

Mock `patchSettings`, render inside a `QueryClientProvider`, click Scouts, and assert immediate checked state plus the exact sibling-preserving body:

```tsx
expect(patchSettings).toHaveBeenCalledWith({
  agent_config: { ...settings.agent_config, scouts_enabled: false },
});
expect(screen.getByRole('switch', { name: /scouts/i })).toHaveAttribute('aria-checked', 'false');
expect(screen.getByRole('switch', { name: /scouts/i })).toBeDisabled();
expect(screen.getByRole('switch', { name: /reviewers/i })).not.toBeDisabled();
```

Add a success case that resolves with authoritative settings and asserts `onSettingsChange` plus `queryClient.getQueryData(['settings'])`. Add a failure case that resolves `{ error: { message: 'Could not save', errors: [] } }`, then asserts rollback and `role="alert"`. Add a storage-unavailable case that asserts all switches are disabled and the explanation is visible.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd app-front-end && npm test -- src/settings/__tests__/OperationsStrip.test.tsx`

Expected: FAIL because `OperationsStrip.tsx` does not exist.

- [ ] **Step 3: Implement the strip with per-control request state**

Define the stable control keys and accessible switch primitive:

```tsx
type OperationKey = 'scouts' | 'reviewers' | 'partners' | 'budget';

interface OperationsStripProps {
  settings: Settings;
  storageUnavailable: boolean;
  onSettingsChange: (settings: Settings) => void;
}

const [optimistic, setOptimistic] = useState(settings);
const [pending, setPending] = useState<OperationKey | null>(null);
const [error, setError] = useState<string | null>(null);

const save = async (key: OperationKey, enabled: boolean) => {
  const previous = optimistic;
  const next = updateOperation(previous, key, enabled);
  setOptimistic(next);
  setPending(key);
  setError(null);
  const body = key === 'budget'
    ? { cost_budget: next.cost_budget }
    : { agent_config: next.agent_config };
  const result = await patchSettings(body);
  if (result.error || !result.data) {
    setOptimistic(previous);
    setError(result.error?.errors[0] ?? result.error?.message ?? 'We could not save this control. Try again.');
  } else {
    setOptimistic(result.data);
    onSettingsChange(result.data);
    queryClient.setQueryData(['settings'], result.data);
  }
  setPending(null);
};
```

Use `role="switch"`, `aria-checked`, a minimum 44px hit target, visible `On`/`Off` text, `aria-busy` on the affected control, and direct copy: “Pipeline controls · Changes apply immediately.” On storage failure render: “Storage unavailable. Runtime controls cannot be changed.”

- [ ] **Step 4: Run focused tests and lint the component**

Run: `cd app-front-end && npm test -- src/settings/__tests__/OperationsStrip.test.tsx && npx eslint src/settings/OperationsStrip.tsx src/settings/__tests__/OperationsStrip.test.tsx --max-warnings 0`

Expected: all tests PASS; ESLint exits 0.

- [ ] **Step 5: Commit the independently working strip**

```bash
git add app-front-end/src/settings/OperationsStrip.tsx app-front-end/src/settings/__tests__/OperationsStrip.test.tsx
git commit -m "feat(settings): add immediate operations strip"
```

---

### Task 2: Accessible draggable threshold ladder

**Files:**
- Modify: `app-front-end/src/settings/DecisionThresholdsPanel.tsx`
- Create: `app-front-end/src/settings/__tests__/DecisionThresholdsPanel.test.tsx`

**Interfaces:**
- Consumes: existing `applyDecisionThresholds`, `DecisionThresholdBoundaries`, `draft`, `updateDraft`, and `updateThreshold` props.
- Produces: `scoreFromPointer(clientX: number, left: number, width: number): number` and three synchronized `role="slider"` controls.

- [ ] **Step 1: Write failing conversion and slider tests**

Test conversion deterministically:

```ts
expect(scoreFromPointer(150, 100, 200)).toBe(25);
expect(scoreFromPointer(50, 100, 200)).toBe(0);
expect(scoreFromPointer(350, 100, 200)).toBe(100);
expect(scoreFromPointer(100, 100, 0)).toBe(0);
```

Render the panel with default configuration and assert three sliders named “Auto-pass ceiling,” “Monitor starts,” and “Invest starts.” Fire `keyDown` with `ArrowRight` on Monitor and verify the updater produces a valid configuration whose pass/monitor boundary increases by one. Assert each slider exposes `aria-valuemin`, `aria-valuemax`, and `aria-valuenow`.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd app-front-end && npm test -- src/settings/__tests__/DecisionThresholdsPanel.test.tsx`

Expected: FAIL because `scoreFromPointer` and slider handles do not exist.

- [ ] **Step 3: Implement score conversion and shared slider behavior**

Add the pure converter:

```ts
export function scoreFromPointer(clientX: number, left: number, width: number): number {
  if (width <= 0) return 0;
  const ratio = (clientX - left) / width;
  return Math.round(Math.min(1, Math.max(0, ratio)) * 100);
}
```

Give `ThresholdBar` `onChange(patch)` and render an absolutely positioned 44px hit target for each handle. Pointer down/move uses `event.currentTarget.setPointerCapture(event.pointerId)`, reads the parent bar rectangle, and calls `onChange({ [boundaryKey]: score })`. Keyboard handling applies `ArrowLeft`/`ArrowDown: -1`, `ArrowRight`/`ArrowUp: +1`, `Home: min`, and `End: max`; all values still flow through `applyDecisionThresholds()`.

Use visually distinct handle marks: a short tick for auto-pass and full-height dividers for verdict boundaries. Add a concise instruction above the range text: “Drag a marker or use arrow keys. Numeric fields remain available below.”

- [ ] **Step 4: Run focused and existing threshold tests**

Run: `cd app-front-end && npm test -- src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/lib/__tests__/decisionThresholds.test.ts`

Expected: all tests PASS.

- [ ] **Step 5: Commit the independently working ladder**

```bash
git add app-front-end/src/settings/DecisionThresholdsPanel.tsx app-front-end/src/settings/__tests__/DecisionThresholdsPanel.test.tsx
git commit -m "feat(settings): make decision thresholds adjustable"
```

---

### Task 3: Two-mode settings information architecture

**Files:**
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Create: `app-front-end/src/settings/__tests__/settingsNavigation.test.ts`

**Interfaces:**
- Consumes: `OperationsStrip`, existing settings/thesis/agent queries, existing deployment flow, and existing `SpineNavButton` projection.
- Produces: exported `SETTINGS_SECTIONS` metadata and `tabForSection(id: SectionId): SettingsTab` helper for deterministic navigation behavior.

- [ ] **Step 1: Write failing navigation metadata tests**

```ts
expect(tabForSection('mandate')).toBe('decision');
expect(tabForSection('weights')).toBe('decision');
expect(tabForSection('policy')).toBe('admin');
expect(tabForSection('system')).toBe('admin');
expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'decision')).toHaveLength(5);
expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'admin')).toHaveLength(3);
```

Also extract and test `getPendingChanges(draft, savedSnapshot)` so an operations-only settings change cannot affect the returned decision buckets.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts`

Expected: FAIL because the exported metadata and pure helpers do not exist.

- [ ] **Step 3: Replace the one-list model with typed tab metadata**

Use:

```ts
export type SettingsTab = 'decision' | 'admin';
export type SectionId = 'mandate' | 'memo' | 'risk' | 'thresholds' | 'weights' | 'policy' | 'thesis' | 'system';

export const SETTINGS_SECTIONS = [
  { id: 'mandate', label: 'Fund mandate', tab: 'decision' },
  { id: 'memo', label: 'Memo output', tab: 'decision' },
  { id: 'risk', label: 'Ruling', tab: 'decision' },
  { id: 'thresholds', label: 'Decision thresholds', tab: 'decision' },
  { id: 'weights', label: 'Scoring weights', tab: 'decision' },
  { id: 'policy', label: 'Scoring policy', tab: 'admin' },
  { id: 'thesis', label: 'Fund thesis', tab: 'admin' },
  { id: 'system', label: 'Storage and agents', tab: 'admin' },
] as const;

export const tabForSection = (id: SectionId): SettingsTab =>
  SETTINGS_SECTIONS.find((section) => section.id === id)?.tab ?? 'decision';
```

Remove `serializeOperations`, `savedOperationsSnapshot`, `operationsDirty`, the Operations section ID, and the Operations pending bucket. Move escalation sensitivity into Ruling. Move live scoring policy content out of Scoring weights.

- [ ] **Step 4: Add the operations strip and semantic tabs**

Render `OperationsStrip` before the tablist and reconcile successful saves through `setSettings`. Add two buttons with `role="tab"`, `aria-selected`, `aria-controls`, visible focus rings, and left/right arrow behavior. The page heading and standfirst explicitly state the selected mode's semantics:

```tsx
<p>Decision edits stay in draft until you deploy them.</p>
<p>Administration shows what is live now. Runtime switches above save immediately.</p>
```

Decision renders its five sections plus preview. Administration renders three `SettingsSection` rows with textual statuses and no preview or deploy controls.

- [ ] **Step 5: Update spine switching and deployment wording**

When a spine item is clicked, call `setActiveTab(tabForSection(id))`, set `activeSection`, then use `requestAnimationFrame` to locate and scroll the mounted section. Group spine buttons under “Decision” and “Administration.” Render the deployment footer only when `activeTab === 'decision'`. Rename buttons to “Deploy decision changes.”

Include `activeTab` in the IntersectionObserver dependency list so it observes the newly mounted targets.

- [ ] **Step 6: Run navigation, configuration, and TypeScript checks**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts src/lib/__tests__/fundConfiguration.test.ts src/lib/__tests__/fundConfiguration.regression.test.ts && npm run build`

Expected: all tests PASS and the Vite production build succeeds.

- [ ] **Step 7: Commit the two-mode page**

```bash
git add app-front-end/src/settings/SettingsPage.tsx app-front-end/src/settings/__tests__/settingsNavigation.test.ts
git commit -m "feat(settings): separate decisions from administration"
```

---

### Task 4: Integrated clarity and regression verification

**Files:**
- Modify only files already touched if verification reveals a focused defect.

**Interfaces:**
- Consumes: completed Operations strip, threshold ladder, and two-mode page.
- Produces: a verified production build with no unrelated change.

- [ ] **Step 1: Run the full frontend unit suite**

Run: `cd app-front-end && npm test`

Expected: all Vitest suites PASS.

- [ ] **Step 2: Run lint and production build**

Run: `cd app-front-end && npm run lint && npm run build`

Expected: ESLint exits 0 and TypeScript/Vite build succeeds.

- [ ] **Step 3: Inspect the UI at desktop and narrow widths**

Run the existing frontend with `npm run dev` and verify:

```text
Desktop: strip is one readable row; Decision has preview; Administration has no deploy UI.
Narrow: strip becomes two columns; controls do not clip; primary decision deploy remains available.
Keyboard: Tab reaches tabs/switches/sliders; arrow keys operate tabs and sliders.
Copy: every control states whether it saves immediately or requires deployment.
```

- [ ] **Step 4: Review the final diff for scope and accidental regressions**

Run: `git diff --check && git status --short && git diff --stat HEAD~3..HEAD`

Expected: no whitespace errors; only the spec, plan, settings source, and focused tests appear.

- [ ] **Step 5: Commit any verification-only corrections**

If Step 3 required a focused correction, commit only that correction:

```bash
git add app-front-end/src/settings
git commit -m "fix(settings): polish control room clarity"
```
