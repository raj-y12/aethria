# Settings Editorial-Ledger Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Decision and Administration grouping, remove the preview column, and restyle settings as a sparse editorial ledger while preserving immediate runtime saves and transactional draft deployment.

**Architecture:** `settingsModel.ts` remains the source of truth for tab ownership and pending-change buckets. `SettingsPage.tsx` renders one full-width ledger and keeps deployment available in both tabs because both contain draft-backed configuration. `OperationsStrip.tsx` keeps its tested save behavior but returns to the original switch proportions and removes its bordered-cell grid.

**Tech Stack:** React 18, TypeScript, TanStack Query 5, Tailwind CSS 3, Vitest, Testing Library

## Global Constraints

- Keep the existing `/v1/settings` route and backend contracts.
- Add no dependency, backend change, database change, or numeric cost-budget editing.
- Keep Scouts, Reviewers, Partners, and Cost budget visible above both tabs and save them immediately.
- Decision owns Fund thesis, Decision thresholds, Scoring weights, and Escalation sensitivity.
- Administration owns Memo output, Ruling workflow, Cost budget summary, and System state.
- Keep deployable pending state and deployment controls available on both tabs.
- Remove the configuration preview entirely.
- Reuse Aethria's original square-ended 44-by-24 switch language.
- Reduce visual rules; use typography and whitespace as the primary hierarchy.
- Preserve unrelated working-tree edits in `SystemBar.tsx` and `PortfolioPage.tsx`.

---

## File map

- Modify `app-front-end/src/settings/settingsModel.ts`: corrected section IDs, labels, order, and tab ownership.
- Modify `app-front-end/src/settings/__tests__/settingsNavigation.test.ts`: exact corrected mapping and deployable Administration pending buckets.
- Modify `app-front-end/src/settings/OperationsStrip.tsx`: sparse toolbar layout and original switch treatment; save logic remains unchanged.
- Modify `app-front-end/src/settings/__tests__/OperationsStrip.test.tsx`: status-copy and switch-state coverage for the restyled control.
- Modify `app-front-end/src/settings/SettingsPage.tsx`: full-width ledger, corrected chapters, budget summary, system summary, no preview, and deployment on both tabs.

---

### Task 1: Correct the settings ownership model

**Files:**
- Modify: `app-front-end/src/settings/settingsModel.ts`
- Modify: `app-front-end/src/settings/__tests__/settingsNavigation.test.ts`

**Interfaces:**
- Consumes: `FundConfiguration`, `serializeDecisionConfig`, and existing pending-change semantics.
- Produces: `SETTINGS_SECTIONS`, `tabForSection(id)`, and `getPendingChanges(draft, snapshot)` with corrected ownership.

- [ ] **Step 1: Write the failing corrected-mapping tests**

Replace the old mapping assertions with:

```ts
expect(tabForSection('thesis')).toBe('decision');
expect(tabForSection('thresholds')).toBe('decision');
expect(tabForSection('weights')).toBe('decision');
expect(tabForSection('sensitivity')).toBe('decision');
expect(tabForSection('memo')).toBe('admin');
expect(tabForSection('workflow')).toBe('admin');
expect(tabForSection('budget')).toBe('admin');
expect(tabForSection('system')).toBe('admin');
expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'decision')).toHaveLength(4);
expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'admin')).toHaveLength(4);
```

Add a pending-state assertion proving an Administration memo edit still produces `{ label: 'Memo output', stages: 'Partner memos' }`.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts`

Expected: FAIL because the old IDs and ownership still map thesis to Administration and memo to Decision.

- [ ] **Step 3: Implement the corrected section model**

Use these exact section IDs and order:

```ts
export type SectionId =
  | 'thesis'
  | 'thresholds'
  | 'weights'
  | 'sensitivity'
  | 'memo'
  | 'workflow'
  | 'budget'
  | 'system';

