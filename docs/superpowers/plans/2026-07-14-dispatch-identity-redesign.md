# Dispatch Identity Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Dispatch’s ambiguous-company chooser into an evidence-rich identity brief and make the ambient background dots breathe in stable positions.

**Architecture:** Keep the existing resolver and `LookupCandidate` API contract. Add a pure presentation module for confidence/evidence semantics, rebuild `CandidatePicker` around those semantics, widen only the Identify-stage container, and remove per-animation React state updates from `DispatchDotPulse`.

**Tech Stack:** React 18, TypeScript, Tailwind CSS 3, Framer Motion, Vitest, Testing Library, CSS keyframes.

## Global Constraints

- Use only verified `LookupCandidate` fields: `name`, `website`, `description`, `confidence`, and `source_badges`.
- Do not add sector, funding, founder, stage, or geography fields.
- Preserve `CandidatePicker`’s `onPick`, `onRefine`, and `busy` contracts.
- Keep candidate selection manual; confidence must never auto-select.
- Animate only opacity and restrained scale for background dots.
- Honor `prefers-reduced-motion` and preserve keyboard focus visibility.
- Do not add dependencies or change the resolver ranking thresholds.

---

### Task 1: Candidate identity presentation semantics

**Files:**
- Create: `app-front-end/src/lib/candidateIdentity.ts`
- Create: `app-front-end/src/lib/__tests__/candidateIdentity.test.ts`

**Interfaces:**
- Consumes: `LookupCandidate` from `src/api/startups.ts`.
- Produces: `domainLabel(website: string): string`, `identityConfidence(confidence: number): { label: string; percent: number; tone: 'strong' | 'likely' | 'possible' }`, `evidenceLabels(sourceBadges: string[], hasDomain: boolean): string[]`, and `isBestIdentityMatch(candidate: LookupCandidate, index: number): boolean`.

- [ ] **Step 1: Write failing tests for normalized identity presentation**

```ts
import { describe, expect, it } from 'vitest';
import {
  domainLabel,
  evidenceLabels,
  identityConfidence,
  isBestIdentityMatch,
} from '../candidateIdentity';

describe('candidate identity presentation', () => {
  it('turns resolver confidence into bounded analyst-facing language', () => {
    expect(identityConfidence(0.91)).toEqual({ label: 'Strong identity match', percent: 91, tone: 'strong' });
    expect(identityConfidence(0.64)).toEqual({ label: 'Likely identity match', percent: 64, tone: 'likely' });
    expect(identityConfidence(-2)).toEqual({ label: 'Possible identity match', percent: 0, tone: 'possible' });
    expect(identityConfidence(4)).toEqual({ label: 'Strong identity match', percent: 100, tone: 'strong' });
  });

  it('normalizes evidence labels and falls back to an official-domain claim', () => {
    expect(evidenceLabels(['official', 'linkedin', 'crunchbase', 'news'], true)).toEqual([
      'Official site', 'LinkedIn', 'Crunchbase', 'Press',
    ]);
    expect(evidenceLabels([], true)).toEqual(['Official domain candidate']);
    expect(evidenceLabels([], false)).toEqual([]);
  });

  it('marks only the first strong candidate as the best match', () => {
    const candidate = { confidence: 0.82 } as never;
    expect(isBestIdentityMatch(candidate, 0)).toBe(true);
    expect(isBestIdentityMatch(candidate, 1)).toBe(false);
    expect(isBestIdentityMatch({ confidence: 0.69 } as never, 0)).toBe(false);
  });

  it('renders a clean registrable domain label', () => {
    expect(domainLabel('https://www.acme.ie/about')).toBe('acme.ie');
  });
});
```

- [ ] **Step 2: Run the focused test and observe the missing-module failure**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/candidateIdentity.test.ts`

Expected: FAIL because `../candidateIdentity` does not exist.

- [ ] **Step 3: Implement the pure presentation helpers**

```ts
import type { LookupCandidate } from '../api/startups';

const EVIDENCE_LABELS: Record<string, string> = {
  official: 'Official site',
  linkedin: 'LinkedIn',
  crunchbase: 'Crunchbase',
  dealroom: 'Dealroom',
  yc: 'Y Combinator',
  news: 'Press',
};

export function domainLabel(website: string): string {
  return website.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '');
}

export function identityConfidence(confidence: number) {
  const bounded = Math.min(1, Math.max(0, Number.isFinite(confidence) ? confidence : 0));
  const percent = Math.round(bounded * 100);
  if (bounded >= 0.7) return { label: 'Strong identity match', percent, tone: 'strong' as const };
  if (bounded >= 0.4) return { label: 'Likely identity match', percent, tone: 'likely' as const };
  return { label: 'Possible identity match', percent, tone: 'possible' as const };
}

