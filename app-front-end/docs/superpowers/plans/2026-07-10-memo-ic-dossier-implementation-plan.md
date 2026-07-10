# Modern IC Dossier Memo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle Aethria's existing investment memo into the approved modern IC dossier while preserving its content order, interactions, and 44rem embedded reading measure.

**Architecture:** Keep `InvestmentMemoContent` as the document orchestrator and retain the existing `MemoMasthead`, `MemoRulingSection`, conditional sections, and disclosure components. Add only the minimal semantic wrappers needed for the opening decision record and numbered section headings, then implement the dossier primarily through the existing memo stylesheet and container breakpoints.

**Tech Stack:** React 19, TypeScript, CSS container queries, Framer Motion, Vitest, Testing Library, Vite.

## Global Constraints

- Preserve this content order exactly: Recommendation → Snapshot → Why Now → What Limits Conviction → Assessment → Risks → Ruling → Appendix.
- Preserve the existing Figtree Variable, Space Mono, and limited Playfair Display font roles.
- Preserve all conditional rendering, memo data sources, ruling behavior, disclosures, download, add-context, and close actions.
- Treat `44rem` as the primary embedded reading measure.
- Do not use decorative double rules, faux-print ornament, continuous broadsheet columns, or repeated rounded card stacks.
- Use Oxford/navy ink, warm paper, and coral emphasis through existing design tokens.
- Preserve user-owned uncommitted changes and review any overlap in `InvestmentMemoContent.css` deliberately.

---

### Task 1: Encode dossier hierarchy in the memo document

**Files:**
- Modify: `app-front-end/src/components/InvestmentMemoContent.tsx:630-1040`
- Create: `app-front-end/src/components/memo/__tests__/InvestmentMemoStructure.test.tsx`

**Interfaces:**
- Consumes: existing derived values `convictionLine`, `reviewerConsensus`, `coverBlocker`, `coverAction`, `focalQuestion`, and current conditional section data.
- Produces: stable `.memoSectionNumber`, `.memoCoverDecisionRecord`, `.memoCoverDecisionMetric`, and `.memoCoverNextAction` hooks without changing component props or backend types.

- [ ] **Step 1: Add a structure test for the preserved section order**

Create a focused fixture test that renders a complete memo and asserts heading order:

```tsx
const headings = screen.getAllByRole('heading').map((node) => node.textContent);
expect(headings.indexOf('Snapshot')).toBeLessThan(headings.indexOf('Why Now'));
expect(headings.indexOf('Why Now')).toBeLessThan(headings.indexOf('What Limits Conviction'));
expect(headings.indexOf('What Limits Conviction')).toBeLessThan(headings.indexOf('Assessment'));
expect(headings.indexOf('Assessment')).toBeLessThan(headings.indexOf('Risks'));
```

Also assert that `Recommendation`, `What decides it`, `Blocker`, and `Next move` remain present when their values exist.

- [ ] **Step 2: Run the structure test and establish the baseline**

Run: `cd app-front-end && npm test -- --run src/components/memo/__tests__/InvestmentMemoStructure.test.tsx`

Expected: the order assertions pass against the existing document; new dossier hook assertions fail until Step 3.

- [ ] **Step 3: Add minimal dossier markup hooks**

Keep the existing text and conditions. Add an `aria-hidden` sequence number beside each main heading:

```tsx
<div className="memoDocSectionTitle">
  <span className="memoSectionNumber" aria-hidden>01</span>
  <h2 className="memoDocSectionHead" id="memo-snapshot">Snapshot</h2>
</div>
```

Use `01` Snapshot, `02` Why Now, `03` What Limits Conviction, `04` Assessment, `05` Risks. Wrap the existing cover metrics in `.memoCoverDecisionRecord`; do not duplicate them when `coverOverride` owns the embedded decision stage.

- [ ] **Step 4: Run the structure test**

