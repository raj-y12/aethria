# App-Wide Memo-Calibrated Mono Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the memo's Space Mono sizing, colour, spacing, line-height, weight, and numeric treatment the shared utility language across every Aethria frontend surface.

**Architecture:** Define five canonical mono roles in the global type utilities and TypeScript token source, then migrate shared class bundles before individual routes. Preserve Playfair display type and Figtree body copy, semantic status colours, component geometry, and the memo's local stylesheet.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, global CSS utilities, Vitest, Testing Library, Vite.

## Global Constraints

- Preserve Playfair Display, Figtree Variable, and Space Mono.
- Mono Label: `10px`, `1.45`, `400`, `0.09em`, uppercase, Oxford `42%`.
- Mono Metadata: `11px`, `1.5`, `400`, `0.04em`, Oxford `52%`.
- Mono Data: `13px`, `1.35`, `600`, `-0.015em`, tabular numerals, Oxford `82%`.
- Mono Status: `10px`, `1.4`, `600`, `0.075em`, uppercase, Oxford `62%`.
- Mono Action: `10px`, `1.4`, `400`, `0.075em`, uppercase, Oxford `72%`.
- Keep body copy, company names, and explanatory hints in Figtree; keep editorial headings in Playfair.
- Keep semantic status colours and minimum interactive target sizes.
- Do not broadly target `.memoPanel`; its local typography remains authoritative.
- Preserve the user's unrelated edits in `app-front-end/src/components/queue/DocketCaseRow.tsx` and `app-front-end/src/design-system/density.ts`.

---

## File Map

- Create `app-front-end/src/design-system/__tests__/typographyRoles.test.ts`: exact regression contract for the five CSS roles.
- Modify `app-front-end/src/index.css`: canonical role utilities and inverse modifiers.
- Modify `app-front-end/src/design-system/tokens.ts`: matching TypeScript values.
- Modify `app-front-end/src/design-system/ui-text.ts`, `railEditorial.ts`, `productSystem.tsx`, `verdictBadgeTokens.ts`, and `clerk-appearance.ts`: shared component contracts.
- Modify shared shell/components: `AppSpine.tsx`, `SystemBar.tsx`, `AccountRailPanel.tsx`, `AgentDispatch.tsx`, `DecisionStage.tsx`, `WorkGrid.tsx`, `system/internals.tsx`, and `queue/DocketMarginColumn.tsx` where shared roles do not already cover the output.
- Modify pages/surfaces: `HomePage.tsx`, `FlowPage.tsx`, `PortfolioPage.tsx`, `FundPage.tsx`, `SettingsPage.tsx`, `DecisionThresholdsPanel.tsx`, `LoginPage.tsx`, `AdminLoginPage.tsx`, and `AdminDashboardPage.tsx`.
- Do not modify `InvestmentMemoContent.css`, `DocketCaseRow.tsx`, or `density.ts`.

### Task 1: Canonical typography roles

**Files:**
- Create: `app-front-end/src/design-system/__tests__/typographyRoles.test.ts`
- Modify: `app-front-end/src/index.css`
- Modify: `app-front-end/src/design-system/tokens.ts`

**Interfaces:**
- Produces CSS classes: `.type-label-section`, `.type-label-tab`, `.type-meta`, `.type-data`, `.type-status`, `.type-action`, `.type-label-inverse`, `.type-meta-inverse`, `.type-data-inverse`, `.type-status-inverse`, and `.type-action-inverse`.
- Produces TypeScript token keys: `tokens.type.labelSection`, `labelTab`, `meta`, `data`, `status`, and `action`.

- [ ] **Step 1: Write the failing role-contract test**

Import `../../index.css?raw` and `tokens`, then assert the exact role definitions:

```ts
expect(css).toMatch(/\.type-label-section[\s\S]*font-size:\s*10px/);
expect(css).toMatch(/\.type-meta[\s\S]*font-size:\s*11px/);
expect(css).toMatch(/\.type-data[\s\S]*font-size:\s*13px/);
expect(css).toMatch(/\.type-status[\s\S]*font-size:\s*10px/);
expect(css).toMatch(/\.type-action[\s\S]*font-size:\s*10px/);
expect(tokens.type.data).toEqual({
  size: '13px', lineHeight: 1.35, letterSpacing: '-0.015em', fontWeight: 600,
  font: 'mono', tabular: true,
});
```