export function evidenceLabels(sourceBadges: string[], hasDomain: boolean): string[] {
  const labels = Array.from(new Set(sourceBadges.map((badge) => EVIDENCE_LABELS[badge.toLowerCase()]).filter(Boolean)));
  return labels.length ? labels : hasDomain ? ['Official domain candidate'] : [];
}

export function isBestIdentityMatch(candidate: LookupCandidate, index: number): boolean {
  return index === 0 && candidate.confidence >= 0.7;
}
```

- [ ] **Step 4: Run the focused test until green**

Run: `cd app-front-end && npm test -- --run src/lib/__tests__/candidateIdentity.test.ts`

Expected: 4 tests pass.

- [ ] **Step 5: Commit the identity semantics**

```bash
git add app-front-end/src/lib/candidateIdentity.ts app-front-end/src/lib/__tests__/candidateIdentity.test.ts
git commit -m "feat: add candidate identity presentation semantics"
```

---

### Task 2: Evidence-rich candidate picker

**Files:**
- Modify: `app-front-end/src/components/CandidatePicker.tsx`
- Create: `app-front-end/src/components/__tests__/CandidatePicker.test.tsx`

**Interfaces:**
- Consumes: the Task 1 presentation helpers and the unchanged `CandidatePickerProps` callback contract.
- Produces: an accessible identity-dossier section with selection rows and a website-refinement panel.

- [ ] **Step 1: Write failing interaction and content tests**

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CandidatePicker from '../CandidatePicker';

const candidates = [
  {
    name: 'Lyra Health',
    website: 'https://lyrahealth.com',
    description: 'Workforce mental-health care platform for employers.',
    confidence: 0.91,
    source_badges: ['official', 'linkedin', 'news'],
  },
  {
    name: 'Lyra',
    website: 'https://lyra.ie',
    description: '',
    confidence: 0.63,
    source_badges: [],
  },
];

describe('CandidatePicker', () => {
  it('shows a decision-useful identity brief for every candidate', () => {
    render(<CandidatePicker candidates={candidates} onPick={() => undefined} onRefine={() => undefined} />);
    expect(screen.getByText('2 plausible identities')).toBeInTheDocument();
    expect(screen.getByText('Best match')).toBeInTheDocument();
    expect(screen.getByText('Strong identity match')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(screen.getByText('Official site')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn')).toBeInTheDocument();
    expect(screen.getByText('Press')).toBeInTheDocument();
    expect(screen.getByText('No description was confirmed for this domain.')).toBeInTheDocument();
  });

  it('preserves selection and website refinement callbacks', () => {
    const onPick = vi.fn();
    const onRefine = vi.fn();
    render(<CandidatePicker candidates={candidates} onPick={onPick} onRefine={onRefine} />);
    fireEvent.click(screen.getByRole('button', { name: 'Use Lyra Health at lyrahealth.com' }));
    expect(onPick).toHaveBeenCalledWith(candidates[0]);
    fireEvent.click(screen.getByRole('button', { name: 'None of these companies' }));
    fireEvent.change(screen.getByLabelText('Company website'), { target: { value: 'other.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Resolve website' }));
    expect(onRefine).toHaveBeenCalledWith('other.example');
  });
});
```

- [ ] **Step 2: Run the component test and observe missing dossier content**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx`

Expected: FAIL because the current picker has no candidate count, confidence language, explicit action, or composed refinement panel.

- [ ] **Step 3: Rebuild `CandidatePicker` as an identity dossier**

Implement these exact structural requirements:

```tsx
<section className="candidate-identity" aria-labelledby="candidate-identity-title">
  <header className="candidate-identity__header">
    <div>
      <p className="type-label-section">Confirm company identity</p>
      <h2 id="candidate-identity-title">Choose the company you meant</h2>
      <p>{heading ?? 'These companies share a similar name. Compare their domains and verification evidence.'}</p>
    </div>
    <p>{`${candidates.length} plausible ${candidates.length === 1 ? 'identity' : 'identities'}`}</p>
  </header>
  <ol className="candidate-identity__list">
    {candidates.map((candidate, index) => {
      const domain = domainLabel(candidate.website);
      const confidence = identityConfidence(candidate.confidence);
      const evidence = evidenceLabels(candidate.source_badges, Boolean(domain));
      return (
        <li key={candidate.website} className="candidate-identity__row">
          <div className="candidate-identity__rail">
            <span>{String(index + 1).padStart(2, '0')}</span>
            <span>{confidence.percent}%</span>
          </div>
          <div className="candidate-identity__body">
            {isBestIdentityMatch(candidate, index) ? <span>Best match</span> : null}
            <h3>{candidate.name}</h3>
            <p>{domain}</p>
            <p>{candidate.description || 'No description was confirmed for this domain.'}</p>
            <div aria-label={`Verification evidence for ${candidate.name}`}>
              <span>{confidence.label}</span>
              <span>Verified by</span>
              {evidence.map((label) => <span key={label}>{label}</span>)}
            </div>
          </div>
          <button type="button" onClick={() => onPick(candidate)} disabled={busy} aria-label={`Use ${candidate.name} at ${domain}`}>
            Use this company <span aria-hidden>→</span>
          </button>
        </li>
      );
    })}
  </ol>
