# Settings two-mode control room

Date: 2026-07-13  
Scope: `app-front-end/src/settings/` plus focused frontend tests  
Backend changes: none

## Outcome

Settings will clearly separate two kinds of control:

- **Decision configuration** changes how Aethria evaluates companies. These edits remain drafts until the user deploys them.
- **Operations** changes whether pipeline stages and cost enforcement are running. These switches save immediately and never appear as pending decision changes.

The page will preserve Aethria's paper-and-Oxford editorial language, squared geometry, existing typography, and single-page route. The redesign must be understandable without relying on tooltips or prior knowledge of the pipeline.

## Problems in the current page

1. Runtime switches share the same draft-and-deploy transaction as investment policy. A user can switch Scouts off and reasonably believe the pipeline stopped even though nothing changes until Deploy.
2. Six unrelated sections create one long settings register with no clear distinction between investment thinking and system administration.
3. Kill switches are buried inside the Operations section instead of remaining available while the user edits the page.
4. Escalation sensitivity is decision policy but currently sits beside runtime controls.
5. The configuration preview and deploy controls occupy space even when the user is reading system state.
6. The threshold bar communicates values but does not communicate that those values are adjustable.
7. Agent and storage status are fetched but not presented as a useful administrative summary.
8. Operations snapshot and dirty-state logic make the save model harder to reason about and allow operational changes to pollute the decision pending list.

## Information architecture

The page keeps the existing `/v1/settings` route and introduces local tab state with two modes.

### Operations strip

A compact strip sits above the tab bar and remains visible while the page content scrolls. It contains exactly four controls:

- Scouts
- Reviewers
- Partners
- Cost budget

The strip includes a short label explaining that changes apply immediately. Each switch saves independently. The budget switch controls only `cost_budget.enabled`; numeric ceilings and other budget configuration remain unchanged and out of scope.

On wide screens the controls form one horizontal row. On narrow screens they form a compact two-column grid so labels and states remain readable without horizontal clipping.

### Decision tab

The default tab contains all draft-and-deploy configuration, ordered to match the user's mental model:

1. Fund mandate
2. Memo output
3. Ruling, including escalation sensitivity
4. Decision thresholds
5. Scoring weights

The existing configuration preview and deployment controls appear only in this tab. Pending changes describe only decision configuration.

### Administration tab

This tab is read-only in this pass and presents a compact system register:

- Live scoring policy ID and last-published time
- Active fund thesis version and what the next deploy will do
- Storage readiness, including whether Supabase is configured
- Agent runtime status already available from `fetchAgentsStatus()`

The presentation uses aligned rows, explicit status language, and short explanations rather than generic dashboard cards. It contains no Deploy action because there is no draft state in Administration.

## Navigation

The tab bar uses semantic tab roles, visible focus states, `aria-selected`, and standard left/right arrow keyboard navigation.

The existing spine remains the section navigator. Its destinations are grouped under Decision and Administration headings. Selecting a destination in the inactive tab first switches tabs, then scrolls to the destination after it mounts. Scroll-spy observes only mounted sections and reattaches when the active tab changes.

Switching tabs never discards work because the decision draft remains owned by `SettingsPage`, above the tab content.

On the Administration tab, the spine omits decision draft/deploy controls. Returning to Decision restores the current pending state and actions.

## Immediate-save operations

`OperationsStrip` receives the current settings value, storage readiness, and a callback for reconciling successful responses. Each switch owns its own in-flight and error state.

When a user changes a switch:

1. Update that switch optimistically.
2. Disable only that switch while its PATCH is in flight.
3. Call `patchSettings()` with the complete relevant nested object: either `agent_config` or `cost_budget`. This avoids losing sibling fields while still using the backend's partial top-level contract.
4. On success, replace the page's settings state with the authoritative response and update the `['settings']` TanStack Query cache.
5. On failure, restore the previous value and show a direct one-line error inside the strip.

