# IC Dossier Sunday Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the complete on-screen investment memo as the approved soft-rule Sunday Review dossier while preserving fonts, data flow, behavior, and accessibility.

**Architecture:** Keep the existing memo component boundaries and data derivations. Make two focused markup changes—the masthead folio and the opening pull-question—then replace the accumulated memo stylesheet with one ordered, container-responsive editorial stylesheet that covers every existing memo and scoring class. Preserve all API, polling, ruling, PDF, and disclosure behavior.

**Tech Stack:** React 18, TypeScript, Vitest, Testing Library, CSS container queries, Framer Motion, Vite.

## Global Constraints

- Preserve Playfair Display, Figtree Variable, and Space Mono.
- Use typography and whitespace as the primary hierarchy; avoid dominant full-width rules.
- Keep the existing paper, Oxford, semantic verdict, and risk-accent tokens.
- Do not change backend models, API contracts, decision logic, PDF content, or application-shell styling.
- Keep all current keyboard, focus, reduced-motion, read-only, loading, error, and ruling behavior.
- Preserve the user's unrelated edits in `app-front-end/src/components/queue/DocketCaseRow.tsx` and `app-front-end/src/design-system/density.ts`.

---

## File Map

- Modify `app-front-end/src/components/memo/MemoMasthead.tsx`: quiet folio, deterministic dossier reference, and subordinate actions.
- Modify `app-front-end/src/components/memo/MemoDossierOpening.tsx`: opening grid plus standalone focal-question pull quote.
- Modify `app-front-end/src/components/memo/__tests__/MemoMasthead.test.tsx`: assert folio and action semantics.
- Modify `app-front-end/src/components/memo/__tests__/MemoDossierOpening.test.tsx`: assert opening grid and question placement.
- Replace `app-front-end/src/components/InvestmentMemoContent.css`: one coherent Sunday Review system for shell, sections, context, scorecard, risks, ruling, appendix, system states, print, and container breakpoints.
- Verify without modifying `app-front-end/src/components/InvestmentMemoContent.tsx`, scoring child APIs, memo data helpers, or PDF generation unless a failing test demonstrates a real integration defect.

### Task 1: Editorial masthead and dossier opening structure

**Files:**
- Modify: `app-front-end/src/components/memo/MemoMasthead.tsx`
- Modify: `app-front-end/src/components/memo/MemoDossierOpening.tsx`
- Test: `app-front-end/src/components/memo/__tests__/MemoMasthead.test.tsx`
- Test: `app-front-end/src/components/memo/__tests__/MemoDossierOpening.test.tsx`

**Interfaces:**
- Consumes: existing `Startup`, masthead callbacks, and `MemoDossierOpeningProps`.
- Produces: existing component exports; new semantic wrappers `.memoMastheadFolio`, `.memoDossierOpeningGrid`, and `.memoDossierQuestion--pull` used by the replacement stylesheet.

- [ ] **Step 1: Add failing masthead assertions**

Add assertions that the masthead exposes the document identity and a stable dossier reference while retaining its actions:

```tsx
expect(screen.getByText('Aethria / IC')).toBeInTheDocument();
expect(screen.getByText(/Dossier/i)).toBeInTheDocument();
expect(screen.getByRole('button', { name: /IC pack as PDF/i })).toBeInTheDocument();
```

- [ ] **Step 2: Add failing dossier-opening assertions**

Assert the recommendation and record share a grid while the focal question is a separate pull quote:

```tsx
const opening = screen.getByRole('banner');
expect(opening.querySelector('.memoDossierOpeningGrid')).not.toBeNull();
expect(opening.querySelector('.memoDossierQuestion--pull')).not.toBeNull();
expect(screen.getByText('What decides it')).toBeInTheDocument();
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
cd app-front-end && npm test -- --run src/components/memo/__tests__/MemoMasthead.test.tsx src/components/memo/__tests__/MemoDossierOpening.test.tsx
```

Expected: FAIL because the new folio text and wrappers do not exist.

- [ ] **Step 4: Implement the masthead folio**

