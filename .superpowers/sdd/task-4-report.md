# Task 4 report

Implemented stable ambient Dispatch background dots.

- Added stability/source regression coverage for animation iterations and relocation handlers.
- Replaced iteration relocation and resize listeners with guarded `ResizeObserver` remeasurement.
- Rebuilds dots only when active or when measured grid dimensions change.
- Replaced zoom-like keyframes with restrained opacity/scale breathing and reduced-motion styling.
- Added a runtime fallback for environments without `ResizeObserver` (including jsdom).

Verification:

- Focused DispatchDotPulse tests: pass (2/2).
- Source check for `onAnimationIteration` / `relocate(`: pass.
- `npm run build`: pass.
- Full frontend suite: 202/203 passed; one unrelated `settingsRoomLayout` test timed out at its existing 5s limit (`routes a deployment validation error to the affected section`).

Review follow-up:

- Scoped the reduced-motion `opacity` and `transform` fallback to `.dot-grid-pulse`; the shared selector group now only applies `animation: none !important`.
- Added a source-level regression test proving unrelated reduced-motion selectors do not receive the dot-specific declarations.

Follow-up verification (2026-07-14):

- `cd app-front-end && npm test -- --run src/components/__tests__/DispatchDotPulse.test.tsx`: pass (1 file, 3 tests).
- `npm run build`: pass (`tsc && vite build`; Vite production bundle generated successfully).
- `git diff --check`: pass (no output).
