# Settings Fund-Room Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Settings as a standard Aethria room using the Fund page's shell, fixed chrome, tab treatment, and golden-ratio content composition while preserving all settings behavior.

**Architecture:** Extract a focused `SettingsRoomChrome` that composes the shared `RoomHeader`, deployment readouts/actions, `OperationsStrip`, and Fund-style tabs. Simplify `SettingsPage` to the same fixed-top/scrolling-body architecture as `FundPage`, remove its spine override, and recompose existing form controls into 61.8/38.2 room sections without changing data flow or deployment functions.

**Tech Stack:** React 18, TypeScript, TanStack Query, Framer Motion, Tailwind CSS, Vitest, React Testing Library.

## Global Constraints

- Reuse `workspaceLayout.shell`, `RoomHeader`, existing typography roles, and Fund tab classes.
- Keep Decision / Administration ownership unchanged.
- Keep pipeline controls above the tabs, visible on both tabs, and immediate-save.
- Keep draft deployment, validation, reset, and fund-thesis confirmation behavior unchanged.
- Remove the Settings-specific spine override and leave the normal application spine intact.
- Desktop pairs use `61.8fr / 38.2fr`; narrow screens stack primary before secondary.
- Do not modify the Fund page, backend APIs, `SystemBar.tsx`, or `PortfolioPage.tsx`.

---

### Task 1: Settings Room Chrome

**Files:**
- Create: `app-front-end/src/settings/SettingsRoomChrome.tsx`
- Create: `app-front-end/src/settings/__tests__/SettingsRoomChrome.test.tsx`

**Interfaces:**
- Consumes: `Settings`, `SettingsTab`, `PendingChange[]`, active thesis/policy labels, deploy/reset callbacks, and the existing `OperationsStrip` settings callback.
- Produces: default `SettingsRoomChrome` with props for the current room state and tab behavior.

- [ ] **Step 1: Write failing room-chrome tests**

Mock `OperationsStrip` to isolate the chrome. Render through a `QueryClientProvider` only if the mock is removed. Assert the shared room title, deployment readouts, deploy/reset actions, and Fund-style tab semantics.

```tsx
render(
  <SettingsRoomChrome
    activeTab="decision"
    settings={settings}
    storageUnavailable={false}
    pendingChanges={[{ label: 'Mandate', stages: 'Scout · Reviewer' }]}
    saving={false}
    thesisVersion="Fund Thesis v5"
    policyVersion="policy-v4"
    onSettingsChange={vi.fn()}
    onTabChange={vi.fn()}
    onTabKeyDown={vi.fn()}
    onDeploy={vi.fn()}
    onReset={vi.fn()}
  />,
);

expect(screen.getByRole('heading', { name: /^settings\.$/i })).toBeInTheDocument();
expect(screen.getByText('The operating model')).toBeInTheDocument();
expect(screen.getByText('Draft')).toBeInTheDocument();
expect(screen.getByText('1 pending')).toBeInTheDocument();
expect(screen.getByRole('tab', { name: 'Decision' })).toHaveAttribute('aria-selected', 'true');
expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeEnabled();
```

Also assert a live state disables deployment, Administration selection is accessible, reset remains available, and the operations strip is present above the tabs.

