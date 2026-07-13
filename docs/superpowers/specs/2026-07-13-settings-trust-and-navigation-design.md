# Settings Trust and Navigation Design

**Date:** 2026-07-13  
**Scope:** Fable Settings focused-mode redesign

## Goal

Preserve the new focused top-bar, desktop rail, and single reading-column layout while making persistence, recovery, navigation, feedback, and consequential controls immediately understandable.

## Information Architecture

Settings has two persistence groups and must describe them consistently everywhere:

1. **Fund policy — deploys as a version**
   - Fund thesis
   - Version context
   - Decision thresholds
   - Escalation sensitivity
   - Scoring weights
   - Memo output
   - Ruling workflow
2. **Live runtime — saves immediately**
   - Pipeline controls
   - Budget enforcement and limits
   - System state

The desktop rail and reading column use the same order. Version context is a navigable section. The terms `Administration`, `Configuration`, `Live` for deployable settings, and `Saves immediately` for memo/risk settings are removed.

## Restore Defaults

- Rename `Reset` to `Restore defaults`.
- Selecting it opens a compact confirmation takeover using the existing Aethria modal language.
- Confirmation replaces the editable draft with defaults but does not modify the saved/live snapshot.
- Restored values therefore remain pending and require deployment.
- After confirmation, show a temporary `Defaults restored · Undo` status beside the top-bar actions.
- Undo restores the pre-reset draft and clears the restore status.
- Restore and Undo are disabled while deployment is running.

## Deployment Feedback and Validation

- The fixed top bar owns visible deployment feedback because it owns the Deploy action.
- It shows `Live`, `Draft · N pending`, `Deploying…`, deployed success, restore/undo state, or the most important error.
- Detailed error text may remain in the document, but it cannot be the only visible feedback.
- Validation errors map to a section. Deploy failure scrolls and focuses the first invalid section, marks that rail/mobile destination as needing attention, and keeps the error announced through an accessible live region.
- Successful deployment clears attention state and changes the fixed status to Live.

## Navigation and Responsive Behavior

- Desktop retains the scroll-spy rail.
- Below `lg`, render a sticky section navigator directly beneath the top bar and above runtime controls.
- The mobile navigator is a labelled native select for dependable keyboard, touch, and screen-reader behavior.
- Options are grouped as `Fund policy` and `Live runtime`, and the current section remains selected as the user scrolls.
- Changing the selection uses the existing reduced-motion-aware section scroll.
- The live/draft status and pending count remain visible on mobile.
- Top-bar actions wrap without overlap at narrow widths; Deploy remains at least 44px high.

## Unsaved Exit Protection

- Leaving through the Aethria back action while deployable changes are pending opens a confirmation dialog.
- Copy distinguishes `Keep editing` from `Discard draft and leave`.
- Discarding restores the live configuration locally before navigating away.
- Browser refresh/close receives a standard `beforeunload` warning while deployable changes are pending.
- Immediate-save runtime changes never trigger the warning.

## Threshold Precision

- Keep the visual threshold bar and keyboard-operable slider handles.
- Restore explicit numeric inputs for Monitor start, Invest start, and Auto-pass ceiling beneath the bar.
- Inputs and slider operate on the same boundaries and preserve existing validation constraints.
- Consequential terms retain concise explanatory text.

## Readability and Error States

- Functional navigation, field labels, save states, and control statuses use at least 12px text and a foreground with at least 4.5:1 contrast against paper.
- Tiny uppercase mono type is limited to nonessential metadata.
- Validation fields use `aria-invalid` and linked error/help text where an error maps to a specific control.
- The settings-unavailable state offers `Retry` and `Back to Aethria` actions.
- Pipeline switches remain rounded and preserve optimistic save/rollback behavior.

## Component Boundaries

- `SettingsPage` continues to own draft data, deployment, validation, restore/undo, and navigation decisions.
- `SettingsTopBar` remains presentational and receives status, attention, restore, undo, deploy, and exit callbacks.
- `SettingsRail` renders the shared ordered navigation model and attention state.
- Add a focused `SettingsMobileNav` that consumes the same ordered navigation model.
- Add a focused confirmation component for restore/leave choices, reusing shared dialog patterns without changing the fund-thesis confirmation.
- `OperationsStrip` remains the immediate-save runtime control surface.

## Testing

- Unit-test restore defaults, pending-state preservation, Undo, and discard-on-leave behavior.
- Test top-bar mobile status visibility and 44px action targets.
- Test desktop and mobile navigation use the same section order, including Version context.
- Test validation routes focus/scroll attention to the first invalid section.
- Test restored numeric threshold inputs update the same boundaries as sliders.
- Preserve existing deployment confirmation, operations rollback, focus, and keyboard tests.
- Run the complete frontend test suite, lint, and production build.

## Non-Goals

- Do not replace the focused-mode top bar, rail, or single-column composition.
- Do not change backend APIs, Supabase schema, thesis versioning, policy publishing, or runtime settings persistence.
- Do not change the Dispatch or fund-thesis confirmation takeovers.
- Do not add a new animation library or component framework.