Derive a short deterministic dossier reference without changing the component API:

```tsx
const dossierRef = startup.id
  ? startup.id.replace(/[^a-zA-Z0-9]/g, '').slice(-6).toUpperCase().padStart(6, '0')
  : '000000';
```

Render `Aethria / IC`, `Dossier ${dossierRef}`, the issue date, company identity, tags, and existing actions in semantic masthead wrappers. Keep callback behavior and accessible names unchanged.

- [ ] **Step 5: Implement the opening grid and pull-question**

Wrap the lede and record in:

```tsx
<div className="memoDossierOpeningGrid">
  <div className="memoDossierLede">…</div>
  <aside className="memoDossierRecord" aria-label="Decision record">…</aside>
</div>
```

Render the focal question after that grid using `.memoDossierQuestion.memoDossierQuestion--pull`. Keep blocker, next move, status, and metric conditionals unchanged.

- [ ] **Step 6: Re-run focused tests**

Run the Task 1 command again. Expected: both test files PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add app-front-end/src/components/memo/MemoMasthead.tsx app-front-end/src/components/memo/MemoDossierOpening.tsx app-front-end/src/components/memo/__tests__/MemoMasthead.test.tsx app-front-end/src/components/memo/__tests__/MemoDossierOpening.test.tsx
git commit -m "feat(front): establish Sunday Review memo opening"
```

### Task 2: Consolidated Sunday Review stylesheet

**Files:**
- Replace: `app-front-end/src/components/InvestmentMemoContent.css`

**Interfaces:**
- Consumes: every existing `memo*` class emitted by `InvestmentMemoContent.tsx`, `components/memo/*`, and `components/scoring/*`.
- Produces: the same class contracts with one ordered visual system and container breakpoints at approximately 760px and 520px.

- [ ] **Step 1: Capture the emitted class contract**

Run:

```bash
cd app-front-end && rg -o 'memo[A-Z][A-Za-z0-9_-]+' src/components/InvestmentMemoContent.tsx src/components/memo src/components/scoring | sort -u > /tmp/aethria-memo-classes.txt
```

Expected: a stable list of memo class names used as the coverage checklist.

- [ ] **Step 2: Replace the stylesheet in ordered layers**

Write one stylesheet in this order:

```css
.memoPanel { /* fonts, type scale, ink, rules, container */ }
.memoScroll, .memoBody { /* document shell and measure */ }
/* masthead and system states */
/* dossier opening and context modules */
/* shared numbered-section primitives */
/* snapshot, case, killers, assessment, risk register */
/* ruling controls */
/* appendix, sources, run log, disclosures */
/* focus, reduced-motion, print */
@container memoPanel (max-width: 760px) { /* collapse editorial grids */ }
@container memoPanel (max-width: 520px) { /* mobile type and controls */ }
```

Use these exact visual decisions:

- paper is continuous; no stacked card surfaces;
- major section top spacing is 64–80px wide and 44–56px narrow;
- section titles use Playfair and a 24–32px pseudo-element stroke;
- opening is roughly `minmax(0, 1.4fr) minmax(13rem, .6fr)` with a generous gap;
- body prose uses Figtree at 14–16px and 1.6–1.75 leading depending on container width;
- score tracks are 2px with 8–12% track opacity;
- risk entries are flat rows with severity metadata and at most 10–12% separators;
- ruling is the only 3–4% Oxford wash;
- appendix rows use 8–10% separators because the line encodes a clickable boundary;
- no radius above 2px, no decorative shadows, no gradient, and no thick side borders.

- [ ] **Step 3: Check selector coverage**

Compare emitted classes against stylesheet selectors:

```bash
cd app-front-end && while read -r cls; do rg -q "\\.${cls}([[:space:][:punct:]]|$)" src/components/InvestmentMemoContent.css || echo "$cls"; done < /tmp/aethria-memo-classes.txt
```

Expected: only classes intentionally controlled by Tailwind or semantic state composition may print. Inspect and style every visual class that otherwise lacks a rule.

- [ ] **Step 4: Run memo tests and production build**

```bash
cd app-front-end && npm test -- --run src/components/memo src/components/scoring && npm run build
```

Expected: tests PASS and Vite production build exits 0.

- [ ] **Step 5: Commit Task 2**

```bash
git add app-front-end/src/components/InvestmentMemoContent.css
git commit -m "feat(front): restyle complete memo as Sunday Review dossier"
```

### Task 3: Interaction and accessibility regression pass

**Files:**
- Modify only if required by a demonstrated failure: `app-front-end/src/components/InvestmentMemoContent.css`
- Modify only if required by a demonstrated failure: memo/scoring component tests.

**Interfaces:**
- Consumes: existing disclosure, expandable-list, ruling, focus, and reduced-motion behavior.
- Produces: no new API; verified accessible interaction states.

- [ ] **Step 1: Run the full frontend test suite**

```bash
cd app-front-end && npm test
```

Expected: all tests PASS.

- [ ] **Step 2: Run lint**

```bash
cd app-front-end && npm run lint
```

Expected: zero warnings and zero errors. If unrelated pre-existing failures occur, record them separately and do not edit unrelated files.

- [ ] **Step 3: Inspect focus and motion selectors**

Confirm the replacement stylesheet contains visible `:focus-visible` rules for masthead actions, disclosures, score rows, precedent links, decision choices, risk acknowledgement, and commit ruling, plus:

```css
@media (prefers-reduced-motion: reduce) {
  .memoPanel *, .memoPanel *::before, .memoPanel *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Commit any verified regression fixes**

Stage only memo files and commit with `fix(front): preserve memo interaction states`. Skip this commit if no changes were needed.

### Task 4: Browser verification and polish

**Files:**
- Modify: memo CSS or memo components only when the browser demonstrates a defect.

**Interfaces:**
- Consumes: the built application and existing representative memo data.
- Produces: visually verified embedded and modal dossier across responsive widths.

- [ ] **Step 1: Start the frontend**

```bash
cd app-front-end && npm run dev -- --host 127.0.0.1
```

Expected: Vite reports a reachable local URL.

- [ ] **Step 2: Verify wide, medium, and narrow memo containers**

Inspect at desktop, tablet, and mobile widths. Confirm:

- masthead actions never dominate or overflow;
- opening record collapses before becoming cramped;
- pull-question has space but does not strand a short line;
- snapshot, score, risk, precedent, portfolio, ruling, and appendix components share the same typography and spacing;
- no horizontal overflow occurs;
- read-only, generating, failure, empty, and expanded disclosure states remain legible.

- [ ] **Step 3: Apply only evidence-based polish**

Fix observed clipping, wrapping, hierarchy, or contrast problems in memo files. Do not change queue or shell files.

- [ ] **Step 4: Re-run targeted tests and build**

```bash
cd app-front-end && npm test -- --run src/components/memo src/components/scoring && npm run build
```

Expected: PASS and exit 0.

- [ ] **Step 5: Commit browser-verified polish**

Stage only memo files and commit with `fix(front): polish responsive IC dossier`. Skip if no changes were needed.

### Task 5: Final verification

**Files:** None unless verification finds a memo-scoped defect.

**Interfaces:**
- Consumes: completed Tasks 1–4.
- Produces: evidence that the redesign is complete and unrelated work remains untouched.

- [ ] **Step 1: Inspect the final diff**

```bash
git diff HEAD~3 -- app-front-end/src/components/InvestmentMemoContent.css app-front-end/src/components/memo app-front-end/src/components/scoring
git status --short
```

Expected: only intended memo files and the user's pre-existing queue/density edits appear.

- [ ] **Step 2: Run the final gate**

```bash
cd app-front-end && npm test && npm run build
```

Expected: all tests PASS and the production build exits 0.

- [ ] **Step 3: Verify design-spec coverage**

Check the final UI against every component section in `docs/superpowers/specs/2026-07-10-ic-dossier-sunday-review-design.md`. Confirm that no memo component retains a card-heavy or rule-heavy visual fallback.