- [ ] **Step 2: Run the chrome test and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/SettingsRoomChrome.test.tsx`

Expected: FAIL because `SettingsRoomChrome` does not exist.

- [ ] **Step 3: Implement `SettingsRoomChrome` with Fund primitives**

Define the exact props and private readout component:

```tsx
interface SettingsRoomChromeProps {
  activeTab: SettingsTab;
  settings: Settings;
  storageUnavailable: boolean;
  pendingChanges: PendingChange[];
  saving: boolean;
  thesisVersion: string;
  policyVersion: string;
  onSettingsChange: (settings: Settings) => void;
  onTabChange: (tab: SettingsTab) => void;
  onTabKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  onDeploy: () => void;
  onReset: () => void;
}
```

Render `RoomHeader` with eyebrow `The operating model`, title `Settings`, and concise draft/immediate-save copy. Its right readouts show Live/Draft, pending count, thesis version, and policy version, followed by square **Deploy changes** and quiet **Reset** actions. Render `OperationsStrip` next. Render Decision/Administration tabs using `FundFacetNav` classes: `type-label-tab`, one-pixel bottom border, quiet inactive Oxford text, horizontal overflow, and existing ARIA/keyboard wiring.

- [ ] **Step 4: Run chrome tests and lint for GREEN**

Run: `cd app-front-end && npm test -- src/settings/__tests__/SettingsRoomChrome.test.tsx && npx eslint src/settings/SettingsRoomChrome.tsx src/settings/__tests__/SettingsRoomChrome.test.tsx --max-warnings 0`

Expected: all room-chrome tests pass and ESLint exits 0.

- [ ] **Step 5: Commit the room chrome**

```bash
git add app-front-end/src/settings/SettingsRoomChrome.tsx app-front-end/src/settings/__tests__/SettingsRoomChrome.test.tsx
git commit -m "feat(settings): add fund-style room chrome"
```

### Task 2: Standard Room Shell and Normal Spine

**Files:**
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Create: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`

**Interfaces:**
- Consumes: `SettingsRoomChrome` from Task 1 and `workspaceLayout`.
- Produces: Settings page with fixed top chrome, one scrolling body, and no `setSpineOverride` behavior.

- [ ] **Step 1: Write a failing room-layout contract test**

Read the Settings source as a contract, matching the existing design-system source tests. Assert use of the shared room shell and chrome and absence of the old custom spine API.

```ts
const source = readFileSync(resolve(process.cwd(), 'src/settings/SettingsPage.tsx'), 'utf8');

expect(source).toContain("import { workspaceLayout } from '../design-system/workspaceLayout'");
expect(source).toContain('<SettingsRoomChrome');
expect(source).toContain('className="flex-none bg-paper"');
expect(source).toContain('ref={contentScrollRef}');
expect(source).not.toContain('setSpineOverride');
expect(source).not.toContain('SpineNavButton');
```

- [ ] **Step 2: Run the layout contract and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsRoomLayout.test.ts`

Expected: FAIL because Settings still owns custom spine chrome and does not import `workspaceLayout`.

- [ ] **Step 3: Replace the old frame with the Fund room shell**

Remove `useNavigate`, `useAppFrame`, `SpineNavButton`, `SETTINGS_SECTIONS`, `tabForSection`, `SectionId`, active-section state, intersection observation, spine refs, and both spine effects. Keep the tab state and keyboard handler.

Use this structural hierarchy:

```tsx
<div className="page-transition-enter flex min-h-0 flex-1 flex-col overflow-hidden bg-paper text-oxford">
  <div className="flex-none bg-paper">
    <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop}`}>
      <SettingsRoomChrome {...roomChromeProps} />
    </div>
  </div>
  <div ref={contentScrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper">
    <main className={`${workspaceLayout.shell} ${workspaceLayout.pageBottom} pt-phi-3`}>
      <div id={`settings-panel-${activeTab}`} role="tabpanel" aria-labelledby={`settings-tab-${activeTab}`}>
        {tabContent}
      </div>
    </main>
  </div>
  <FundThesisConfirmationModal {...confirmationProps} />
</div>
```

Pass `requestDeploy`, `handleReset`, current versions, pending changes, and operations props into `SettingsRoomChrome`. Keep validation/status messages at the top of the scrolling body in a compact accessible register.

- [ ] **Step 4: Run layout/chrome/settings tests and lint**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsRoomLayout.test.ts src/settings/__tests__/SettingsRoomChrome.test.tsx src/settings/__tests__/settingsNavigation.test.ts src/settings/__tests__/OperationsStrip.test.tsx && npx eslint src/settings/SettingsPage.tsx src/settings/__tests__/settingsRoomLayout.test.ts --max-warnings 0`

Expected: all focused tests pass and ESLint exits 0.

- [ ] **Step 5: Commit the room shell migration**

```bash
git add app-front-end/src/settings/SettingsPage.tsx app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts
git commit -m "refactor(settings): use standard fund room shell"
```

### Task 3: Golden-Ratio Tab Composition

**Files:**
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts`