export const SETTINGS_SECTIONS = [
  { id: 'thesis', label: 'Fund thesis', short: 'Thesis', tab: 'decision' },
  { id: 'thresholds', label: 'Decision thresholds', short: 'Thresholds', tab: 'decision' },
  { id: 'weights', label: 'Scoring weights', short: 'Weights', tab: 'decision' },
  { id: 'sensitivity', label: 'Escalation sensitivity', short: 'Sensitivity', tab: 'decision' },
  { id: 'memo', label: 'Memo output', short: 'Memo', tab: 'admin' },
  { id: 'workflow', label: 'Ruling workflow', short: 'Workflow', tab: 'admin' },
  { id: 'budget', label: 'Cost budget', short: 'Budget', tab: 'admin' },
  { id: 'system', label: 'System state', short: 'System', tab: 'admin' },
] satisfies ReadonlyArray<SettingsSectionDefinition>;
```

Do not change pending-change serialization or bucket labels.

- [ ] **Step 4: Run the model tests**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts`

Expected: all tests PASS.

- [ ] **Step 5: Commit the corrected model**

```bash
git add app-front-end/src/settings/settingsModel.ts app-front-end/src/settings/__tests__/settingsNavigation.test.ts
git commit -m "fix(settings): correct decision and admin ownership"
```

---

### Task 2: Restore the operations strip visual language

**Files:**
- Modify: `app-front-end/src/settings/OperationsStrip.tsx`
- Modify: `app-front-end/src/settings/__tests__/OperationsStrip.test.tsx`

**Interfaces:**
- Consumes: existing `settings`, `storageUnavailable`, `onSettingsChange`, optimistic state, and PATCH reconciliation.
- Produces: the same `OperationsStrip` API and behavior with a quieter responsive toolbar.

- [ ] **Step 1: Add failing comprehension assertions**

Extend the existing render test:

```tsx
expect(screen.getByText('Pipeline controls')).toBeInTheDocument();
expect(screen.getByText('Changes apply immediately.')).toBeInTheDocument();
expect(screen.getByRole('switch', { name: 'Scouts' })).toHaveAttribute('aria-checked', 'true');
expect(screen.getByText('On', { selector: '[data-operation-status="scouts"]' })).toBeInTheDocument();
```

The `data-operation-status` assertion fails until the restyled explicit status element exists.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd app-front-end && npm test -- src/settings/__tests__/OperationsStrip.test.tsx`

Expected: FAIL because the control-specific status marker does not exist.

- [ ] **Step 3: Implement the sparse toolbar**

Keep every line of save/reconciliation logic unchanged. Replace the visual structure with:

```tsx
<section className="border-b border-oxford/[0.08] bg-paper px-phi-4 py-phi-3 lg:px-phi-6">
  <div className="flex flex-col gap-phi-3 lg:flex-row lg:items-center">
    <div className="lg:mr-auto">
      <p className="type-label-section">Pipeline controls</p>
      <p className="mt-phi-1 type-note text-oxford/55">Changes apply immediately.</p>
    </div>
    <div className="grid grid-cols-2 gap-x-phi-5 gap-y-phi-2 sm:grid-cols-4">
      {/* controls */}
    </div>
  </div>
</section>
```

Each control uses a label, original-style `h-6 w-11` track, `h-4 w-4` thumb, and a status element with `data-operation-status={control.key}`. Remove cell borders, descriptions, backdrop blur, and the miniaturized 32-by-16 track.

- [ ] **Step 4: Run focused tests and lint**

Run: `cd app-front-end && npm test -- src/settings/__tests__/OperationsStrip.test.tsx && npx eslint src/settings/OperationsStrip.tsx src/settings/__tests__/OperationsStrip.test.tsx --max-warnings 0`

Expected: all tests PASS and ESLint exits 0.

- [ ] **Step 5: Commit the strip correction**

```bash
git add app-front-end/src/settings/OperationsStrip.tsx app-front-end/src/settings/__tests__/OperationsStrip.test.tsx
git commit -m "style(settings): simplify pipeline controls"
```

---

### Task 3: Rebuild the page as an editorial ledger

**Files:**
- Modify: `app-front-end/src/settings/SettingsPage.tsx`

**Interfaces:**
- Consumes: corrected `SETTINGS_SECTIONS`, existing draft update functions, `settings.cost_budget`, `agentsStatus`, and spine projection.
- Produces: one full-width ledger with corrected tab content, no preview, and deployment controls in both modes.

- [ ] **Step 1: Remove preview-only components and layout**

Delete `PreviewPanel` and `SettingsSidebarFooter`. Replace the conditional two-column grid with:

```tsx
<div
  id={`settings-panel-${activeTab}`}
  role="tabpanel"
  aria-labelledby={`settings-tab-${activeTab}`}
  className="min-h-full"
