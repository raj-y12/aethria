# Settings Trust and Navigation Implementation Plan

> **For Codex:** Execute this plan task-by-task with `superpowers:subagent-driven-development` or inline execution. Use test-driven development and run verification before claiming completion.

**Goal:** Correct the Fable settings redesign so persistence, navigation, recovery, validation, and precision are immediately understandable without losing its focused workspace layout.

**Architecture:** Keep `SettingsPage` as the data and transaction owner. Derive desktop and mobile navigation from one settings model, keep `SettingsTopBar` presentational, and add one compact reusable confirmation dialog. Fund-policy fields remain draft data until deployment; runtime controls retain their existing immediate-save behavior.

**Tech stack:** React 19, TypeScript, TanStack Query, Framer Motion, Vitest, Testing Library, Tailwind CSS.

## Non-negotiable design constraints

- Preserve the focused top bar, desktop rail, and single scrolling reading column from the Fable redesign.
- Present exactly two persistence groups:
  - **Fund policy — deploys as a version:** thesis, version, thresholds, sensitivity, weights, memo output, ruling workflow.
  - **Live runtime — saves immediately:** pipeline controls, budget enforcement and limits, system state.
- “Restore defaults” modifies only the deployable draft. It must not mutate the live configuration or saved snapshot.
- Keep immediate runtime saves, the existing rounded switches, the Dispatch-style thesis confirmation, and Framer Motion.
- Functional labels and status text must be at least 12px and meet a 4.5:1 contrast target.
- Do not change backend APIs, database schema, policy versioning semantics, Dispatch, or the thesis confirmation flow.
- Do not stage unrelated edits in `app-front-end/src/components/SystemBar.tsx`, `app-front-end/src/pages/PortfolioPage.tsx`, or `.impeccable/critique/`.

---

### Task 1: Record the approved Fable baseline

**Files:**
- Include: `app-front-end/screenshot/main.tsx`
- Include: `app-front-end/src/App.tsx`
- Include: `app-front-end/src/settings/DecisionThresholdsPanel.tsx`
- Include: `app-front-end/src/settings/OperationsStrip.tsx`
- Include: `app-front-end/src/settings/SettingsPage.tsx`
- Include: `app-front-end/src/settings/SettingsRail.tsx`
- Include: `app-front-end/src/settings/SettingsTopBar.tsx`
- Include deletion: `app-front-end/src/settings/SettingsRoomChrome.tsx`
- Include deletion: `app-front-end/src/settings/__tests__/SettingsRoomChrome.test.tsx`
- Include: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`
- Exclude: `app-front-end/src/components/SystemBar.tsx`
- Exclude: `app-front-end/src/pages/PortfolioPage.tsx`
- Exclude: `.impeccable/critique/`

**Step 1: Inspect the exact baseline diff**

Run:

```bash
git diff -- app-front-end/screenshot/main.tsx app-front-end/src/App.tsx app-front-end/src/settings
git status --short
```

Confirm the included files form the Fable settings redesign and the three excluded paths remain unrelated.

**Step 2: Verify the baseline before recording it**

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/settingsRoomLayout.test.ts
npm run build
```

Expected: both commands pass. If they fail because the Fable baseline is internally broken, stop and report the failure before committing; do not hide it inside the corrective work.

**Step 3: Commit only the baseline settings files**

Run:

```bash
git add app-front-end/screenshot/main.tsx app-front-end/src/App.tsx app-front-end/src/settings/DecisionThresholdsPanel.tsx app-front-end/src/settings/OperationsStrip.tsx app-front-end/src/settings/SettingsPage.tsx app-front-end/src/settings/SettingsRail.tsx app-front-end/src/settings/SettingsTopBar.tsx app-front-end/src/settings/SettingsRoomChrome.tsx app-front-end/src/settings/__tests__/SettingsRoomChrome.test.tsx app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts
git diff --cached --check
git diff --cached --stat
git commit -m "feat(settings): add focused configuration workspace"
```

Expected: the baseline is isolated in one commit; unrelated user changes remain unstaged.

---

### Task 2: Create truthful persistence groups and shared navigation

**Files:**
- Modify: `app-front-end/src/settings/settingsModel.ts`
- Modify: `app-front-end/src/settings/SettingsRail.tsx`
- Create: `app-front-end/src/settings/SettingsMobileNav.tsx`
- Create: `app-front-end/src/settings/__tests__/SettingsMobileNav.test.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`
- Test: existing settings model tests, or create `app-front-end/src/settings/__tests__/settingsModel.test.ts` if none exists

**Step 1: Write failing model and mobile-navigation tests**