</section>
```

Use Tailwind classes or component-scoped classes consistent with the existing Oxford/paper palette. Desktop rows use `grid-template-columns: minmax(3rem, .12fr) minmax(0, 1fr) auto`; below the existing small breakpoint they collapse to one column. Use dividers and `bg-oxford/[0.025]`, not shadows. Add `focus-visible` outline, pointer-gated hover styles, and `active:scale-[0.985]` with a 140–180ms transform transition.

The refinement trigger must be a native button labeled `None of these companies`. When open, render a `<label htmlFor="candidate-website">Company website</label>`, the existing input, explanatory copy, and a `Resolve website` action.

- [ ] **Step 4: Run the component and existing lookup tests**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx src/api/__tests__/startupsLookup.test.ts`

Expected: all tests pass.

- [ ] **Step 5: Commit the picker redesign**

```bash
git add app-front-end/src/components/CandidatePicker.tsx app-front-end/src/components/__tests__/CandidatePicker.test.tsx
git commit -m "feat: redesign Dispatch company identity picker"
```

---

### Task 3: Identify-stage layout integration

**Files:**
- Modify: `app-front-end/src/components/DispatchCommandBar.tsx`
- Modify: `app-front-end/src/components/__tests__/DispatchCommandBar.test.tsx`

**Interfaces:**
- Consumes: the redesigned `CandidatePicker` without changing its props.
- Produces: a candidate-only wide layout while all other Dispatch views retain their current measures.

- [ ] **Step 1: Add a failing integration assertion**

Add a test that renders `DispatchCommandBar` with unresolved progress and two candidates, then asserts the dossier region is present and its wrapper carries `max-w-4xl`:

```tsx
const { container } = render(
  <DispatchCommandBar
    open
    onClose={() => undefined}
    input="Lyra"
    setInput={() => undefined}
    onSubmit={() => undefined}
    isBusy={false}
    message="Confirm the exact company."
    lookupPhase="Scouting"
    progress={{ query: 'Lyra', name: null, sector: null, resolved: false, found: false, reviewed: false }}
    candidates={candidates}
    onPickCandidate={() => undefined}
    onRefineWebsite={() => undefined}
  />,
);
expect(screen.getByRole('region', { name: 'Select the company you meant' })).toBeInTheDocument();
expect(container.querySelector('.max-w-4xl')).not.toBeNull();
```

- [ ] **Step 2: Run the integration test and observe the width failure**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/DispatchCommandBar.test.tsx`

Expected: FAIL because the current picker wrapper is `max-w-md`.

- [ ] **Step 3: Widen only the candidate branch and simplify competing motion**

Change the picker wrapper from `w-full max-w-md text-left` to `w-full max-w-4xl text-left`. Keep the progress steps and message at their existing centered measure. Ensure the picker owns its single 200ms entrance and remove any nested transform that causes the dossier to animate twice.

- [ ] **Step 4: Run the integration test**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/DispatchCommandBar.test.tsx`

Expected: all DispatchCommandBar tests pass.

- [ ] **Step 5: Commit the layout integration**

```bash
git add app-front-end/src/components/DispatchCommandBar.tsx app-front-end/src/components/__tests__/DispatchCommandBar.test.tsx
git commit -m "style: widen Dispatch identity confirmation"
```

---

### Task 4: Stable ambient dot motion

**Files:**
- Modify: `app-front-end/src/components/DispatchDotPulse.tsx`
- Modify: `app-front-end/src/index.css`
- Create: `app-front-end/src/components/__tests__/DispatchDotPulse.test.tsx`

