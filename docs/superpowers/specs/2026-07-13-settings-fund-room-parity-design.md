# Settings Fund-Room Parity

Date: 2026-07-13

## Purpose

Settings currently behaves correctly but reads as a separate interface system. The Fund page is the source of truth for Aethria's room layout and visual language. Settings should use that same shell, hierarchy, spacing, typography, tab treatment, and golden-ratio composition without changing its persistence or deployment behavior.

This specification supersedes the layout and styling portions of the earlier Settings editorial-ledger specification. The ownership model, runtime-control behavior, draft deployment model, and fund-thesis confirmation remain unchanged.

## Room Architecture

Settings becomes a standard Aethria room like Fund:

- The outer page uses the shared `workspaceLayout.shell` with its `1180px` maximum width and canonical horizontal padding.
- A fixed paper top band contains `RoomHeader`, the pipeline controls, and the Decision / Administration tab row.
- Only the tab body scrolls. Switching tabs resets the body scroll to the top.
- The standard application spine remains visible. Settings no longer replaces it with section navigation or a deployment footer.
- The content canvas remains paper with Oxford typography and existing semantic colors.

The fixed header uses the established `RoomHeader` component:

- Eyebrow: **The operating model**
- Title: **Settings**
- Sub-action/status: a concise sentence distinguishing deployable drafts from immediate runtime controls.
- Right-side readouts: deployment state (**Live** or **Draft**), pending change count, active fund-thesis version, and active scoring-policy version.
- The primary **Deploy changes** action remains visible in this top band. It is disabled when no deployable changes exist or deployment is running.

## Pipeline Controls

The Scouts, Reviewers, Partners, and Cost budget switches stay above the tabs and remain visible on both tabs. They continue saving immediately and never enter the deployable draft.

The strip is constrained to the room shell rather than spanning an unrelated page frame. It uses the Fund page's compact readout rhythm: mono labels, quiet status text, original square switches, whitespace between controls, and one subtle structural rule. No boxed control grid or explanatory paragraphs are added.

## Navigation

Decision and Administration use the same tab vocabulary as `FundFacetNav`:

- Compact mono tab labels.
- One-pixel active underline.
- Quiet inactive text.
- Horizontal overflow on small screens.
- No secondary section rail.

The tabs retain their current keyboard behavior and ARIA semantics.

## Decision Composition

The Decision tab uses the Fund page's 61.8 / 38.2 reading-room composition.

### Fund thesis

The primary 61.8% column is the editable mandate document:

- Thesis statement and mandate identity receive the strongest typographic measure.
- Stages, geography, sectors, exclusions, business models, cheque size, ownership, and traction are presented as Fund-style specification rows.
- Labels use the established mono section-label role; values and controls use body typography.
- Chip selections remain usable but are visually quiet and square.

The 38.2% column contains thesis version context, publication behavior, and compact deployment guidance. It is not a card and uses sparse rows like Fund version history.

### Decision mechanics

A following 61.8 / 38.2 split pairs:

- Decision thresholds in the primary column.
- Escalation sensitivity in the secondary column.

The existing threshold visualization and validation remain intact but lose any layout treatment that conflicts with Fund's sparse instrument language.

### Scoring weights

Weights use the full room width as a ledger. Each row contains the dimension, explanation, impact, and numeric value with only subtle row dividers. Policy version metadata sits quietly below the ledger.

## Administration Composition

Administration uses two Fund-style 61.8 / 38.2 pairs:

1. Memo output in the primary column and Ruling workflow in the secondary column.
2. Cost budget in the primary column and System state in the secondary column.

Memo and workflow toggles keep the original square switch language. Cost limits remain read-only, because budget enforcement is controlled by the immediate-save strip. System state uses compact status rows without cards or per-row decoration.

## Deployment State

The custom Settings spine footer is removed. Deployment state moves into the fixed room header:

- **Live** when no deployable settings differ from the saved snapshot.
- **Draft** plus the pending count when deployable changes exist.
- **Deploy changes** remains reachable from either tab.
- Reset remains available as a quiet secondary action near deployment controls.

Clicking Deploy preserves the existing flow:

- Validation errors remain in the Settings room and are announced accessibly.
- A fund-thesis change opens the existing full-screen before/after confirmation.
- A non-thesis deployment proceeds directly.
- Runtime-control changes continue saving independently.

## Responsive Behavior

- Desktop and wide tablet: bounded room shell with 61.8 / 38.2 content splits.
- Narrow tablet and mobile: each pair becomes a single reading column, with the primary section before the secondary section.
- The header readouts wrap without overlapping the title or deployment action.
- Pipeline controls form a compact two-column grid before reaching one row at wider widths.
- Tabs remain horizontally scrollable.
- No content, heading, or action may overflow the viewport.

## Motion and Accessibility

- Reuse existing Aethria motion tokens and `Reveal`/tab transition conventions.
- Motion communicates room or tab state and remains under the product duration scale.
- Reduced-motion preferences receive immediate or crossfade behavior.
- All controls retain visible focus treatment, keyboard operation, labels, disabled states, and current ARIA semantics.
- Body copy remains within readable measure and muted text maintains adequate contrast.

## Component Boundaries

- Reuse `RoomHeader`, `workspaceLayout`, and the Fund tab styling rather than duplicating a new room system.
- Keep settings data and deployment orchestration in `SettingsPage`.
- Keep `OperationsStrip`, `DecisionThresholdsPanel`, and `FundThesisConfirmationModal` as focused components.
- Extract a small shared room-tab component only if both Fund and Settings can consume it without changing Fund behavior; otherwise reuse the established classes directly in Settings.
- Do not refactor unrelated Fund, Portfolio, Flow, or spine behavior.

## Testing

- Add layout-contract tests asserting Settings uses the shared room shell, fixed chrome, normal spine behavior, and Fund-style tab semantics.
- Preserve all settings model, operations-strip, threshold, deployment-gate, and thesis-confirmation tests.
- Run the complete frontend test suite, lint, and production build.
- If an authenticated visual session is unavailable, report that limitation rather than weakening automated verification.

## Out of Scope

- Changing which fields belong to Decision or Administration.
- Changing backend settings or fund-thesis APIs.
- Redesigning the fund-thesis confirmation takeover in this pass.
- Changing the Fund page itself.
- Modifying unrelated pending work in `SystemBar.tsx` or `PortfolioPage.tsx`.
