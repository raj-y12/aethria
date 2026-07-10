# Product UI Recalibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recalibrate Aethria into a legible, evidence-first investment operating system with an action-center spine, clearer navigation, faster interactions, and coherent decision and publication workflows.

**Architecture:** Preserve existing routes, API clients, query ownership, and backend investment behavior. Introduce pure presentation models at system boundaries, then refactor focused UI components around those models so desktop and mobile share the same semantics. Each task is independently testable and committed before the next begins.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3.4, TanStack Query 5, React Router 7, Framer Motion 10, Vitest, Testing Library, Playwright.

## Global Constraints

- Every storage read and API call remains user-scoped through existing authenticated clients.
- No direct `fetch` calls outside `src/api/`.
- Preserve `/v1`, `/v1/flow`, `/v1/portfolio`, `/v1/fund`, `/v1/settings`, deep links, and keyboard shortcuts.
- Meaningful text on paper must meet WCAG AA and use at least Oxford at 60% opacity; operational labels generally use 11–12px, with compact 11px navigation permitted at sufficient contrast.
- Structural rules use Oxford 12–16% on paper and white 12–18% on Oxford.
- Primary touch targets are at least 44px where practical.
- Product interaction transitions target 150–200ms and respect reduced motion.
- Keep Oxford/paper, square geometry, verdict colors, escalation semantics, and Playfair only for intentional editorial moments.
- Do not add dependencies or change backend investment logic.
- Run focused tests red→green before each implementation commit.

---

### Task 1: Reliable action-center state model

**Files:**
- Create: `app-front-end/src/lib/appChrome.ts`
- Create: `app-front-end/src/lib/__tests__/appChrome.test.ts`
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Modify: `app-front-end/src/components/AppSpine.tsx`

**Interfaces:**
- Consumes: `Settings['agent_config']`, agent status responses, loop status responses, `Startup[]`, `isDealHumanResolved`, `isDealUnresolved`.
- Produces: `PipelineState`, `ActionCenterModel`, `derivePipelineState()`, `countPendingRulings()`, `buildActionCenter()`.

- [ ] **Step 1: Write failing pure-model tests**

```ts
import { describe, expect, it } from 'vitest';
import { buildActionCenter, countPendingRulings, derivePipelineState } from '../appChrome';

describe('app chrome model', () => {
  it('counts unresolved human-review deals without relying on the Flow query', () => {
    const startups = [
      { partner: { human_review_required: true }, human_resolution: null },
      { partner: { human_review_required: true }, human_resolution: { decision: 'PASS' } },
    ] as never;
    expect(countPendingRulings(startups)).toBe(1);
  });

  it('builds an attention action that deep-links to the ruling queue', () => {
    expect(buildActionCenter(3, 8)).toEqual({
      mode: 'attention',
      heading: 'Needs your attention',
      primaryValue: '3',
      supportingLabel: 'Deals need ruling',
      actionLabel: 'Review queue',
      href: '/v1/flow?queue=escalated',
    });
  });

  it('builds a quiet clear state', () => {
    expect(buildActionCenter(0, 8)).toMatchObject({
      mode: 'clear',
      heading: 'Desk clear',
      primaryValue: '8',
      href: '/v1/flow',
    });
  });

  it('prioritizes Issue over Live and Off', () => {
    expect(derivePipelineState({ enabled: true, healthIssue: true, stopping: false, loopAlive: true })).toBe('Issue');
  });
});
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/appChrome.test.ts`  
Expected: FAIL because `appChrome.ts` does not exist.

- [ ] **Step 3: Implement the pure model**

