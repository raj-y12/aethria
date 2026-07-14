# Task 2 report: Evidence-rich candidate picker

## Files

- Modified `app-front-end/src/components/CandidatePicker.tsx` with the accessible identity dossier, confidence/evidence presentation, explicit selection actions, and website refinement panel.
- Added `app-front-end/src/components/__tests__/CandidatePicker.test.tsx` covering dossier content and callback interactions.

## TDD RED/GREEN

- RED: `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx`
  - Failed as expected: 2 tests failed because the existing picker did not render the candidate count, identity confidence/evidence labels, required action names, or labeled refinement input.
- GREEN: `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx`
  - Passed: 1 test file, 2 tests.

## Verification

- `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx src/api/__tests__/startupsLookup.test.ts`
  - Passed: 2 files, 3 tests.
- `cd app-front-end && npm run build`
  - Passed TypeScript compilation and Vite production build.
- `git diff --check`
  - Passed with no whitespace errors.

## Self-review

- Uses Task 1 helpers for normalized domains, confidence language, evidence labels, and best-match marking.
- Candidate rows retain the original `onPick` contract and expose descriptive accessible names.
- Refinement is a native-button flow with an explicit label, explanatory copy, keyboard Enter submission, and unchanged `onRefine` payload semantics.
- Layout follows the requested three-column desktop grid, paper/Oxford palette, dividers, focus-visible outlines, pointer-gated hover, and active scale transition.

## Concerns

- No concerns identified. The existing `motion` entrance animation remains for the picker wrapper; no DispatchCommandBar or dot-motion code was changed.

## Review fix

### Files

- Modified `app-front-end/src/components/CandidatePicker.tsx` to collapse candidate rows to one column below `sm`, retain the three-column evidence rail at `sm` and above, gate hover styles to fine pointers, and honor `usePrefersReducedMotion` with reduced Framer Motion transitions.
- Modified `app-front-end/src/components/__tests__/CandidatePicker.test.tsx` with responsive/fine-pointer class contract coverage and a `matchMedia` test shim.

### Verification

- `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx src/api/__tests__/startupsLookup.test.ts` — passed: 2 files, 4 tests.
- `cd app-front-end && npm run build` — passed TypeScript compilation and Vite production build.

### Concerns

- No concerns identified. DispatchCommandBar and dot motion were not changed.

## Review fix: pointer-gated action hover

- Replaced `productInteraction.action` on the Use/Resolve controls with a component-local equivalent that preserves the existing `type-action` typography, focus, and disabled behavior while gating `hover:text-oxford` behind the fine-pointer media query.

### Verification

- `cd app-front-end && npm test -- --run src/components/__tests__/CandidatePicker.test.tsx src/api/__tests__/startupsLookup.test.ts` — passed: 2 files, 4 tests.
- `cd app-front-end && npm run build` — passed TypeScript compilation and Vite production build.

### Concerns

- No concerns identified. The focused change is limited to the two CandidatePicker action controls.