**Interfaces:**
- Consumes: existing field/toggle/threshold components and the room body from Task 2.
- Produces: Decision and Administration bodies composed with Fund-style 61.8/38.2 sections and sparse specification rows.

- [ ] **Step 1: Extend the layout contract with composition assertions**

```ts
expect(source).toContain('lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]');
expect(source).toContain('The mandate');
expect(source).toContain('Decision mechanics');
expect(source).toContain('Scoring weights');
expect(source).toContain('Memo output');
expect(source).toContain('Ruling workflow');
expect(source).toContain('Cost budget');
expect(source).toContain('System state');
```

Assert the old repeated `SettingsSection` component is absent after the recompose.

- [ ] **Step 2: Run the composition contract and verify RED**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsRoomLayout.test.ts`

Expected: FAIL because the current tab bodies remain a one-column settings ledger.

- [ ] **Step 3: Recompose Decision without changing its handlers**

Replace `SettingsSection` with a private `RoomSection` matching Fund's `TabSection` rhythm: compact title/label row, `px-phi-4 pt-phi-5 pb-phi-5`, and no card wrapper.

Decision renders:

1. `lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]` for **The mandate** editor and **Version context**.
2. The same split for **Decision thresholds** and **Escalation sensitivity**.
3. Full-width **Scoring weights** ledger with subtle `border-t border-oxford/[0.06]` rows.

Use Fund-style specification rows for mandate controls: `grid-cols-[clamp(110px,18%,160px)_minmax(0,1fr)]`, mono labels, body values, and one subtle top rule per row. Keep every current `updateMandate`, `updateThreshold`, and `updateRisk` call unchanged.

- [ ] **Step 4: Recompose Administration without changing its handlers**

Render two golden-ratio pairs:

1. **Memo output** primary / **Ruling workflow** secondary.
2. **Cost budget** primary / **System state** secondary.

Keep memo selects, memo toggles, risk toggles, budget values, status values, and immediate budget-enforcement explanation unchanged. Remove card-like wrappers and use sparse rows.

- [ ] **Step 5: Run focused tests, lint, and build**

Run: `cd app-front-end && npm test -- src/settings/__tests__/settingsRoomLayout.test.ts src/settings/__tests__/SettingsRoomChrome.test.tsx src/settings/__tests__/DecisionThresholdsPanel.test.tsx src/settings/__tests__/deploymentConfirmation.test.ts src/settings/__tests__/FundThesisConfirmationModal.test.tsx && npm run lint && npm run build`

Expected: focused tests pass, ESLint exits 0, and the production build succeeds.

- [ ] **Step 6: Commit the tab composition**

```bash
git add app-front-end/src/settings/SettingsPage.tsx app-front-end/src/settings/__tests__/settingsRoomLayout.test.ts
git commit -m "style(settings): match fund room composition"
```

### Task 4: Full Verification and Workspace Audit

**Files:**
- Verify only; no expected source edits.

**Interfaces:**
- Consumes: complete Settings Fund-room implementation.
- Produces: fresh test/build evidence and a clean feature handoff on `main`.

- [ ] **Step 1: Run all frontend tests**

Run: `cd app-front-end && npm test`

Expected: every Vitest test passes with zero failures.

- [ ] **Step 2: Run lint and production build**

Run: `cd app-front-end && npm run lint && npm run build`

Expected: ESLint exits 0 and TypeScript/Vite build succeeds.

- [ ] **Step 3: Audit repository state**

Run: `git diff --check && git status --short && git log --oneline -10`

Expected: feature changes are committed on `main`; only the user's pre-existing `SystemBar.tsx` and `PortfolioPage.tsx` edits remain uncommitted.