Cover these behaviors:

```ts
expect(SETTINGS_GROUPS.map((group) => group.label)).toEqual([
  'Fund policy',
  'Live runtime',
]);

expect(SETTINGS_SECTIONS.map((section) => section.id)).toEqual([
  'thesis',
  'version',
  'thresholds',
  'sensitivity',
  'weights',
  'memo',
  'workflow',
  'budget',
  'system',
]);
```

Render `SettingsMobileNav` and assert that:

- it renders a native `<select>`;
- it renders `Fund policy — deploys as a version` and `Live runtime — saves immediately` as optgroup labels;
- choosing `budget` calls `onSelect('budget')`;
- an attention section gains a visible `Needs attention` suffix.

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/settingsModel.test.ts src/settings/__tests__/SettingsMobileNav.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
```

Expected: tests fail because the shared grouped model and mobile navigator do not exist yet.

**Step 2: Replace tab-oriented metadata with a persistence-oriented model**

Implement the following source of truth in `settingsModel.ts`:

```ts
export type SettingsPersistenceGroup = 'policy' | 'runtime';

export type SectionId =
  | 'thesis'
  | 'version'
  | 'thresholds'
  | 'sensitivity'
  | 'weights'
  | 'memo'
  | 'workflow'
  | 'budget'
  | 'system';

export const SETTINGS_GROUPS = [
  { id: 'policy', label: 'Fund policy', persistence: 'Deploys as a version' },
  { id: 'runtime', label: 'Live runtime', persistence: 'Saves immediately' },
] as const;

export const SETTINGS_SECTIONS = [
  { id: 'thesis', label: 'Fund thesis', short: 'Thesis', group: 'policy' },
  { id: 'version', label: 'Version context', short: 'Version', group: 'policy' },
  { id: 'thresholds', label: 'Decision thresholds', short: 'Thresholds', group: 'policy' },
  { id: 'sensitivity', label: 'Escalation sensitivity', short: 'Sensitivity', group: 'policy' },
  { id: 'weights', label: 'Scoring weights', short: 'Weights', group: 'policy' },
  { id: 'memo', label: 'Memo output', short: 'Memo', group: 'policy' },
  { id: 'workflow', label: 'Ruling workflow', short: 'Workflow', group: 'policy' },
  { id: 'budget', label: 'Cost budget', short: 'Budget', group: 'runtime' },
  { id: 'system', label: 'System state', short: 'System', group: 'runtime' },
] as const satisfies readonly {
  id: SectionId;
  label: string;
  short: string;
  group: SettingsPersistenceGroup;
}[];
```

Remove `SettingsTab`, `tabForSection`, and any stale decision/admin copy if no remaining consumer needs them.

**Step 3: Render both navigators from the shared model**

- Update `SettingsRail` to group links under the two persistence headings.
- Do not label the Administration/runtime group simply “Live”; use the explicit persistence phrase.
- Implement `SettingsMobileNav` as a sticky native select below the fixed top bar, using `<optgroup>` for the same two groups.
- Keep the mobile control visible below `lg`; keep the rail visible at `lg` and above.
- Give the mobile control a minimum 44px interactive height.
- Use the same `activeSection` and `attentionSection` props for rail and mobile navigation.

**Step 4: Reorder and relabel page sections**

Render page sections in exactly the `SETTINGS_SECTIONS` order. Add a real `version` section anchor around the current version context. Replace misleading decision/admin headers with:

```tsx
<GroupHeader
  title="Fund policy"
  description="Changes here stay in draft until you deploy a new version."
/>

<GroupHeader
  title="Live runtime"
  description="Changes here save immediately and affect the running system."
/>
```

Pipeline controls belong to the runtime group even if they remain in `OperationsStrip`; ensure the strip copy explicitly says those controls save immediately.

**Step 5: Run focused tests and commit**

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/settingsModel.test.ts src/settings/__tests__/SettingsMobileNav.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git diff --check
git add src/settings/settingsModel.ts src/settings/SettingsRail.tsx src/settings/SettingsMobileNav.tsx src/settings/__tests__/SettingsMobileNav.test.tsx src/settings/SettingsPage.tsx src/settings/__tests__/settingsRoomLayout.test.ts src/settings/__tests__/settingsModel.test.ts
git commit -m "refactor(settings): align navigation with persistence"
```

Expected: focused tests pass and desktop/mobile section order is identical.

---

### Task 3: Make restoring defaults and leaving with a draft safe

