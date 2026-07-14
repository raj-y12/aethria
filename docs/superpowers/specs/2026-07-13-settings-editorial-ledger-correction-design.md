# Settings editorial-ledger correction

Date: 2026-07-13  
Scope: correction to the two-tab settings redesign  
Backend changes: none

## Correction

The first implementation treated Decision as all editable configuration and Administration as read-only live state. That is not the intended distinction.

The tabs group settings by what they control:

- **Decision** defines how the fund evaluates and decides.
- **Administration** defines how the product operates and presents its output.

Both tabs can contain deployable draft settings. The always-visible pipeline switches remain the only controls that save immediately.

## Selected visual direction

Use the approved **editorial ledger** direction.

- Remove the configuration preview entirely.
- Use one calm reading column instead of a content-plus-preview split.
- Restore the original compact switch treatment used by `ToggleRow`.
- Remove the boxed four-cell appearance from the operations strip.
- Use typography, indentation, and generous whitespace as the primary hierarchy.
- Keep only meaningful separators: one edge around the operations strip, field underlines, and occasional faint chapter dividers.
- Avoid generic cards, status tiles, and a dense register of horizontal lines.

## Persistent pipeline controls

The operations strip remains above the tabs and outside the scrolling content so it is visible in both modes.

It contains Scouts, Reviewers, Partners, and Cost budget. Each control:

- Uses the original 44-by-24 square-ended switch treatment.
- Shows a concise label and an `On`, `Off`, or `Saving` status.
- Saves immediately with the already-implemented optimistic PATCH behavior.
- Disables only itself while saving.
- Rolls back and shows one direct error line on failure.

The strip is a quiet toolbar, not four bordered cells. On narrow screens it wraps cleanly into two rows while retaining the same visual treatment.

## Decision tab

The Decision tab contains the settings that shape investment judgment:

1. **Fund thesis** — the current Fund Mandate fields, renamed to match the user's language.
2. **Decision thresholds** — the draggable Pass, Monitor, and Invest ladder plus precise numeric inputs.
3. **Scoring weights** — reviewer dimension weighting.
4. **Escalation sensitivity** — the conservative, balanced, or aggressive decision-sensitivity setting.

The heading becomes “How the fund decides.” The standfirst states that these changes remain draft until deployed.

Live fund-thesis and policy-version metadata appears as quiet secondary text near the relevant chapter, not as separate Administration sections.

## Administration tab

The Administration tab contains operational and presentation preferences:

1. **Memo output** — memo style, tone, evidence, missing-data, reasoning, and confidence display preferences.
2. **Ruling workflow** — acknowledgement and high-severity gating controls. Escalation sensitivity is not here because it changes judgment rather than workflow.
3. **Cost budget** — a clear read-only summary of the currently configured token and spend ceilings. The enabled switch remains in the persistent operations strip. Editing numeric ceilings remains out of scope, as previously agreed.
4. **System state** — concise storage, OpenAI, worker, and pipeline readiness. These are presented in a light textual summary with minimal rules.

The heading becomes “How the system operates.” The standfirst explicitly distinguishes the two save models: preferences below deploy as a draft; pipeline switches above save immediately.

## Deployment behavior

Removing the preview does not remove deployment controls.

- The spine deployment footer remains visible on both tabs.
- The compact mobile deployment action remains visible on both tabs.
- Pending changes continue to include mandate, scoring, memo-output, and ruling-workflow edits.
- The action label is “Deploy changes.”
- Switching tabs never loses draft work.
- Runtime strip changes never appear in the pending list and never require deployment.

This is necessary because Administration contains `fund_config` preferences that still use the existing transactional publish flow.

## Navigation

The spine groups sections under the corrected tab ownership:

### Decision

- Fund thesis
- Decision thresholds
- Scoring weights
- Escalation sensitivity

### Administration

- Memo output
- Ruling workflow
- Cost budget
- System state

Selecting a spine item switches tabs before scrolling, as in the current implementation.

## Component changes

### `SettingsPage.tsx`

- Remove `PreviewPanel` and `SettingsSidebarFooter`.
- Reorder and reassign the settings chapters.
- Keep deployment status projected into the spine for both tabs.
- Add a restrained budget summary using existing `settings.cost_budget` values.
- Replace the current line-heavy Administration register with editorial summaries.
- Update headings and explanatory copy.

### `settingsModel.ts`

- Correct `SETTINGS_SECTIONS` ownership and labels.
- Keep the existing pending-change model because both tabs contain deployable settings.

### `OperationsStrip.tsx`

- Preserve save logic and tests.
- Replace the bordered cell grid with a sparse toolbar.
- Reuse the original switch proportions and motion.

### `DecisionThresholdsPanel.tsx`

- Preserve interaction and accessibility behavior.
- Reduce surrounding visual rules only if needed for the ledger rhythm.

## Comprehension rules

- Every tab heading explains what belongs there.
- Every editable chapter states its consequence in one sentence.
- “Saves immediately” appears only with the pipeline strip.
- “Deploy changes” appears with draft-backed preferences on both tabs.
- Status is communicated with text first; color remains secondary.
- Technical IDs and timestamps remain secondary metadata.

## Verification

Automated checks will cover:

- Correct section-to-tab mapping.
- Pending memo and ruling changes remaining deployable from Administration.
- Operations still excluded from pending changes.
- Operations PATCH success and rollback behavior.
- Threshold keyboard and conversion behavior.
- Preservation of unsaved draft settings across operations saves and tab changes.
- Full frontend unit suite, ESLint, and production build.

Visual checks will cover:

- No preview column at desktop widths.
- Operations controls remain visible and use the original switch form.
- The strip wraps without bordered-cell clutter on narrow screens.
- Both tabs retain a clear deployment action.
- Decision and Administration each read as a coherent sequence.
- Divider count is materially lower than the first implementation.

## Out of scope

- Backend or database changes
- Editing numeric cost-budget ceilings
- URL-synchronized tabs
- New operational telemetry
- A new card system or component library