```ts
import type { Startup } from '../types/startup';
import { isDealHumanResolved, isDealUnresolved } from './dealState';

export type PipelineState = 'Live' | 'Idle' | 'Off' | 'Issue' | 'Stopping';

export interface ActionCenterModel {
  mode: 'attention' | 'clear';
  heading: string;
  primaryValue: string;
  supportingLabel: string;
  actionLabel: string;
  href: string;
}

export function countPendingRulings(startups: Startup[]): number {
  return startups.filter((startup) => startup.partner?.human_review_required && !isDealHumanResolved(startup)).length;
}

export function countOpenDeals(startups: Startup[]): number {
  return startups.filter(isDealUnresolved).length;
}

export function derivePipelineState(input: {
  enabled: boolean;
  healthIssue: boolean;
  stopping: boolean;
  loopAlive: boolean;
}): PipelineState {
  if (!input.enabled) return 'Off';
  if (input.healthIssue) return 'Issue';
  if (input.stopping) return 'Stopping';
  return input.loopAlive ? 'Live' : 'Idle';
}

export function buildActionCenter(pendingRulings: number, openDeals: number): ActionCenterModel {
  return pendingRulings > 0
    ? {
        mode: 'attention',
        heading: 'Needs your attention',
        primaryValue: pendingRulings.toLocaleString(),
        supportingLabel: 'Deals need ruling',
        actionLabel: 'Review queue',
        href: '/v1/flow?queue=escalated',
      }
    : {
        mode: 'clear',
        heading: 'Desk clear',
        primaryValue: openDeals.toLocaleString(),
        supportingLabel: openDeals === 1 ? 'Open deal' : 'Open deals',
        actionLabel: 'Open deals',
        href: '/v1/flow',
      };
}
```

- [ ] **Step 4: Integrate the model into `AppFrame` without changing presentation yet**

Replace Flow-query-derived pending counts with `countPendingRulings(startups)`, derive the pipeline state through `derivePipelineState`, and pass `buildActionCenter(pendingRulings, openDeals)` to `AppSpine`. Remove the Fund-thesis summary query and mandate mapping from `AppFrame`; Fund owns mandate information.

- [ ] **Step 5: Run focused and regression tests**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/appChrome.test.ts tests/stream-health.test.ts`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app-front-end/src/lib/appChrome.ts app-front-end/src/lib/__tests__/appChrome.test.ts app-front-end/src/components/AppFrame.tsx app-front-end/src/components/AppSpine.tsx
git commit -m "fix(front): derive reliable action center state"
```

### Task 2: Action-center spine, preserved navigation rhythm, and account disclosure

**Files:**
- Create: `app-front-end/src/components/SpineAttentionAction.tsx`
- Create: `app-front-end/src/components/SpinePipelineStatus.tsx`
- Create: `app-front-end/src/components/AccountDisclosure.tsx`
- Create: `app-front-end/src/components/__tests__/AppSpine.test.tsx`
- Create: `app-front-end/src/components/__tests__/AccountDisclosure.test.tsx`
- Modify: `app-front-end/src/components/AppSpine.tsx`
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Modify: `app-front-end/src/components/MobileHeader.tsx`
- Modify: `app-front-end/src/components/SystemBar.tsx`

**Interfaces:**
- Consumes: `ActionCenterModel`, `PipelineState`, React Router navigation, `useAgentLogoutFlow`.
- Produces: `SpineAttentionAction`, `SpinePipelineStatus`, `AccountDisclosure`, and restored pre-audit workspace navigation styling.

- [ ] **Step 1: Write failing component tests**

```tsx
it('renders one full-region attention action and no mandate slab', () => {
  renderSpine({ action: buildActionCenter(3, 8), pipelineState: 'Live' });
  expect(screen.getByRole('link', { name: /3 deals need ruling review queue/i })).toHaveAttribute(
    'href',
    '/v1/flow?queue=escalated',
  );
  expect(screen.queryByText(/mandate/i)).not.toBeInTheDocument();
});

it('makes a pipeline issue actionable', () => {
  renderSpine({ action: buildActionCenter(0, 8), pipelineState: 'Issue' });
  expect(screen.getByRole('link', { name: /pipeline needs attention/i })).toHaveAttribute('href', '/v1/settings');
});

it('opens account actions and restores trigger focus on Escape', async () => {
  render(<AccountDisclosure surface="oxford" />);
  const trigger = screen.getByRole('button', { name: /account/i });
  await user.click(trigger);
  expect(screen.getByRole('menu')).toBeVisible();
  await user.keyboard('{Escape}');
  expect(trigger).toHaveFocus();
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/AppSpine.test.tsx src/components/__tests__/AccountDisclosure.test.tsx`  
Expected: FAIL because the new components do not exist.