**Files:**
- Create: `app-front-end/src/settings/SettingsActionDialog.tsx`
- Create: `app-front-end/src/settings/__tests__/SettingsActionDialog.test.tsx`
- Modify: `app-front-end/src/settings/SettingsTopBar.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`

**Step 1: Write failing interaction tests**

Test the dialog in isolation:

- opening moves focus into the dialog;
- Tab and Shift+Tab stay inside it;
- Escape calls `onCancel` unless `busy` is true;
- confirm calls `onConfirm`;
- closing restores focus to the trigger.

Add page-level tests, using the existing data-hook mocks, to prove:

- clicking `Restore defaults` opens a confirmation dialog;
- confirming changes the draft fields but does not call the deployment mutation and does not replace the last deployed snapshot;
- the top bar shows `Defaults restored` with `Undo`;
- Undo restores the exact pre-restore draft;
- clicking Back with deployable changes opens the leave dialog;
- `Keep editing` closes the dialog without navigation;
- `Discard and leave` restores the last live configuration and navigates back;
- Back navigates immediately when there are no deployable changes.

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/SettingsActionDialog.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
```

Expected: tests fail because confirmation, undo, and guarded exit do not exist.

**Step 2: Implement the compact Dispatch-language action dialog**

Use a portal and this explicit API:

```ts
type SettingsActionDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};
```

Match the existing Dispatch/logout modal language: Oxford backdrop, warm paper panel, restrained rules, uppercase mono eyebrow, clear primary and secondary actions. Use Framer Motion only. Include `role="dialog"`, `aria-modal="true"`, labelled title/description, focus trapping, Escape handling, and focus restoration.

**Step 3: Separate live configuration from the local draft**

Maintain this invariant in `SettingsPage`:

```ts
// `configuration` remains the last live/deployed policy configuration.
// `draft` is the only value edited by policy controls.
// Restore defaults changes `draft` only.
```

Use state shaped like:

```ts
type SettingsDialogState = 'restore' | 'leave' | null;

const [dialog, setDialog] = useState<SettingsDialogState>(null);
const [preRestoreDraft, setPreRestoreDraft] = useState<FundConfiguration | null>(null);
```

The confirmed restore handler must follow this sequence:

```ts
const restoreDefaults = () => {
  setPreRestoreDraft(draft);
  setDraft(DEFAULT_FUND_CONFIGURATION);
  setDialog(null);
  setStatus({ tone: 'notice', message: 'Defaults restored' });
};
```

Do **not** call `setConfiguration(DEFAULT_FUND_CONFIGURATION)`. Do **not** update `savedSnapshot`. This guarantees defaults remain pending and the live policy stays intact.

Undo restores `preRestoreDraft`, clears it, and updates the top-bar message. A later ordinary edit may clear the Undo offer if retaining it would restore stale input.

**Step 4: Guard Back and browser exit**

Define pending deployable changes by comparing the canonical serialized policy draft with `savedSnapshot`. Runtime mutations are excluded.

```ts
const requestExit = () => {
  if (hasPendingPolicyChanges) {
    setDialog('leave');
    return;
  }
  navigateBack();
};

const discardAndLeave = () => {
  setDraft(configuration);
  setPreRestoreDraft(null);
  setDialog(null);
  navigateBack();
};
```

This works because Step 3 keeps `configuration` live and never overwrites it during restore. Add a `beforeunload` listener only while `hasPendingPolicyChanges` is true; remove it on cleanup. Do not warn for immediate runtime changes that have already saved.

**Step 5: Update top-bar action language**

- Rename `Reset` to `Restore defaults`.
- Keep it visually secondary to Deploy.
- Keep Back connected to `requestExit`, not directly to navigation.
- Render `Defaults restored · Undo` in the top bar after confirmation.
- Use a minimum 44px target for Back, Restore defaults, Undo, and Deploy.

**Step 6: Run focused tests and commit**

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/SettingsActionDialog.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git diff --check
git add src/settings/SettingsActionDialog.tsx src/settings/__tests__/SettingsActionDialog.test.tsx src/settings/SettingsTopBar.tsx src/settings/SettingsPage.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git commit -m "feat(settings): make restore and exit safe"
```

Expected: restoring defaults is reversible and cannot silently become live.

---

### Task 4: Keep deployment feedback visible and route validation errors

**Files:**
- Modify: `app-front-end/src/settings/settingsModel.ts`
- Modify: `app-front-end/src/settings/__tests__/settingsModel.test.ts`
- Modify: `app-front-end/src/settings/SettingsTopBar.tsx`
- Create or modify: `app-front-end/src/settings/__tests__/SettingsTopBar.test.tsx`
- Modify: `app-front-end/src/settings/SettingsRail.tsx`
- Modify: `app-front-end/src/settings/SettingsMobileNav.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`

