# Dispatch Result Summary Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the large dispatch result summary to a balanced 16–18px serif treatment without changing any other snapshot variant.

**Architecture:** Keep the existing `LookupResultSnapshot` public API and variant branching. Change only the `lg` summary class branch, and protect the styling boundary with a focused rendering test in the app frontend, which already resolves the shared workspace package.

**Tech Stack:** React 18, TypeScript, Tailwind CSS utilities, Vitest, Testing Library

## Global Constraints

- Only the large, non-memo snapshot summary typography changes.
- The summary remains in the display serif with a 16px minimum, 18px maximum, and 1.4 line-height.
- Company name, metadata, verdict, scores, card spacing, memo, default, and compact variants remain unchanged.
- No content is truncated, clamped, or hidden.

---

### Task 1: Bound the large snapshot summary typography

**Files:**
- Create: `app-front-end/src/components/__tests__/LookupResultSnapshotTypography.test.tsx`
- Modify: `packages/product-chrome/src/LookupResultSnapshot.tsx:119-129`

**Interfaces:**
- Consumes: `LookupResultSnapshotProps.size` and `LookupResultSnapshotProps.variant`
- Produces: Existing `LookupResultSnapshot` rendering with a large-summary class contract of `text-[clamp(1rem,1.8vw,1.125rem)] leading-[1.4]`

- [ ] **Step 1: Write the failing typography-boundary test**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LookupResultSnapshot } from '@aethria/product-chrome';

const baseProps = {
  companyName: 'Simantic',
  verdict: 'Invest',
  summary: 'A detailed investment finding that should remain readable without dominating the result card.',
  dimensions: [],
};

describe('LookupResultSnapshot summary typography', () => {
  it('uses the balanced serif scale only for the large snapshot', () => {
    const { rerender } = render(<LookupResultSnapshot {...baseProps} size="lg" />);
    const largeSummary = screen.getByText(baseProps.summary);

    expect(largeSummary).toHaveClass('pc-font-display');
    expect(largeSummary).toHaveClass('text-[clamp(1rem,1.8vw,1.125rem)]');
    expect(largeSummary).toHaveClass('leading-[1.4]');

    rerender(<LookupResultSnapshot {...baseProps} />);
    const defaultSummary = screen.getByText(baseProps.summary);

    expect(defaultSummary).toHaveClass('font-sans');
    expect(defaultSummary).toHaveClass('text-[15px]');
    expect(defaultSummary).not.toHaveClass('text-[clamp(1rem,1.8vw,1.125rem)]');
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd app-front-end && npm test -- src/components/__tests__/LookupResultSnapshotTypography.test.tsx`

Expected: FAIL because the large summary still has `text-[clamp(1.125rem,2.4vw,1.45rem)]` and `leading-[1.45]`.

- [ ] **Step 3: Apply the minimal large-variant class change**

In `packages/product-chrome/src/LookupResultSnapshot.tsx`, replace the `lg` summary class with:

```tsx
'pc-font-display mt-3 text-[clamp(1rem,1.8vw,1.125rem)] leading-[1.4] tracking-[-0.012em] text-oxford/80'
```

Keep every other branch and class unchanged.

- [ ] **Step 4: Run focused and regression checks**

Run: `cd app-front-end && npm test -- src/components/__tests__/LookupResultSnapshotTypography.test.tsx src/components/__tests__/DispatchCommandBar.test.tsx`

Expected: both test files pass.

Run: `cd app-front-end && npm run build`

Expected: TypeScript compilation and Vite production build complete successfully.

- [ ] **Step 5: Inspect the final diff**

Run: `git diff --check && git diff -- packages/product-chrome/src/LookupResultSnapshot.tsx app-front-end/src/components/__tests__/LookupResultSnapshotTypography.test.tsx`

Expected: no whitespace errors; the diff contains one scoped class replacement and one focused test file.

- [ ] **Step 6: Commit the implementation**

```bash
git add packages/product-chrome/src/LookupResultSnapshot.tsx app-front-end/src/components/__tests__/LookupResultSnapshotTypography.test.tsx docs/superpowers/plans/2026-07-14-dispatch-result-summary-typography.md
git commit -m "fix: balance dispatch result summary typography"
```