- [ ] **Step 3: Implement focused components**

`SpineAttentionAction` renders one Router `Link` whose accessible name combines value, supporting label, and action. `SpinePipelineStatus` renders ambient text for Live/Idle/Off/Stopping and a Settings link for Issue. `AccountDisclosure` uses `aria-haspopup="menu"`, `aria-expanded`, Escape dismissal, outside-pointer dismissal, focus restoration, Settings, and Log out.

```ts
export interface AccountDisclosureProps {
  surface: 'paper' | 'oxford';
  settingsPath?: string;
  align?: 'start' | 'end';
}
```

- [ ] **Step 4: Replace only the lower spine slab and restore the old workspace buttons**

Keep the familiar Home, Flow, Portfolio, Fund, and Dispatch labels. Remove every `sublabel` prop and restore the original single-line `SpineNavButton` markup, height, padding, and shortcut presentation. Restore `.aethria-spine` to `width: clamp(204px, 15vw, 248px)`. Keep routes and shortcut values `1`–`4` and `⌘K`. Remove `SpineMandate`, `SpineReadout`, mandate props, total/new counts, scattered Settings/Log out fragments, and decorative separators. Do not alter the top navigation's established visual rhythm while rebuilding the lower action center.

- [ ] **Step 5: Update mobile menu semantics**

Add `menuOpen`, `aria-expanded`, and an attention action to `MobileHeader`. Keep every menu row at least 44px high and use Home, Flow, Portfolio, Fund, and Dispatch consistently.

- [ ] **Step 6: Run tests and commit**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/AppSpine.test.tsx src/components/__tests__/AccountDisclosure.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/components app-front-end/src/components/SystemBar.tsx
git commit -m "feat(front): replace spine telemetry with action center"
```

### Task 3: Global legibility, motion baseline, error copy, and Today

**Files:**
- Create: `app-front-end/src/lib/todayBrief.ts`
- Create: `app-front-end/src/lib/__tests__/todayBrief.test.ts`
- Create: `app-front-end/src/pages/__tests__/HomePage.test.tsx`
- Modify: `app-front-end/src/design-system/tokens.ts`
- Modify: `app-front-end/tailwind.config.js`
- Modify: `app-front-end/src/design-system/productSystem.tsx`
- Modify: `app-front-end/src/index.css`
- Modify: `app-front-end/src/components/Reveal.tsx`
- Modify: `app-front-end/src/components/AppFrame.tsx`
- Modify: `app-front-end/src/components/ErrorBoundary.tsx`
- Modify: `app-front-end/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: `SystemData`, `ActionCenterModel`, existing attention helpers.
- Produces: `buildTodayBrief()` and canonical readable design tokens.

- [ ] **Step 1: Write failing Today model and component tests**

```ts
it('sends urgent work directly to the escalated queue', () => {
  expect(buildTodayBrief({ pendingRulings: 2, newCount: 1, openCount: 3 })).toMatchObject({
    headline: '2 matters await your ruling.',
    dealsHref: '/v1/flow?queue=escalated',
    dealsAction: 'Review deals',
  });
});

it('keeps the desk-clear state calm', () => {
  expect(buildTodayBrief({ pendingRulings: 0, newCount: 0, openCount: 0 }).headline).toBe('The desk is clear.');
});
```

- [ ] **Step 2: Implement `buildTodayBrief` and refactor `HomePage`**

Remove `HomeDoor.numeral`, Roman numerals, per-item motion delays, fund/operator footer fragments, and mandate metadata. Make the desk band explicitly say Review deals and deep-link to the escalated queue when necessary. Footer contains Search company, Settings, and `AccountDisclosure`.