**Step 1: Write failing status and routing tests**

Add pure mapping tests:

```ts
expect(sectionForDeploymentError('Scoring weights must total 100')).toBe('weights');
expect(sectionForDeploymentError('Monitor threshold overlaps invest')).toBe('thresholds');
expect(sectionForDeploymentError('Memo output is invalid')).toBe('memo');
expect(sectionForDeploymentError('Risk ruling is incomplete')).toBe('workflow');
expect(sectionForDeploymentError('Fund thesis is required')).toBe('thesis');
```

Test `SettingsTopBar` for these mutually understandable states:

- Live;
- Draft changes;
- Deploying…;
- deployment error;
- Defaults restored with Undo;
- Deployed successfully.

Add a page interaction test where deployment validation fails and assert that the corresponding section receives focus and both navigation variants expose `Needs attention` for that section.

**Step 2: Implement deterministic error-to-section routing**

Add to `settingsModel.ts`:

```ts
export function sectionForDeploymentError(error: string): SectionId {
  const value = error.toLowerCase();
  if (value.includes('weight')) return 'weights';
  if (value.includes('threshold') || value.includes('score band')) return 'thresholds';
  if (value.includes('memo')) return 'memo';
  if (value.includes('risk') || value.includes('ruling')) return 'workflow';
  return 'thesis';
}
```

**Step 3: Move transactional feedback into the fixed top bar**

Give `SettingsTopBar` explicit `message`, `tone`, `onUndo`, and `canUndo` props rather than making it infer transaction state. Apply this priority:

1. Deploying
2. Error
3. Defaults restored / Undo
4. Deployed successfully
5. Draft changes
6. Live

Keep this status visible at mobile widths. Allow the action/status region to wrap rather than hiding it; Deploy remains the visually dominant action and at least 44px high.

Remove duplicate deploy alerts from the top of the scrolling content unless they provide field-specific help.

**Step 4: Focus and expose the invalid section**

On validation failure:

```ts
const section = sectionForDeploymentError(message);
setAttentionSection(section);
document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
requestAnimationFrame(() => document.getElementById(section)?.focus());
```

Ensure every section wrapper has `id={id}` and `tabIndex={-1}`. Add a restrained attention marker to the matching desktop rail item and mobile select label. Clear attention when the relevant field becomes valid or after a successful deployment.

**Step 5: Run tests and commit**

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/settingsModel.test.ts src/settings/__tests__/SettingsTopBar.test.tsx src/settings/__tests__/SettingsMobileNav.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git diff --check
git add src/settings/settingsModel.ts src/settings/__tests__/settingsModel.test.ts src/settings/SettingsTopBar.tsx src/settings/__tests__/SettingsTopBar.test.tsx src/settings/SettingsRail.tsx src/settings/SettingsMobileNav.tsx src/settings/SettingsPage.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git commit -m "feat(settings): keep deployment feedback visible"
```

Expected: deployment state remains visible at the action point and validation failures lead directly to the affected section.

---

### Task 5: Restore threshold precision, readable utility text, and recovery actions

**Files:**
- Modify: `app-front-end/src/settings/DecisionThresholdsPanel.tsx`
- Modify or create: `app-front-end/src/settings/__tests__/DecisionThresholdsPanel.test.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/SettingsTopBar.tsx`
- Modify: `app-front-end/src/settings/SettingsRail.tsx`
- Modify: `app-front-end/src/settings/SettingsMobileNav.tsx`
- Modify: `app-front-end/src/settings/OperationsStrip.tsx`
- Modify: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`

**Step 1: Write failing threshold and recovery tests**

For `DecisionThresholdsPanel`, assert that:

- three labelled numeric inputs exist: `Monitor starts at`, `Invest starts at`, and `Auto-pass below`;
- changing an input calls the same change handler used by the visual threshold control;
- Monitor is bounded from 2 through `invest - 1`;
- Invest is bounded from `monitor + 1` through 100;
- Auto-pass is bounded from 0 through `monitor - 1`;
- the instruction mentions dragging, arrow keys, and exact score entry.

For the unavailable state, mock a failed settings query and assert `Retry` invokes `refetch` and `Back to Aethria` invokes the existing back navigation.

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
```

Expected: tests fail because exact numeric entry and unavailable-state recovery are missing.

**Step 2: Add exact numeric controls beneath the visual threshold bar**

Reuse the repository’s existing `ScoreInput` styling or extract it locally if it was removed by Fable. Render:

```tsx
<ScoreInput
  label="Monitor starts at"
  value={monitorThreshold}
  min={2}
  max={investThreshold - 1}
  onChange={setMonitorThreshold}