When Supabase is known to be unavailable, all four switches are disabled and the strip explains why. Other switches remain usable when any single request is in flight.

The redesign removes `serializeOperations`, `savedOperationsSnapshot`, `operationsDirty`, and the Operations pending-change bucket.

## Decision threshold ladder

The existing Pass, Monitor, and Invest band remains the visual foundation. It gains three controls tied to the same draft values as the numeric fields:

- Auto-pass ceiling tick inside the Pass region
- Pass/Monitor boundary divider
- Monitor/Invest boundary divider

Each handle has a minimum 44px interactive target while its visible mark remains visually restrained. Pointer interaction uses pointer capture and converts `clientX` within the bar bounds into a rounded 0–100 score. Updates pass through `applyDecisionThresholds()` so drag, keyboard, and text input share one source of truth and one clamping policy.

Each handle uses `role="slider"`, an explicit accessible name, `aria-valuemin`, `aria-valuemax`, and `aria-valuenow`. Arrow keys adjust by one point. Home and End move to the current valid minimum or maximum. Numeric inputs remain below the ladder for precise editing.

Labels and score ranges update live. The handles must remain distinguishable without relying on color alone.

## Language and comprehension

The page uses plain, specific language:

- "Applies immediately" for operations
- "Deploy decision changes" for the transaction button
- "Saved" or a direct error beside operational controls
- "Storage unavailable" rather than internal configuration jargon where possible
- One-sentence descriptions that state the consequence of a control

Labels use sentence case. Technical identifiers may appear as secondary metadata, never as the only explanation. Statuses pair color with text.

## Component boundaries

### `SettingsPage.tsx`

- Owns tab state, decision draft state, settings reconciliation, navigation, and deploy behavior.
- Renders the operations strip above tab content.
- Renders decision or administration sections according to the selected tab.
- Projects grouped navigation and tab-appropriate footer content into the spine.

### `OperationsStrip.tsx`

- Renders the four immediate-save switches.
- Manages optimistic values, per-switch in-flight state, and inline errors.
- Uses the existing typed settings client and query cache.

### `DecisionThresholdsPanel.tsx`

- Adds pointer and keyboard control to the threshold visualization.
- Delegates all valid-value enforcement to existing decision-threshold helpers.

No new runtime dependency or route is introduced.

## Error and edge states

- A failed operations PATCH reverts only the affected switch and keeps the other controls available.
- A successful response is authoritative if the backend normalizes settings.
- Decision deploy and operations PATCH may overlap because they write disjoint top-level concerns; subsequent refetching reconciles the shared settings cache.
- Missing agent-status data is shown as "Status unavailable," not treated as storage failure.
- Known missing Supabase configuration disables operational controls and is explained in both the strip and Administration.
- Long policy IDs wrap safely or use copy-friendly selectable text.
- Reduced-motion preferences are respected; dragging itself does not require decorative motion.

## Verification

Automated checks will cover:

- Pointer-position-to-score conversion and boundary clamping
- Slider keyboard behavior and accessible attributes
- Optimistic switch updates, partial payload shape, success reconciliation, and failure rollback
- Pending-change calculation excluding operations
- Tab semantics and inactive-section navigation where practical
- Existing decision threshold and fund configuration regression tests
- TypeScript build and ESLint

Browser verification will confirm:

- All four switches save without Deploy and retain their state after refresh
- Only the changed switch disables during a request
- Failure rollback and the inline message are understandable
- Decision edits remain pending across tab switches
- Administration has no misleading Deploy control
- Dragging and numeric editing stay synchronized
- Keyboard users can operate tabs, switches, and all three threshold handles
- Wide and narrow layouts remain readable and do not clip controls

## Out of scope

- Backend or database changes
- Numeric cost-budget editing
- URL-synchronized tabs
- Per-toggle audit history
- New operational telemetry
- Drag animation libraries or decorative spring effects