- [ ] **Step 3: Correct contrast and borders without globally inflating density**

Keep compact navigation and short metadata at the established 11px scale where they fit and meet contrast; use 12–14px for operational descriptions and body content. Raise semantic hairline to 12% and strong hairline to 16%. Update shared product text to `/60` or stronger for meaningful content. Audit components by role rather than replacing every 10–11px token globally. Verify that denser labels still have adequate line-height and spacing before increasing their size.

- [ ] **Step 4: Remove repeated workspace choreography and sanitize shell errors**

Set standard chrome transitions to 150–200ms, render recurring workspace content immediately, and keep reduced-motion behavior. Replace the shell error with: “Deal data couldn’t refresh. Showing the latest available information.” Provide a Try again action without environment-variable, API URL, CORS, Supabase, or OpenAI terminology.

- [ ] **Step 5: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/todayBrief.test.ts src/pages/__tests__/HomePage.test.tsx src/components/__tests__/ErrorBoundary.test.tsx tests/login-entry-transition.test.ts`  
Expected: PASS.

```bash
git add app-front-end/src app-front-end/tailwind.config.js
git commit -m "refactor(front): establish readable product chrome"
```

### Task 4: Evidence-first decision model and brief

**Files:**
- Create: `app-front-end/src/lib/decisionBrief.ts`
- Create: `app-front-end/src/lib/__tests__/decisionBrief.test.ts`
- Create: `app-front-end/src/components/DecisionBrief.tsx`
- Create: `app-front-end/src/components/__tests__/DecisionBrief.test.tsx`
- Modify: `app-front-end/src/components/DecisionStage.tsx`
- Modify: `app-front-end/src/pages/FlowPage.tsx`

**Interfaces:**
- Consumes: `Startup`, `FundConfiguration`, `extractAdverseRegister` and existing scoring helpers.
- Produces: `DecisionSignal`, `DecisionBriefModel`, `buildDecisionBrief()`, `DecisionBrief`.

- [ ] **Step 1: Write failing derivation tests**

```ts
it('orders grounded evidence before model signals and removes duplicates', () => {
  const model = buildDecisionBrief(fixtureStartup, fixtureConfig);
  expect(model.decisiveEvidence[0]).toBe(fixtureStartup.partner!.decision_drivers![0]);
  expect(new Set(model.decisiveEvidence).size).toBe(model.decisiveEvidence.length);
  expect(model.signals.map((signal) => signal.key)).toEqual([
    'conviction',
    'thesis_fit',
    'reviewer_agreement',
    'partner_confidence',
  ]);
});
```

- [ ] **Step 2: Implement the model with explicit fallback order**

```ts
export interface DecisionSignal {
  key: 'conviction' | 'thesis_fit' | 'reviewer_agreement' | 'partner_confidence';
  label: string;
  reading: string;
  value?: number;
  tone?: 'default' | 'warning';
}

export interface DecisionBriefModel {
  companyName: string;
  metadata: string[];
  recommendation: string;
  attentionReason: string | null;
  whyNow: string | null;
  decisiveEvidence: string[];
  principalUncertainty: string[];
  changeTheCall: string[];
  signals: DecisionSignal[];
}
```

Evidence uses partner decision drivers first; uncertainty uses Aethria tension/focal question then adverse register; change-the-call uses next action then improvement/diligence actions. Never invent missing facts.

- [ ] **Step 3: Write and pass DOM-order tests**

Assert company/recommendation, Why now, Decisive evidence, Principal uncertainty, and What changes the call occur before the compact Model signals region. Assert conviction does not use a hero-size style or heading.

- [ ] **Step 4: Integrate the shared brief in desktop and mobile memo covers**

Keep `DecisionStage` as a compatibility wrapper during migration or replace its imports atomically. `FlowPage` and `InvestmentMemo` must receive the same brief model.

- [ ] **Step 5: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/decisionBrief.test.ts src/components/__tests__/DecisionBrief.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/lib/decisionBrief.ts app-front-end/src/lib/__tests__/decisionBrief.test.ts app-front-end/src/components/DecisionBrief.tsx app-front-end/src/components/__tests__/DecisionBrief.test.tsx app-front-end/src/components/DecisionStage.tsx app-front-end/src/pages/FlowPage.tsx
git commit -m "feat(front): make deal decisions evidence first"
```