/>
<ScoreInput
  label="Invest starts at"
  value={investThreshold}
  min={monitorThreshold + 1}
  max={100}
  onChange={setInvestThreshold}
/>
<ScoreInput
  label="Auto-pass below"
  value={autoPassThreshold}
  min={0}
  max={monitorThreshold - 1}
  onChange={setAutoPassThreshold}
/>
```

Use the actual prop and field names already defined in the component; do not create a second state model. The visible instruction is:

> Drag a marker, use arrow keys, or enter an exact score.

Maintain the threshold ordering invariant in both slider and numeric paths.

**Step 3: Raise functional typography and contrast**

Audit the touched settings components for `text-[9px]`, `text-[10px]`, and very faint utility colors. For labels, statuses, instructions, limits, and navigation metadata:

- use at least `text-xs`/12px;
- prefer `text-oxford/70` or stronger on paper surfaces;
- preserve the editorial hierarchy by changing spacing and weight, not by shrinking essential text;
- retain smaller decorative marks only when they convey no required information.

Verify switches keep the existing rounded visual language and clear on/off labels.

**Step 4: Add actionable unavailable-state recovery**

In the settings-query unavailable state, render:

- `Retry`, which calls `settingsQuery.refetch()` and shows disabled/busy feedback while refetching;
- `Back to Aethria`, which uses the same navigation callback as the top-bar Back action but does not need a draft warning because no editable configuration loaded.

Keep the message plain: what could not load, and what the user can do next.

**Step 5: Run tests and commit**

Run:

```bash
cd app-front-end
npm test -- --run src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git diff --check
git add src/settings/DecisionThresholdsPanel.tsx src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/settings/SettingsPage.tsx src/settings/SettingsTopBar.tsx src/settings/SettingsRail.tsx src/settings/SettingsMobileNav.tsx src/settings/OperationsStrip.tsx src/settings/__tests__/settingsRoomLayout.test.ts
git commit -m "fix(settings): restore precision and readability"
```

Expected: threshold edits support both fast visual adjustment and exact entry; all unavailable states provide a next action.

---

### Task 6: Verify the complete settings correction

**Files:**
- Verify all changed frontend settings files
- Do not modify unrelated dirty files merely to make verification clean

**Step 1: Run the complete frontend test suite**

Run:

```bash
cd app-front-end
npm test -- --run
```

Expected: all tests pass with zero failures.

**Step 2: Run static checks and production build**

Inspect `app-front-end/package.json` for the exact available scripts, then run the repository-defined lint/typecheck commands and build. At minimum:

```bash
cd app-front-end
npm run lint
npm run build
```

If a separate typecheck script exists, run it as well. Expected: zero errors. Record any pre-existing warning separately rather than misreporting it as introduced by this work.

**Step 3: Perform a focused browser verification**

Start the existing frontend development server and verify these paths in the browser at desktop and mobile widths:

1. Desktop rail and mobile select have identical grouped order.
2. Policy copy says deployment is required; runtime copy says saves immediately.
3. Restoring defaults requires confirmation, creates a draft, and Undo restores the prior draft.
4. Leaving with a draft requires confirmation; leaving without a draft does not.
5. Deploy feedback stays visible in the fixed top bar.
6. Invalid deployment scrolls and focuses the correct section.
7. Thresholds work by drag, keyboard, and exact input.
8. Retry and Back are available when settings fail to load.
9. Mobile actions wrap without overlap and remain at least 44px tall.
10. Functional labels remain readable without relying on hover.

Capture screenshots only if they materially help compare desktop/mobile results; do not add generated screenshots to git unless the repository already tracks the relevant screenshot fixture.

**Step 4: Audit the final diff and dirty tree**

Run:

```bash
git diff --check
git status --short
git log --oneline -6
```

Expected: the settings implementation is committed in focused commits. The only remaining dirty paths should be unrelated pre-existing user work such as:

```text
app-front-end/src/components/SystemBar.tsx
app-front-end/src/pages/PortfolioPage.tsx
.impeccable/critique/
```

If additional settings files are dirty, inspect and either commit the intentional change to the appropriate task commit or report why it remains.

**Step 5: Report the outcome**

Summarize:

- the corrected persistence model;
- safe restore/leave behavior;
- mobile navigation and fixed feedback;
- threshold/readability/recovery improvements;
- exact test, lint, typecheck, build, and browser-verification results;
- untouched unrelated user changes.
