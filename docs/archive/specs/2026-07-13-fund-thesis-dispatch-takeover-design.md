# Fund Thesis Dispatch Takeover Design

**Date:** 2026-07-13  
**Scope:** `app-front-end/src/settings/FundThesisConfirmationModal.tsx`

## Goal

Make fund-thesis confirmation feel like the Dispatch screen in both composition and styling while preserving the existing explicit confirmation behavior.

## Visual Structure

- Use the Dispatch full-screen paper dot-grid canvas.
- Center the entire confirmation experience vertically and horizontally within the takeover.
- Remove the current bordered header, independent scrolling body, and sticky footer bars.
- Use the Dispatch hierarchy: compact centered eyebrow, centered display title, short centered explanatory copy, focused content, then inline footer actions.
- Match Dispatch reveal timing and upward entrance cadence, with reduced-motion support.

## Confirmation Content

- Eyebrow: `Fund thesis change`.
- Title: `Confirm the new mandate`.
- Supporting copy explains that deployment makes the proposed thesis immediately active for Scouts and Reviewers. First publication keeps its distinct explanation.
- Show the change comparison in a centered, width-limited review panel beneath the introduction.
- Keep `Currently live` and `Proposed` columns on wider screens. Stack each field's previous and proposed values clearly on narrow screens.
- Keep the comparison visually quiet: one restrained boundary around the review panel and subtle internal rules only where they aid scanning.

## Actions and Interaction

- Replace the separate footer buttons with Dispatch-style inline underlined actions beneath the review panel: `Go back · Confirm update`.
- Preserve explicit manual confirmation; no timeout, automatic deployment, or implicit confirmation.
- Preserve focus trapping, initial focus on the confirm action, Escape-to-cancel when idle, focus restoration, and busy-state disabling.
- Busy copy becomes `Updating fund thesis…`.

## Accessibility and Responsive Behavior

- Retain `role="dialog"`, `aria-modal`, labelled title, and descriptive copy.
- The takeover may scroll as one surface when the comparison exceeds the viewport; it must not introduce nested scroll regions.
- Maintain visible focus styles and at least 44px action targets despite the visually compact inline treatment.
- Long values wrap without overflowing.

## Testing

- Update the modal tests to assert Dispatch parity markers: dot-grid canvas, centered takeover structure, no header/footer elements, and inline action labels.
- Preserve tests for focus, Escape handling, confirmation, cancellation, first-publication copy, and busy state.
- Run the focused modal tests, full frontend tests, lint, and production build.

## Non-Goals

- No change to thesis diff generation, settings deployment, backend APIs, or persistence.
- No change to the Dispatch component itself.
- No new modal abstraction or animation library.