### Task 5: Queue hierarchy, immediate selection, and sticky ruling controls

**Files:**
- Create: `app-front-end/src/components/memo/StickyRulingControls.tsx`
- Create: `app-front-end/src/components/memo/__tests__/StickyRulingControls.test.tsx`
- Create: `app-front-end/src/components/queue/__tests__/DocketCaseRow.test.tsx`
- Create: `app-front-end/src/components/__tests__/WorkGrid.test.tsx`
- Modify: `app-front-end/src/components/WorkGrid.tsx`
- Modify: `app-front-end/src/components/queue/DocketCaseRow.tsx`
- Modify: `app-front-end/src/components/queue/queueRowShared.ts`
- Modify: `app-front-end/src/components/queue/DecisionQueueHeader.tsx`
- Modify: `app-front-end/src/components/InvestmentMemoContent.tsx`
- Modify: `app-front-end/src/components/InvestmentMemoContent.css`
- Modify: `app-front-end/src/components/InvestmentMemo.tsx`

**Interfaces:**
- Consumes: existing ruling callbacks, risk gate, selected queue model, shared `DecisionBrief`.
- Produces: `StickyRulingControlsProps { mode, currentDecision, successMessage, ...existing ruling inputs }`.

- [ ] **Step 1: Write failing queue tests**

Assert no decorative row index, company first, visible attention reason, recommendation after reason, full-row selected treatment, accurate accessible label, immediate auto-selection, 44px filter controls, filter summary, reset, and arrow-key navigation.

- [ ] **Step 2: Remove queue delays and rebuild row hierarchy**

Delete `autoSelectReady`/`chromeSettled` timers and list stagger. Remove `displayIndex` from visible presentation. Preserve filtering, sorting, deep links, and selection callbacks.

- [ ] **Step 3: Write failing ruling-control tests**

Assert recommendation selection, five-character rationale gate, high-risk acknowledgement, saving state, inline failure, explicit success, current-decision copy, and mobile `sheet` mode.

- [ ] **Step 4: Extract and integrate sticky ruling controls**

Move the existing memo ruling behavior behind `StickyRulingControls`; retain `shouldGateRisk`, `buildOptimisticResolution`, and `resolveEscalation`. Place controls after the brief and before long memo sections. Add desktop sticky behavior and mobile safe-area padding. Remove memo reveal staggering.

