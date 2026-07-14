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
- Disable workspace position layout animation during bare Home → full Flow chrome changes so the Flow row stagger begins in stable final geometry.
- Keep Dispatch's internal views, progress stages, result presentation, and focus behavior unchanged.

This centralizes coordination where the spine, workspace, and Dispatch are already composed. Dispatch remains responsible for its content while `AppFrame` remains responsible for application chrome.

## Motion Contract

For normal motion preferences:

1. Opening Dispatch starts all frame motion together: the spine slides/fades from `x: 0` to `x: -28`, the workspace expands with position layout animation, and Dispatch fades from `opacity: 0` to `1` while moving from `y: 10` to `y: 0`.
2. Closing Dispatch starts the exact reverse at the same time: the spine slides/fades from `x: -28` to `x: 0`, the workspace contracts with the same position layout animation, and Dispatch fades from `opacity: 1` to `0` while moving from `y: 0` to `y: 10`.
3. Each element uses the same duration and easing in both directions. No element waits for another element's exit callback.
4. Home → Flow changes the frame from bare to full chrome without workspace position layout animation, preserving the existing immediate Flow row stagger.

For reduced motion:

- Remove spatial translation and layout choreography.
- Use an effectively immediate opacity transition.
- Preserve the same sequencing so focus and visibility do not flash or overlap.

## State and Lifecycle

`dispatch.commandBarOpen` remains the sole source of truth for Dispatch and chrome visibility. When it becomes false, `AnimatePresence` retains the Dispatch surface for its exit while the spine/mobile chrome mount immediately and animate in concurrently.

`AppFrame` records only whether its `chrome` prop changed between bare and full modes. Position layout animation is disabled for that render so route-level Home → Flow choreography does not inherit Dispatch motion. No timeout or Dispatch exit-pending state is required.

## Accessibility

- Keep the existing dialog semantics and focus trap while Dispatch is open.
- Keep Escape and explicit Exit actions routed through the same close path.
- Release scroll lock from logical open state as today; the short exit surface remains non-interactive once closing begins.
- Respect the existing reduced-motion preference helper.

## Testing

Add focused regression coverage that proves:

- the workspace uses position layout animation with the shared chrome transition during Dispatch motion;
- Dispatch exposes reciprocal `y: 10 → 0` enter and `y: 0 → 10` exit states inside `AnimatePresence`;
- spine/mobile chrome visibility follows logical Dispatch open state so their return overlaps the retained exit surface;
- bare ↔ full chrome changes disable workspace layout animation for Home → Flow;
- reduced motion removes spatial movement while retaining a valid exit phase.

Run the focused tests, the frontend test suite relevant to app-frame choreography, TypeScript/build verification, and lint if configured.

## Non-Goals

- Redesigning Dispatch content or lookup stages.
- Changing spine dimensions, typography, navigation, or information hierarchy.
- Adding a new animation library or changing global motion tokens.
- Refactoring unrelated settings or pipeline behavior.