>
  <div className="mx-auto flex w-full max-w-[68rem] min-w-0 flex-col px-phi-5 py-phi-7 lg:px-phi-7">
    {/* heading and chapters */}
  </div>
</div>
```

Remove all preview rendering and imports.

- [ ] **Step 2: Reduce chapter rules and strengthen whitespace**

Change `SettingsSection` from a border-led section to:

```tsx
<section id={id} className={`py-phi-8 first:pt-0 ${className ?? ''}`}>
  <div className="grid gap-phi-6 lg:grid-cols-[minmax(10rem,22%)_minmax(0,1fr)] lg:gap-phi-8">
    {/* title, consequence, content */}
  </div>
</section>
```

Apply a faint top rule only through an explicit `className="border-t border-oxford/[0.07]"` on later major chapters. Do not add cards or boxed status rows.

- [ ] **Step 3: Render corrected Decision chapters**

Render in this order:

```tsx
<SettingsSection id="thesis" title="Fund thesis">{/* former mandate fields */}</SettingsSection>
<SettingsSection id="thresholds" title="Decision thresholds">{/* ladder */}</SettingsSection>
<SettingsSection id="weights" title="Scoring weights">{/* weights */}</SettingsSection>
<SettingsSection id="sensitivity" title="Escalation sensitivity">{/* sensitivity select */}</SettingsSection>
```

Use heading “How the fund decides.” and state that changes remain draft until deployment. Keep thesis and policy version text near Thesis and Weights respectively.

- [ ] **Step 4: Render corrected Administration chapters**

Render in this order:

```tsx
<SettingsSection id="memo" title="Memo output">{/* existing memo fields */}</SettingsSection>
<SettingsSection id="workflow" title="Ruling workflow">{/* acknowledgement toggles */}</SettingsSection>
<SettingsSection id="budget" title="Cost budget">{/* read-only limits */}</SettingsSection>
<SettingsSection id="system" title="System state">{/* concise readiness summary */}</SettingsSection>
```

The budget summary shows `max_tokens_per_run`, `daily_cost_ceiling`, `weekly_cost_ceiling`, and `cooldown_seconds` using `type-data` for values and plain labels. It includes no input. Replace `StatusRegisterRow` with a border-light `EditorialStatus` helper that uses spacing and one optional dot rather than a rule per row.

- [ ] **Step 5: Keep deployment controls visible on both tabs**

Remove `activeTab === 'decision'` conditions around the spine footer and mobile deployment button. Rename the action to “Deploy changes.” Update the Administration standfirst to:

```tsx
Preferences below remain draft until deployed. Pipeline controls above save immediately.
```

Keep pending buckets unchanged so memo and workflow changes appear in the deployment list.

- [ ] **Step 6: Run focused regressions, lint, and build**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsNavigation.test.ts src/settings/__tests__/OperationsStrip.test.tsx src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/hooks/__tests__/useFundConfiguration.test.tsx && npm run lint && npm run build`

Expected: focused tests PASS, ESLint exits 0, and Vite production build succeeds.

- [ ] **Step 7: Commit the editorial ledger**

```bash
git add app-front-end/src/settings/SettingsPage.tsx
git commit -m "fix(settings): apply editorial ledger layout"
```

---

### Task 4: Full verification

**Files:**
- Modify only the settings files above if a focused regression is discovered.

**Interfaces:**
- Consumes: corrected settings implementation.
- Produces: a verified frontend with unrelated user edits preserved.

- [ ] **Step 1: Run the full unit suite**

Run: `cd app-front-end && npm test`

Expected: all Vitest suites PASS.

- [ ] **Step 2: Run lint and production build**

Run: `cd app-front-end && npm run lint && npm run build`

Expected: ESLint exits 0 and TypeScript/Vite build succeeds.

- [ ] **Step 3: Review scope and repository state**

Run: `git diff --check && git status --short && git log -5 --oneline`

Expected: no whitespace errors; only the pre-existing `SystemBar.tsx` and `PortfolioPage.tsx` working-tree edits remain unstaged.