Run: `cd app-front-end && npm test -- --run src/components/memo/__tests__/InvestmentMemoStructure.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit the semantic hierarchy**

```bash
git add app-front-end/src/components/InvestmentMemoContent.tsx app-front-end/src/components/memo/__tests__/InvestmentMemoStructure.test.tsx
git commit -m "feat(front): encode IC dossier memo hierarchy"
```

### Task 2: Implement the approved dossier visual system

**Files:**
- Modify: `app-front-end/src/components/InvestmentMemoContent.css:4100-4473`

**Interfaces:**
- Consumes: existing memo design tokens and the Task 1 class hooks.
- Produces: the final embedded and standalone dossier layout; no exported JavaScript interface changes.

- [ ] **Step 1: Preserve the user's current stylesheet work**

Review `git diff -- app-front-end/src/components/InvestmentMemoContent.css` and retain the existing masthead-border removal. Work additively in the final memo refinement layer so earlier rules remain recoverable and unrelated user changes are untouched.

- [ ] **Step 2: Implement the opening dossier grid**

At useful container widths, style the non-overridden `.memoCover` as a two-column opening using the existing recommendation and brief content. Keep the lede in the main column and compact decision data in the rail. Collapse at `620px`:

```css
.memoPanel:not(.memoPanel--embedded) .memoCover {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(11rem, 0.34fr);
  column-gap: clamp(28px, 4vw, 48px);
}

@container memoPanel (max-width: 620px) {
  .memoCover { grid-template-columns: 1fr; }
}
```

Do not create a duplicate opening grid around `coverOverride` in Flow.

- [ ] **Step 3: Replace rule-led sections with numbered editorial spacing**

Remove the universal main-section top border in the final override layer. Use stable spacing, a compact number/title row, and content-specific row separators:

```css
.memoDocSection,
.memoDocSection + .memoDocSection {
  margin-top: clamp(40px, 5vw, 62px);
  padding-top: 0;
  border-top: 0;
}

.memoDocSectionTitle {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: clamp(18px, 2.3vw, 26px);
}
```

- [ ] **Step 4: Restyle each existing content system**

Use the approved treatments:

- Snapshot: stable `9.5rem / 1fr` definition rows with quiet internal dividers.
- Why Now: numbered case list; stronger first point, no surrounding card.
- Limits and Risks: severity/rank, statement, and metadata aligned as rows.
- Assessment: compact score cells only where the container supports them; narrative remains single-column.
- Ruling: one navy terminal action surface while preserving component behavior and selected/error states.
- Appendix: quiet disclosure index with only row separators and right-aligned summaries.

- [ ] **Step 5: Add container-responsive fallbacks**

At `620px`, collapse opening, snapshot, and risk grids that squeeze prose. At `440px`, allow ruling choices and disclosure metadata to stack. Preserve the existing mobile `20px` inline padding and safe-area behavior.

- [ ] **Step 6: Run CSS and type verification**

Run: `cd app-front-end && npm run build`

Expected: TypeScript and Vite build complete successfully with no missing classes or syntax errors.

- [ ] **Step 7: Commit the visual system**

```bash
git add app-front-end/src/components/InvestmentMemoContent.css
git commit -m "feat(front): style memo as modern IC dossier"
```

### Task 3: Verify the full memo experience

**Files:**
- Modify only if verification exposes a defect: `app-front-end/src/components/InvestmentMemoContent.tsx`
- Modify only if verification exposes a defect: `app-front-end/src/components/InvestmentMemoContent.css`

**Interfaces:**
- Consumes: completed dossier markup and styling.
- Produces: verified behavior across data states and responsive widths.

- [ ] **Step 1: Run focused and full automated checks**

Run:

```bash
cd app-front-end
npm test -- --run src/components/memo/__tests__/InvestmentMemoStructure.test.tsx src/components/memo/__tests__/MemoMasthead.test.tsx src/components/memo/__tests__/memoTags.test.tsx
npm run build
```

Expected: all tests pass and the production build succeeds.

- [ ] **Step 2: Inspect the rendered memo at product widths**

Start the frontend with `npm run dev`, open a memo, and verify:

- embedded workspace at the real memo column width;
- wider standalone/modal memo;
- approximately `620px` container width;
- approximately `440px` narrow width.

Confirm the order, hierarchy, restrained separators, current fonts, natural wrapping, and lack of horizontal overflow.

- [ ] **Step 3: Exercise behavioral states**

Verify complete, partial, generating, failed, and decided memos where fixtures/data permit. Exercise add context, PDF download, close, disclosures, risk acknowledgement, ruling selection, rationale entry, and submit.

- [ ] **Step 4: Fix only evidence-backed defects and rerun checks**

For each defect, make the smallest correction in the owning existing component or stylesheet, then rerun the failing check and `npm run build`.

- [ ] **Step 5: Commit verification fixes if any**

```bash
git add app-front-end/src/components/InvestmentMemoContent.tsx app-front-end/src/components/InvestmentMemoContent.css app-front-end/src/components/memo/__tests__/InvestmentMemoStructure.test.tsx
git commit -m "fix(front): finish IC dossier memo verification"
```