- [ ] **Step 5: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/components/queue/__tests__/DocketCaseRow.test.tsx src/components/__tests__/WorkGrid.test.tsx src/components/memo/__tests__/StickyRulingControls.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/components app-front-end/src/pages/FlowPage.tsx
git commit -m "refactor(front): streamline deal queue and rulings"
```

### Task 6: Full-canvas Portfolio presentation

**Files:**
- Create: `app-front-end/src/lib/portfolioPresentation.ts`
- Create: `app-front-end/src/lib/__tests__/portfolioPresentation.test.ts`
- Create: `app-front-end/src/components/portfolio/PortfolioOverview.tsx`
- Create: `app-front-end/src/components/portfolio/PortfolioPositions.tsx`
- Create: `app-front-end/src/components/portfolio/PortfolioAttention.tsx`
- Create: `app-front-end/src/pages/__tests__/PortfolioPage.test.tsx`
- Modify: `app-front-end/src/pages/PortfolioPage.tsx`

**Interfaces:**
- Consumes: `SystemData`, `buildTrackRecord`, watchlist analytics, signals, concentration snapshot.
- Produces: `PortfolioOverviewModel`, `PortfolioPositionModel[]`, `PortfolioAttentionItem[]`.

- [ ] **Step 1: Write failing presentation-model tests**

Test position ordering, current concentration ordering, stale severity, watchlist reason fallback “Monitoring for new evidence,” signal consequence derivation, and omission of unavailable historical movement.

- [ ] **Step 2: Implement pure models**

```ts
export interface PortfolioOverviewModel {
  investCount: number;
  monitorCount: number;
  watchlistCount: number;
  pendingRulings: number;
  sectors: Array<{ label: string; count: number; percentage: number }>;
  updatedAt: string | null;
}
```

Do not fabricate exposure history; label concentration as current composition.

- [ ] **Step 3: Build focused presentation components**

Use positions as the dominant column and Watchlist + Signals as a dedicated attention column. Replace 1px animated concentration lines with readable fixed-scale bars and explicit values. Remove 0.9s stagger.

- [ ] **Step 4: Add route, empty-state, and responsive tests**

Assert deal links use `/v1/flow?open=<id>`, mobile section order is summary→positions→attention→composition, and empty states provide relevant next actions.

- [ ] **Step 5: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/portfolioPresentation.test.ts src/pages/__tests__/PortfolioPage.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/lib/portfolioPresentation.ts app-front-end/src/lib/__tests__/portfolioPresentation.test.ts app-front-end/src/components/portfolio app-front-end/src/pages/PortfolioPage.tsx app-front-end/src/pages/__tests__/PortfolioPage.test.tsx
git commit -m "refactor(front): use portfolio canvas for conviction and attention"
```

### Task 7: Clear Fund strategy facets and structured mandate

**Files:**
- Create: `app-front-end/src/components/__tests__/FundFacetNav.test.tsx`
- Create: `app-front-end/src/components/system/__tests__/InstitutionalMandateTab.test.tsx`
- Modify: `app-front-end/src/components/SystemIntelligence.tsx`
- Modify: `app-front-end/src/components/system/internals.tsx`
- Modify: `app-front-end/src/pages/FundPage.tsx`

**Interfaces:**
- Consumes: existing `FundFacetTab` keys and `FundThesisRuntime` data.
- Produces: user-facing labels Strategy, Decision record, Patterns, Calibration, Agent learning without changing tab keys.

- [ ] **Step 1: Write failing label/order tests**

Assert exact visible labels and order while callbacks still receive `thesis`, `decisions`, `analytics`, `calibration`, and `meta`.

- [ ] **Step 2: Write mandate-state tests**

Test structured facts, missing-value omission, live-version marker, history dates, loading, error, and empty states.

- [ ] **Step 3: Relabel facets and refine strategy composition**

Keep existing data contracts. Present mandate facts as scannable rows, version history as a clear live/previous list, and alignment/drift as secondary diagnostics.

- [ ] **Step 4: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/FundFacetNav.test.tsx src/components/system/__tests__/InstitutionalMandateTab.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/components/SystemIntelligence.tsx app-front-end/src/components/system app-front-end/src/components/__tests__/FundFacetNav.test.tsx app-front-end/src/pages/FundPage.tsx
git commit -m "refactor(front): clarify fund strategy workspace"
```

### Task 8: Settings change model and review/publish state machine

**Files:**
- Create: `app-front-end/src/lib/settingsChangeModel.ts`
- Create: `app-front-end/src/lib/__tests__/settingsChangeModel.test.ts`
- Create: `app-front-end/src/settings/SettingsChangeSummary.tsx`
- Create: `app-front-end/src/settings/SettingsPublishFlow.tsx`
- Create: `app-front-end/src/settings/__tests__/SettingsPublishFlow.test.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/api/settings.ts`

**Interfaces:**
- Consumes: existing serialized configuration, `previewPolicy`, `patchSettings`, `publishPolicy`.
- Produces: `SettingsChange`, `SettingsChangeModel`, `buildSettingsChangeModel()`, UI state `'edit' | 'review' | 'publishing' | 'success' | 'partial-failure'`.

- [ ] **Step 1: Confirm backend/API semantics before promising drafts**

Read the PATCH settings route and fund-thesis publication path. Record in code comments whether PATCH mutates live behavior. If it does, keep browser-local draft until Publish; do not label a live PATCH as Save draft.

- [ ] **Step 2: Write failing pure-model tests**

Test changed sections, affected pipeline stages, invalid weight totals, invalid decision bands, reset remaining dirty, and no-op models.

- [ ] **Step 3: Implement the pure model**

```ts
export interface SettingsChange {
  section: 'mandate' | 'memo' | 'ruling' | 'thresholds' | 'operations' | 'weights';
  label: string;
  affectedStages: Array<'Scout' | 'Reviewer' | 'Partner' | 'Portfolio'>;
}

