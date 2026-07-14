# Fund Thesis Deploy Confirmation

Date: 2026-07-13

## Purpose

Publishing a fund-thesis change alters what the pipeline discovers and how it evaluates companies. A thesis change must therefore require a separate, explicit confirmation before the existing deployment transaction begins.

## Trigger

- Clicking any existing **Deploy changes** action first runs the current validation.
- If validation fails, the existing errors remain on the settings page and no confirmation opens.
- If validation succeeds and any field in `FundConfiguration.mandate` differs from the saved configuration, open the confirmation takeover.
- A change to scoring, thresholds, escalation, memo output, or ruling workflow without a mandate change deploys through the existing flow without this extra confirmation.
- The first thesis publication is treated as a thesis change. The previous side displays that no thesis is currently deployed.

## Interaction Design

The confirmation is a full-viewport modal takeover that follows the established `AgentLogoutModal` language:

- Render through a portal above the app shell.
- Use the paper background, Oxford text, square geometry, existing typography roles, and existing primary/secondary button styles.
- Use Framer Motion with the existing restrained ease and honor reduced-motion preferences.
- Use `role="dialog"`, `aria-modal="true"`, a labelled title, focus trapping, focus restoration, and Escape-to-cancel.
- The modal heading is **Confirm fund thesis change**.
- Supporting copy explains that Scouts and Reviewers will use the proposed thesis after deployment.

The review area shows only mandate fields whose normalized display values changed. On desktop, each changed field is a three-column editorial row: field label, **Currently live**, and **Proposed**. On small screens, the current and proposed values stack under the field label. Long thesis text preserves readable wrapping. Empty values display **Not set**. The first publication displays **No thesis currently deployed** as the previous state.

Actions remain visible at the bottom of the takeover:

- Primary: **Yes, update fund thesis**
- Secondary: **Go back**

The confirmation is deliberately binary. There is no background-click dismissal and no preselected checkbox. The user must activate the primary action manually. Escape and **Go back** close the takeover without saving.

## Data and Component Boundaries

Add pure helpers in `settingsModel.ts`:

- Parse the saved serialized configuration safely.
- Detect whether the mandate changed.
- Produce display-ready changed rows from the saved and proposed mandates.

The row model contains a stable field key, human-readable label, previous value, and proposed value. Arrays are displayed as comma-separated text; money and percentages use concise human-readable formatting.

Add a focused `FundThesisConfirmationModal` component under `src/settings/`. It receives `open`, the changed rows, a first-publication flag, `onCancel`, and `onConfirm`. It owns only presentation, keyboard handling, focus trapping, and focus restoration.

`SettingsPage` separates deployment intent from deployment execution:

- The existing deploy buttons call a request function.
- The request function validates and either opens the thesis confirmation or starts deployment directly.
- The modal's confirmation closes the modal and invokes the existing deployment transaction exactly once.
- While deployment is running, existing loading and error behavior remains authoritative.

Runtime switches above the tabs are unrelated and continue saving immediately without this confirmation.

## Error and Edge-Case Behavior

- Malformed or missing saved snapshots fail safely and treat a present draft mandate as requiring confirmation.
- Closing the modal leaves every draft edit intact.
- Reopening after further edits recomputes the comparison from the latest draft.
- Confirming cannot double-submit while deployment is in progress.
- If deployment fails after confirmation, the user returns to the settings page with the existing error message and the draft remains available.

## Tests

- Pure unit tests cover unchanged mandates, each class of mandate change, first publication, empty values, and malformed snapshots.
- Component tests cover rendered before/after values, omitted unchanged fields, Escape cancellation, manual confirmation, focus behavior, and disabled confirmation while busy.
- Existing settings tests, full lint, and the production build must continue to pass.

## Out of Scope

- Backend schema or endpoint changes.
- Confirmation for non-thesis settings.
- Editing values inside the confirmation takeover.
- Replacing the app's modal design system.
