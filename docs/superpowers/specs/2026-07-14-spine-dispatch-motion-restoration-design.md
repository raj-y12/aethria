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
- Dispatch enters with the existing restrained product motion language and exits by fading while lifting slightly upward.
- Keep the desktop spine and mobile chrome hidden until the Dispatch exit animation completes; only then begin their return animation.
- Keep Dispatch's internal views, progress stages, result presentation, and focus behavior unchanged.

This centralizes coordination where the spine, workspace, and Dispatch are already composed. Dispatch remains responsible for its content while `AppFrame` remains responsible for application chrome.

## Motion Contract

For normal motion preferences:

1. Opening Dispatch slides/fades the spine away while the workspace reflows with position layout animation.
2. Dispatch enters as a full-frame paper surface with a short fade and small upward settle.
3. Closing Dispatch fades and lifts the takeover out.
4. After that exit completes, the spine/mobile chrome returns and the workspace shifts into place with the restored synchronized position animation.

For reduced motion:

- Remove spatial translation and layout choreography.
- Use an effectively immediate opacity transition.
- Preserve the same sequencing so focus and visibility do not flash or overlap.

## State and Lifecycle

`dispatch.commandBarOpen` remains the source of truth for whether Dispatch is logically open. A small frame-level transition state records whether the closing surface is still present. The visibility rules for the spine and mobile chrome include that transition state, preventing them from returning underneath a still-exiting Dispatch surface.

The transition state is cleared by the presence exit-complete callback rather than a hard-coded timeout, so duration token changes cannot desynchronize the sequence.

## Accessibility

- Keep the existing dialog semantics and focus trap while Dispatch is open.
- Keep Escape and explicit Exit actions routed through the same close path.
- Release scroll lock from logical open state as today; the short exit surface remains non-interactive once closing begins.
- Respect the existing reduced-motion preference helper.

## Testing

Add focused regression coverage that proves:

- the workspace uses position layout animation with the shared chrome transition;
- Dispatch exposes distinct enter and exit motion states inside `AnimatePresence`;
- the spine/mobile chrome visibility condition includes the Dispatch exit lifecycle;
- reduced motion removes spatial movement while retaining a valid exit phase.

Run the focused tests, the frontend test suite relevant to app-frame choreography, TypeScript/build verification, and lint if configured.

## Non-Goals

- Redesigning Dispatch content or lookup stages.
- Changing spine dimensions, typography, navigation, or information hierarchy.
- Adding a new animation library or changing global motion tokens.
- Refactoring unrelated settings or pipeline behavior.