- [ ] **Step 2: Run the test and verify red**

```bash
cd app-front-end && npm test -- --run src/design-system/__tests__/typographyRoles.test.ts
```

Expected: FAIL because status/action utilities do not exist and existing sizes differ.

- [ ] **Step 3: Implement the six TypeScript role tokens**

Set the exact values from Global Constraints. Keep `labelTab` as an alias-equivalent label role so existing callers migrate without a breaking rename.

- [ ] **Step 4: Implement the CSS role utilities**

Use `var(--font-mono)` and explicit properties. Role utilities include their default Oxford colours. Inverse utilities override colour only, using `rgba(var(--color-paper-rgb), …)`.

- [ ] **Step 5: Verify green and build**

```bash
cd app-front-end && npm test -- --run src/design-system/__tests__/typographyRoles.test.ts && npm run build
```

Expected: PASS and build exit 0.

- [ ] **Step 6: Commit**

```bash
git add app-front-end/src/index.css app-front-end/src/design-system/tokens.ts app-front-end/src/design-system/__tests__/typographyRoles.test.ts
git commit -m "feat(front): define memo-calibrated mono roles"
```

### Task 2: Shared design-system class contracts

**Files:**
- Modify: `app-front-end/src/design-system/ui-text.ts`
- Modify: `app-front-end/src/design-system/railEditorial.ts`
- Modify: `app-front-end/src/design-system/productSystem.tsx`
- Modify: `app-front-end/src/design-system/verdictBadgeTokens.ts`
- Modify: `app-front-end/src/design-system/clerk-appearance.ts`

**Interfaces:**
- Consumes: Task 1 role utilities and TypeScript tokens.
- Produces: shared class bundles used by queue, panels, rails, settings, Clerk, and badges.

- [ ] **Step 1: Migrate shared labels and actions**

Replace repeated arbitrary mono strings with:

```ts
export const UI_DENSE_MONO_UPPER = 'type-action';
export const UI_FILTER_TOOLBAR_LABEL = 'type-label-section';
export const UI_PANEL_CHROME_LABEL = 'type-label-section';
export const UI_FILTER_SEGMENT_INACTIVE = 'type-action';
```

Keep component-specific selected/semantic colour classes at the call site.

- [ ] **Step 2: Migrate rail and product bundles**

Map `railEditorial.label` → `type-label-section`, `meta` → `type-meta`, `statusLabel` → `type-status`, and the base of `statValue` → `type-data` while retaining its responsive size override. Map `productInteraction.action`, `panelAction`, and `panelActionInline` to `type-action`.

- [ ] **Step 3: Migrate badges and Clerk**

Set verdict chips to `type-status` while retaining semantic fill, minimum width, and padding. Set Clerk action buttons from `tokens.type.action`; keep Clerk body fields in Figtree.

- [ ] **Step 4: Run tests, lint, and build**

```bash
cd app-front-end && npm test && npm run lint && npm run build
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add app-front-end/src/design-system
git commit -m "refactor(front): align shared UI with mono roles"
```

### Task 3: Shared shell and operational components

**Files:**
- Modify: `app-front-end/src/components/AppSpine.tsx`
- Modify: `app-front-end/src/components/SystemBar.tsx`
- Modify: `app-front-end/src/components/AccountRailPanel.tsx`
- Modify: `app-front-end/src/components/AgentDispatch.tsx`
- Modify: `app-front-end/src/components/DecisionStage.tsx`
- Modify: `app-front-end/src/components/WorkGrid.tsx`
- Modify: `app-front-end/src/components/system/internals.tsx`
- Modify: `app-front-end/src/components/queue/DocketMarginColumn.tsx`

**Interfaces:**
- Consumes: Task 1 utilities and Task 2 bundles.
- Produces: consistent mono labels, metadata, data, statuses, actions, and inverse shell typography.

- [ ] **Step 1: Migrate the dark shell**

Map AppSpine/SystemBar headings to `type-label-section type-label-inverse`, supporting time/user detail to `type-meta type-meta-inverse`, counts to `type-data type-data-inverse`, pipeline state to `type-status type-status-inverse`, and navigation/actions to `type-action type-action-inverse`.

- [ ] **Step 2: Migrate operational components**