**Interfaces:**
- Consumes: `active: boolean`.
- Produces: stable grid-aligned decorative dots with no per-cycle state mutation and ResizeObserver-based remeasurement.

- [ ] **Step 1: Write the failing stability test**

```tsx
import { readFileSync } from 'node:fs';
import { fireEvent, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DispatchDotPulse from '../DispatchDotPulse';

describe('DispatchDotPulse', () => {
  beforeEach(() => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    });
  });

  it('keeps dot coordinates stable across animation iterations', () => {
    const { container } = render(<DispatchDotPulse active />);
    const dot = container.querySelector<HTMLElement>('.dot-grid-pulse');
    expect(dot).not.toBeNull();
    const before = `${dot!.style.left}:${dot!.style.top}`;
    fireEvent.animationIteration(dot!);
    expect(`${dot!.style.left}:${dot!.style.top}`).toBe(before);
  });

  it('does not attach a per-animation relocation handler', () => {
    const source = readFileSync(new URL('../DispatchDotPulse.tsx', import.meta.url), 'utf8');
    expect(source).not.toContain('onAnimationIteration');
    expect(source).not.toContain('relocate(');
  });
});
```

- [ ] **Step 2: Run the test and verify the current relocation path is exercised**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/DispatchDotPulse.test.tsx`

Expected: FAIL because the source still contains `onAnimationIteration` and `relocate(`.

- [ ] **Step 3: Remove iteration relocation and measure with ResizeObserver**

Refactor the component so `PulseDot` coordinates are generated only inside a `buildDots(cols, rows)` function called when `active` becomes true or measured grid dimensions actually change. Remove `onAnimationIteration`, `gridRef`, and `relocate`. Attach one `ResizeObserver` to the overlay and disconnect it on cleanup. Avoid rebuilding dots when width and height map to the same column/row counts.

- [ ] **Step 4: Replace the zooming keyframe with a restrained breath**

```css
@keyframes dot-grid-pulse {
  0%, 100% { opacity: 0.04; transform: scale(0.92); }
  50% { opacity: var(--pulse-peak, 0.26); transform: scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .dot-grid-pulse {
    animation: none !important;
    opacity: 0.08;
    transform: none;
  }
}
```

Keep `will-change: opacity, transform`; do not animate `left`, `top`, width, or height.

- [ ] **Step 5: Run the dot test and source checks**

Run: `cd app-front-end && npm test -- --run src/components/__tests__/DispatchDotPulse.test.tsx`

Run: `! rg -n 'onAnimationIteration|relocate\(' app-front-end/src/components/DispatchDotPulse.tsx`

Expected: test passes and search returns no matches.

- [ ] **Step 6: Commit the motion fix**

```bash
git add app-front-end/src/components/DispatchDotPulse.tsx app-front-end/src/components/__tests__/DispatchDotPulse.test.tsx app-front-end/src/index.css
git commit -m "fix: stabilize Dispatch background activity dots"
```

---

### Task 5: Full verification and visual review

**Files:**
- Modify only files required to correct issues found during verification.

**Interfaces:**
- Consumes: completed Tasks 1–4.
- Produces: verified desktop/mobile identity selection and stable long-running background motion.

- [ ] **Step 1: Run the complete frontend suite**

Run: `cd app-front-end && npm test -- --run`

Expected: all tests pass.

- [ ] **Step 2: Run lint and production build**

Run: `cd app-front-end && npm run lint`

Run: `cd app-front-end && npm run build`

Expected: both commands exit 0 with no warnings promoted to errors.

- [ ] **Step 3: Verify implementation constraints by search**

Run: `! rg -n 'onAnimationIteration|transform: scale\(0\.[0-7]\)' app-front-end/src/components/DispatchDotPulse.tsx app-front-end/src/index.css`

Run: `git diff --check`

Expected: both commands exit 0.

- [ ] **Step 4: Perform browser verification**

Start the frontend with `npm run dev`, open Dispatch, and verify:

- two to five candidates render name, domain, description fallback, confidence language, and evidence;
- desktop layout uses the evidence rail and mobile layout stacks without horizontal scroll;
- keyboard focus reaches each selection action and the refinement path in order;
- busy state disables all submission controls;
- dots remain in fixed positions for at least three complete pulse cycles;
- reduced-motion emulation removes scale movement;
- long company names and domains truncate or wrap without moving the action off-screen.

- [ ] **Step 5: Commit any verification corrections**

If verification required corrections, stage only those files and commit:

```bash
git add app-front-end/src
git commit -m "fix: polish Dispatch identity verification states"
```

If no corrections were required, do not create an empty commit.
