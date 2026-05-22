# Left rail density reduction design

## Goal

Reduce the perceived density of the desktop left rail in `src/components/MainLayout.tsx` without losing the existing editorial styling, justified spacing rhythm, or the information the rail currently exposes.

The user feedback is specific:

- The overall styling direction is good.
- The rail feels overcramped and reads as information overload.
- The pipeline overview concept is good, but the current section feels structurally wrong.
- Dispatch carries too much permanent visual weight.
- The fund thesis / mandate section breaks down when too many tags are rendered.

This design keeps the current left-rail concept and typography system, but changes the information hierarchy so each section communicates one main idea instead of several stacked sub-panels.

## Approved direction

The approved direction is:

- Overall rail structure: quiet stack
- Pipeline overview: split summary
- Dispatch: status-first
- Mandate: inline thesis line

This should make the rail feel like a calm operating column rather than a compressed dashboard.

## Scope

In scope:

- Desktop left rail content in `src/components/MainLayout.tsx`
- Desktop rail dispatch rendering through `src/components/AgentDispatch.tsx`
- Desktop mandate / fund thesis summary mapping in `src/components/MainLayout.tsx`
- Minor supporting style adjustments needed to preserve the current editorial rhythm

Out of scope:

- Mobile header and mobile rail summaries
- Work grid, memo panel, or right-side panel structure
- Backend or API contract changes
- New data fields or new product behavior beyond presentation and section expansion/collapse behavior

## Existing problems

### Pipeline overview

The current pipeline block reads as four stacked slices:

1. Header row
2. Large primary metric row
3. Pipeline status row
4. Total / decided two-column footer

This creates too many horizontal dividers and too many changes in emphasis inside one compact area. The section concept is correct, but the composition feels like multiple mini-cards attached together.

### Dispatch

Desktop rail dispatch is always open through `alwaysOpen`, so the rail permanently displays:

- input field
- action button
- helper text
- runtime message state
- phase line

That is too much visual machinery for an on-demand action that is usually idle.

### Mandate

The current mandate card can render a large tag set from `thesisTagList`, which turns the section into a wrapped metadata wall. The section loses hierarchy because the fund name has to compete with many equivalent chips.

## Target experience

The desktop left rail should read top-to-bottom like this:

1. Wordmark / nav
2. Pipeline section with one dominant summary and one subordinate summary cluster
3. Dispatch section that reads primarily as state, with action secondary
4. Mandate section that reads as one calibrated thesis line, not many separate badges
5. Account section

Every section should feel like one thought. Dividers should separate sections, not subdivide sections into many internal panels unless there is a strong interaction reason.

## Section designs

### 1. Quiet stack rail structure

The left rail remains a vertically justified stack with the current editorial language and spacing system. The change is not a layout rewrite; it is a density reduction inside each section.

Rules:

- Preserve the existing vertical distribution and section ordering.
- Keep the current mono labels and editorial text treatment.
- Reduce internal borders inside sections wherever they create fake subcards.
- Prefer one clear summary line over multiple secondary micro-lines.

### 2. Pipeline overview: split summary

The approved pipeline treatment is split summary.

Structure:

- Top row: `Pipeline` label on the left, status token (`Live`, `Idle`, `Off`, `Issue`) on the right
- Main content row:
  - left side: primary number (`open / in-progress` or escalations when escalations exist)
  - right side: two small ledger rows for `Total` and `Decided`

Behavior:

- Keep the existing escalation override behavior:
  - when `pendingEscalations > 0`, the primary number becomes escalations and uses escalation tone
- Keep status derivation logic exactly as today:
  - `OFF`, `ISSUE`, `ACTIVE`, `IDLE`
- Keep issue help behavior, but integrate it into the quieter section without recreating the current multi-panel look

Layout intent:

- The big number remains the anchor
- Supporting metrics move into a quieter right-side ledger
- Internal section borders are minimized
- The section should read as one composed block, not four stacked strips

### 3. Dispatch: status-first

The approved dispatch treatment is status-first.

Idle state should show:

- `Dispatch` label
- short state text such as `Idle` or `Ready`
- one short explanatory line like `No lookup in flight.`
- one action affordance line like `Run lookup →`

Interaction:

- The full input should not dominate the rail at rest
- Clicking the action affordance should expand or reveal the real input affordance
- If a lookup is running, the section can expand into the current active state UI
- If a result or runtime message exists, the section can temporarily use the richer active state layout