export interface SettingsChangeModel {
  changes: SettingsChange[];
  errors: string[];
  canReview: boolean;
  canPublish: boolean;
}
```

- [ ] **Step 4: Write failing publication-flow tests**

Mock preview, PATCH, and publish. Test validation gating, review summary, success reconciliation, PATCH failure preserving draft, policy partial failure identifying completed steps, and retry.

- [ ] **Step 5: Implement Draft → Review effects → Publish**

Keep `SettingsPage` as draft owner. `SettingsChangeSummary` shows changed sections and affected stages. `SettingsPublishFlow` invokes preview before publication, then existing PATCH and publish calls in verified order, preserving the draft on failure.

- [ ] **Step 6: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/settingsChangeModel.test.ts src/settings/__tests__/SettingsPublishFlow.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/lib/settingsChangeModel.ts app-front-end/src/lib/__tests__/settingsChangeModel.test.ts app-front-end/src/settings app-front-end/src/api/settings.ts
git commit -m "feat(front): clarify settings review and publication"
```

### Task 9: Settings responsive navigation and order regression

**Files:**
- Create: `app-front-end/src/settings/__tests__/SettingsPage.test.tsx`
- Modify: `app-front-end/src/settings/SettingsPage.tsx`
- Modify: `app-front-end/src/settings/SettingsChangeSummary.tsx`

**Interfaces:**
- Consumes: the existing `sections` array, `activeSection`, `scrollToSection`, draft state.
- Produces: shared desktop/mobile section navigation with matching DOM order.

- [ ] **Step 1: Write failing responsive/order tests**

Assert headings occur in Mandate, Memo output, Ruling, Decision thresholds, Operations, Scoring weights order; mobile navigation uses the same order; changing sections retains draft input; each mobile target is 44px.

- [ ] **Step 2: Implement shared section navigation**

Drive desktop spine override and mobile horizontal/select navigation from the same array. Preserve the mounted Settings page and existing `IntersectionObserver` active-section behavior.

- [ ] **Step 3: Remove obsolete Deploy copy and verify change summary behavior**

Use Edit, Review effects, and Publish states consistently. Ensure reset changes values but remains dirty until publication or explicit discard.

- [ ] **Step 4: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/settings/__tests__/SettingsPage.test.tsx`  
Expected: PASS.

```bash
git add app-front-end/src/settings
git commit -m "refactor(front): make settings workflow responsive and ordered"
```

### Task 10: Search progress and operator-safe errors

**Files:**
- Modify: `app-front-end/src/lib/lookupFailure.ts`
- Modify: `app-front-end/src/lib/__tests__/lookupFailure.test.ts`
- Modify: `app-front-end/src/hooks/useDispatchLookup.ts`
- Modify: `app-front-end/src/components/DispatchCommandBar.tsx`
- Modify: `app-front-end/src/components/__tests__/DispatchCommandBar.test.tsx`
- Modify: `app-front-end/src/components/AgentDispatch.tsx`
- Modify: `app-front-end/src/components/CandidatePicker.tsx`

**Interfaces:**
- Consumes: existing lookup polling and progress state.
- Produces: `mapLookupFailureToOperatorMessage()` and consistent Identify/Review/Decide/Memo progress semantics.

- [ ] **Step 1: Write failing safe-error tests**

Assert raw messages containing `VITE_API_URL`, `CORS`, `SUPABASE`, stack text, or URLs become task-focused recovery copy and the raw detail is not rendered.

- [ ] **Step 2: Implement safe failure mapping**

```ts
export function mapLookupFailureToOperatorMessage(input: unknown): string {
  const text = typeof input === 'string' ? input.toLowerCase() : '';
  if (text.includes('timeout')) return 'The analysis took too long. Try again or refine the company website.';
  if (text.includes('not found') || text.includes('resolve')) return 'No confirmed company match was found. Refine the website or try another company.';
  return 'The analysis could not finish. Your search is saved; try again.';
}
```

- [ ] **Step 3: Normalize progress tests and UI**

Assert normal and rerun flows expose the applicable subset of Identify, Review, Decide, Memo with correct done/active/pending semantics. Keep background lookup persistence and chips unchanged.

- [ ] **Step 4: Remove ornamental reveals and apply legibility baseline**

Render progress immediately, retain only state transitions, and keep operator text at canonical size/contrast.

- [ ] **Step 5: Verify and commit**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/lookupFailure.test.ts src/components/__tests__/DispatchCommandBar.test.tsx src/lib/__tests__/lookupTracking.test.ts tests/dispatch-lookup-persistence.test.ts`  
Expected: PASS.

