# Spine and Dispatch Motion Restoration

## Goal

Restore the earlier synchronized workspace-and-spine transition and add the missing Dispatch exit animation without changing Dispatch's internal lookup-stage choreography.

## Current Problem

`AppFrame` still animates the spine itself, but the workspace's position layout animation was removed. The spine therefore moves independently instead of shifting the workspace in the earlier coordinated way.

`DispatchCommandBar` also returns `null` as soon as `open` becomes false. Because it is plain conditionally rendered markup rather than an `AnimatePresence` child, Framer Motion never receives an exit phase. The spine can begin returning at the same time, producing an abrupt transition.

## Chosen Design

`AppFrame` owns the complete chrome transition lifecycle.

- Restore `layout="position"` and the shared chrome transition on the workspace `motion.main`.
- Render Dispatch through `AnimatePresence` as a keyed motion surface.
- Make closing the exact reciprocal of opening: Dispatch follows the same path backward while the spine and workspace reverse their opening motion at the same time.
- Keep the desktop spine, mobile chrome, workspace, and Dispatch transitions concurrent in both directions; do not serialize their animations.
- Use the same 500 ms spine/workspace position transition during bare Home → full Flow chrome changes.
- Hold the existing Flow queue stagger until that chrome transition completes, then release it from the actual Framer Motion completion callback.
- Keep Dispatch's internal views, progress stages, result presentation, and focus behavior unchanged.
- Preserve all existing Flow row, empty-state, selected-memo, readout, and micro-interaction animations.
- Do not auto-select the first Flow row. The memo remains closed until a row click or an explicit `?open=<id>` deep link selects a deal.

This centralizes coordination where the spine, workspace, and Dispatch are already composed. Dispatch remains responsible for its content while `AppFrame` remains responsible for application chrome.

## Motion Contract

For normal motion preferences:

1. Opening Dispatch starts all frame motion together: the spine slides/fades from `x: 0` to `x: -28`, the workspace expands with position layout animation, and Dispatch fades from `opacity: 0` to `1` while moving from `y: 10` to `y: 0`.
2. Closing Dispatch starts the exact reverse at the same time: the spine slides/fades from `x: -28` to `x: 0`, the workspace contracts with the same position layout animation, and Dispatch fades from `opacity: 1` to `0` while moving from `y: 0` to `y: 10`.
3. Each element uses the same duration and easing in both directions. No element waits for another element's exit callback.
4. Home → Flow uses the same 500 ms spine/workspace entrance. Flow content renders in its initial animation state during that movement; the existing queue stagger begins immediately after the chrome completion callback.
5. The queue keeps its existing `26 ms` row stagger, and the existing empty-state, selected-memo, readout, and micro-interaction animations remain unchanged.
6. Flow starts without an active memo. Clicking a row or following an explicit memo deep link sets the selection and runs the existing memo reveal animation; no timer or automatic first-row selection opens it.

For reduced motion:

- Remove spatial translation and layout choreography.
- Use an effectively immediate opacity transition.
- Preserve the same sequencing so focus and visibility do not flash or overlap.

## State and Lifecycle

`dispatch.commandBarOpen` remains the sole source of truth for Dispatch and chrome visibility. When it becomes false, `AnimatePresence` retains the Dispatch surface for its exit while the spine/mobile chrome mount immediately and animate in concurrently.

`AppFrame` records whether it is entering full chrome from a bare page. During that entrance it exposes `workspaceChromeReady: false` through the frame context. The desktop spine or mobile chrome sets it to true from its Framer Motion `onAnimationComplete` callback.

`FlowPage` passes `workspaceChromeReady` to `WorkGrid`. `WorkGrid` retains its existing variants but stays in `hidden` until the frame is ready, then switches to `visible` and runs its current stagger. Reduced motion resolves readiness immediately. No fixed timeout or Dispatch exit-pending state is required.

Memo selection remains owned by `FlowPage`. Ordinary entry leaves `selectedStartup` null. Row clicks and the existing `?open=<id>` route are the only automatic inputs that set it; `WorkGrid` has no first-row auto-selection effect.

## Accessibility

- Keep the existing dialog semantics and focus trap while Dispatch is open.
- Keep Escape and explicit Exit actions routed through the same close path.
- Release scroll lock from logical open state as today; the short exit surface remains non-interactive once closing begins.
- Respect the existing reduced-motion preference helper.

## Testing

Add focused regression coverage that proves:

- the workspace uses position layout animation with the shared chrome transition during Dispatch and Home → Flow motion;
- Dispatch exposes reciprocal `y: 10 → 0` enter and `y: 0 → 10` exit states inside `AnimatePresence`;
- spine/mobile chrome visibility follows logical Dispatch open state so their return overlaps the retained exit surface;
- bare → full chrome keeps `workspaceChromeReady` false until the spine/mobile entrance completes;
- Flow passes readiness to `WorkGrid`, which releases its existing `26 ms` row stagger only after completion;
- existing Flow empty-state, selected-memo, readout, and micro-interaction animations remain present;
- ordinary Flow entry does not auto-select a row or render a memo;
- row clicks and explicit `?open=<id>` deep links still render the memo with its existing reveal;
- reduced motion removes spatial movement while retaining a valid exit phase.

Run the focused tests, the frontend test suite relevant to app-frame choreography, TypeScript/build verification, and lint if configured.

## Non-Goals

- Redesigning Dispatch content or lookup stages.
- Changing spine dimensions, typography, navigation, or information hierarchy.
- Adding a new animation library or changing global motion tokens.
- Refactoring unrelated settings or pipeline behavior.