Behavioral requirement:

- Existing lookup functionality remains intact
- Existing cancel behavior remains intact
- Existing phase display remains available during active runs
- Only the idle presentation changes materially

Implementation direction:

- `AgentDispatch` should gain a desktop embedded idle mode that renders a compact status-first shell before expanding into the existing control surface
- Avoid duplicating lookup state logic in `MainLayout`
- Keep the component as the main owner of its interaction state

### 4. Mandate: inline thesis line

The approved mandate treatment is inline thesis line.

Structure:

- `Mandate` label
- fund name
- one compact uppercase thesis line, for example:
  - `Seed to Series A · Europe and US · B2B infrastructure`

Rules:

- Replace the multi-chip display in the desktop rail
- Reduce the thesis summary to at most one line, or a visually controlled wrapped second line if space forces it
- Keep the existing live indicator only if it does not compete with the fund name; otherwise de-emphasize it

Mapping logic:

- Reuse current thesis sources (`stage`, `geography`, `sectors`)
- Collapse them into a single ordered string instead of rendering individual tags
- Order should remain stable and predictable:
  - stage
  - geography
  - sector / focus

Fallbacks:

- If only one or two thesis fragments exist, render only those fragments
- If no thesis fragments exist, render no thesis line and keep only the fund name / empty fallback

## Component boundaries

### `src/components/MainLayout.tsx`

Responsibilities after change:

- Own the quiet stack composition
- Pass normalized mandate summary text rather than a raw tag list for desktop rail rendering
- Render the revised pipeline overview block
- Use the compact desktop dispatch presentation

### `SystemTelemetryRail` in `src/components/MainLayout.tsx`

Responsibilities after change:

- Keep the existing data inputs and status derivation
- Change presentation from stacked segmented card to one quieter split-summary composition
- Preserve issue help toggle

### `src/components/AgentDispatch.tsx`

Responsibilities after change:

- Support a compact embedded idle state for desktop rail use
- Expand into richer interaction state only on intent or active lookup state
- Preserve current drawer behavior outside the desktop rail path unless a shared cleanup falls out naturally

## Data flow

No backend or query changes are needed.

Frontend-only transformation changes:

- `thesisTagList` can continue to exist for other surfaces if needed
- desktop rail should derive a single `mandateSummaryLine` from the same source values
- pipeline metrics continue to use the existing counts and status inputs
- dispatch continues to use the current lookup props and phases

## Error and edge handling

### Pipeline issue state

- `Issue` state still needs visible distinction
- the issue explainer must remain accessible
- the section should not expand back into the old stacked-card feel just because an issue exists

### Long mandate data

- Very long geography or sector values must truncate or wrap in a controlled way
- The section must never return to an uncontrolled tag cloud

### Dispatch active state

- While a lookup is in flight, active information takes precedence over compactness
- The active state can temporarily expand within the section
- Once the active state is cleared, the component should return to status-first idle presentation

## Testing

### Visual

- Desktop left rail at standard desktop width
- Narrow desktop width where the rail has less horizontal room
- Long mandate summary cases
- Escalation-present pipeline state
- Pipeline issue state
- Idle dispatch vs active dispatch

### Functional

- On-demand lookup still submits successfully
- Active lookup still exposes cancel behavior
- Lookup messages still display and clear correctly
- Pipeline issue help still opens settings path correctly

## Risks

### Risk: dispatch becomes too hidden

If the compact status-first idle state becomes too subtle, on-demand lookup may feel less discoverable.

Mitigation:

- Keep a clear action affordance like `Run lookup →`
- Preserve expansion on click

### Risk: mandate summary becomes too compressed

Collapsing thesis metadata into one line may hide useful nuance.

Mitigation:

- Use stable ordering and concise terms
- Keep full thesis detail elsewhere in settings / system surfaces

### Risk: pipeline summary loses urgency

Reducing the stacked sections may make the pipeline feel less alive.

Mitigation:

- Preserve one strong primary metric
- Preserve status token and escalation emphasis

## Implementation notes

- This should be a focused refactor, not a redesign of the whole layout
- Preserve current type choices and existing tokens unless a small adjustment is required to make the new hierarchy work
- Prefer deleting structure over adding more structure
- Do not add new decorative badges or additional metadata rows