Map DecisionStage labels/status/data, AgentDispatch state/actions, WorkGrid toolbar actions, system metrics, and docket numbers to the corresponding roles. Preserve larger responsive numeric sizes by pairing `type-data` with the existing `text-[clamp(...)]` override.

- [ ] **Step 3: Verify no explanatory prose changed font family**

Inspect every edited diff and confirm narrative sentences retain `font-sans`, `type-body*`, or `type-note`.

- [ ] **Step 4: Run component tests and build**

```bash
cd app-front-end && npm test -- --run src/components src/design-system && npm run build
```

Expected: PASS and build exit 0.

- [ ] **Step 5: Commit**

```bash
git add app-front-end/src/components/AppSpine.tsx app-front-end/src/components/SystemBar.tsx app-front-end/src/components/AccountRailPanel.tsx app-front-end/src/components/AgentDispatch.tsx app-front-end/src/components/DecisionStage.tsx app-front-end/src/components/WorkGrid.tsx app-front-end/src/components/system/internals.tsx app-front-end/src/components/queue/DocketMarginColumn.tsx
git commit -m "refactor(front): apply mono roles to app shell"
```

### Task 4: Route and configuration surfaces

**Files:**
- Modify: `app-front-end/src/pages/HomePage.tsx`
- Modify: `app-front-end/src/pages/FlowPage.tsx`
- Modify: `app-front-end/src/pages/PortfolioPage.tsx`
- Modify: `app-front-end/src/pages/FundPage.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/DecisionThresholdsPanel.tsx`
- Modify: `app-front-end/src/components/LoginPage.tsx`
- Modify: `app-front-end/src/admin/AdminLoginPage.tsx`
- Modify: `app-front-end/src/admin/AdminDashboardPage.tsx`

**Interfaces:**
- Consumes: Task 1 utilities and Task 2 shared contracts.
- Produces: route-level typography consistent with the memo.

- [ ] **Step 1: Migrate Home, Flow, Portfolio, and Fund**

Use role utilities according to content meaning. Preserve hero, page headings, company names, and prose. Pair large score/count displays with `type-data` plus the existing responsive size.

- [ ] **Step 2: Migrate Settings**

Map field/section labels to Label, draft/live and validation state to Status, totals and numeric inputs to Data, navigation/save controls to Action, and short compact context to Metadata. Convert explanatory hint sentences from `type-meta` to `type-note` when they are prose.

- [ ] **Step 3: Migrate login, Clerk-adjacent, and admin surfaces**

Map form labels, buttons, status, IDs, dates, and numeric table values to roles. Preserve user names, instructions, and error explanations in Figtree body/note styles.

- [ ] **Step 4: Run full automated verification**

```bash
cd app-front-end && npm test && npm run lint && npm run build
```

Expected: all tests pass, lint reports zero warnings/errors, and build exits 0.

- [ ] **Step 5: Commit**

```bash
git add app-front-end/src/pages app-front-end/src/settings app-front-end/src/components/LoginPage.tsx app-front-end/src/admin
git commit -m "refactor(front): carry memo typography across routes"
```

### Task 5: Audit, responsive verification, and final gate

**Files:**
- Modify only files from Tasks 1–4 when an audit demonstrates an incorrect role.

**Interfaces:**
- Consumes: completed role system and migrated surfaces.
- Produces: evidence that arbitrary mono styling is eliminated or intentionally retained.

- [ ] **Step 1: Audit remaining arbitrary mono combinations**

```bash
cd app-front-end && rg -n "font-mono.*text-\\[|font-mono.*tracking-\\[|type-meta.*uppercase|type-meta.*tracking-\\[" src --glob '*.{tsx,ts}'
```

Classify each result. Keep only intentional large numeric overrides, raw code/identifier styling, or memo-local exceptions. Migrate every ordinary label, metadata, status, or action result.

- [ ] **Step 2: Verify role coverage by surface**

Inspect Home, Flow, Portfolio, Fund, Settings, system/dispatch, login, and admin markup. Confirm each has the appropriate role classes and no body sentence was converted to monospace.

- [ ] **Step 3: Run the final gate**

```bash
cd app-front-end && npm test && npm run lint && npm run build && git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 4: Inspect repository scope**

```bash
git status --short
git diff --stat HEAD~4
```

Expected: only typography-system files are committed; the user's `DocketCaseRow.tsx` and `density.ts` edits remain uncommitted and untouched.