```bash
git add app-front-end/src/lib/lookupFailure.ts app-front-end/src/lib/__tests__/lookupFailure.test.ts app-front-end/src/hooks/useDispatchLookup.ts app-front-end/src/components
git commit -m "refactor(front): clarify company search progress and recovery"
```

### Task 11: End-to-end accessibility, responsive, and quality verification

**Files:**
- Modify: `app-front-end/e2e/smoke.spec.ts`
- Modify: `app-front-end/screenshot/shots.mjs`
- Modify: `app-front-end/UI_AUDIT.md`

**Interfaces:**
- Consumes: completed recalibrated UI.
- Produces: route-level regression coverage and current audit evidence.

- [ ] **Step 1: Add failing browser assertions**

Cover action-center navigation, Deals deep link and mobile decision takeover, sticky ruling action, Portfolio no-overflow, Fund labels, Settings section order/draft retention, Search close/reopen persistence, keyboard account disclosure, reduced motion, and 200% zoom.

- [ ] **Step 2: Run E2E and fix only demonstrated regressions**

Run: `cd app-front-end && npm run test:e2e`  
Expected: PASS with no primary-route horizontal overflow.

- [ ] **Step 3: Run static anti-pattern guards**

```bash
rg -n "VITE_|API_URL|CORS|SUPABASE|OPENAI_API_KEY" app-front-end/src --glob '*.{tsx,ts}'
rg -n "order-[1-9]" app-front-end/src/settings
rg -n "fetch\(" app-front-end/src --glob '*.{ts,tsx}' --glob '!api/**'
```

Expected: no operator-facing environment terminology, no Settings visual-order utilities, and no new direct API fetches outside `src/api/`.

- [ ] **Step 4: Run full verification**

Run:

```bash
cd app-front-end
npm test -- --run
npm run lint
npm run build
npm run test:e2e
```

Expected: all commands exit 0.

- [ ] **Step 5: Generate and inspect representative screenshots**

Capture Today, Deals, Portfolio, Fund strategy, Settings, and Search at 390×844, 1024×768, 1512×945, and a wide desktop. Verify hierarchy, text contrast, touch targets, empty states, long names, and reduced-motion state.

- [ ] **Step 6: Update audit and commit**

Update `UI_AUDIT.md` with the new architecture, verified accessibility floors, remaining limitations, and test evidence.

```bash
git add app-front-end/e2e/smoke.spec.ts app-front-end/screenshot/shots.mjs app-front-end/UI_AUDIT.md
git commit -m "test(front): verify product UI recalibration"
```

## Final completion gate

- [ ] Run `git status --short` and confirm only intentional files are present.
- [ ] Run the full frontend suite again after the final commit.
- [ ] Compare every acceptance criterion in the design spec to a passing test or visual verification note.
- [ ] Request final code review before merging or pushing.
