# Aethria product UI recalibration

**Date:** 2026-07-10  
**Status:** Approved direction, implementation pending  
**Scope:** Authenticated product UI in `app-front-end`; no backend behavior or route changes unless explicitly required by an existing UI contract.

## Objective

Make Aethria feel like a calm, trustworthy investment operating system rather than a ceremonial interpretation of one. Preserve the recognizable identity—Oxford and paper, square geometry, restrained verdict colors, and carefully chosen editorial typography—while improving legibility, task hierarchy, information density, navigation clarity, and interaction speed.

The redesign must help a principal answer three questions quickly:

1. What requires my attention?
2. What evidence supports the system's recommendation?
3. What action will change the live investment workflow?

## Product principles

### Human action outranks system telemetry

The interface foregrounds decisions that require a person. Ambient system health remains visible but cannot compete with the primary investment task.

### Evidence outranks scores

Model scores are supporting signals. Recommendation rationale, contrary evidence, uncertainty, and decision-changing facts appear before large numeric readouts.

### Plain language outranks private vocabulary

Brand voice remains in editorial copy. Navigation and controls use labels that predict their destination or effect.

### Quiet means restrained, not faint

Hierarchy comes from weight, spacing, grouping, and scale. Meaningful text and boundaries cannot disappear through low opacity.

### Motion communicates state

Content renders immediately. Motion is limited to selection, disclosure, continuity, and completion feedback.

## Global visual system

### Preserved identity

- Oxford and paper remain the primary palette.
- Verdict colors remain reserved for INVEST, MONITOR, and PASS.
- Escalation color remains reserved for human attention and operational issues.
- Square geometry remains the default.
- Playfair remains for the wordmark, Today statement, and major room titles.
- Existing keyboard shortcuts and reduced-motion support remain.

### Typography

- Operational labels have a practical minimum of 12px.
- Body copy and meaningful metadata use 13–14px by default.
- Meaningful text on paper uses at least the contrast produced by Oxford at 60% opacity.
- Meaningful text on Oxford uses at least white at 50% opacity; 60% is preferred for small text.
- Values below these contrast floors are limited to decorative marks and disabled content.
- Uppercase mono is reserved for statuses, timestamps, compact field labels, and short metadata.
- Navigation, descriptions, and multi-word controls use sentence case or compact title case without excessive tracking.

### Borders and surfaces

- Structural rules use sufficient contrast to remain visible on ordinary displays, generally Oxford at 12–16% on paper and white at 12–18% on Oxford.
- Borders group related content; they do not decorate otherwise unrelated content.
- No nested framed panels.
- Background tint, spacing, and rules may separate content, but each section uses one primary grouping method.

### Motion

- Repeated workspace entry choreography is removed.
- Primary content is visible on the first render.
- Standard interaction transitions target 150–200ms.
- Longer transitions are limited to full-screen takeovers or large responsive layout changes and remain below 300ms where possible.
- Width and height are not animated when transform, opacity, or clip can express the same state.
- Reduced-motion mode remains an equivalent, immediate experience.

## Application spine

### Purpose

The lower spine becomes an action center that answers: “Does anything require me right now?” It no longer hosts a miniature dashboard or fund-thesis summary.

### Desktop structure

The spine contains four regions:

1. Identity and current time
2. Primary workspace navigation
3. Human attention action and compact pipeline health
4. Account disclosure

### Attention action

When rulings are required:

- Show the label “Needs your attention.”
- Show the ruling count as the dominant value.
- Use the action label “Review queue.”
- The full region is one accessible control that opens `/v1/flow?queue=escalated`.
- Supporting open/new counts do not appear in the spine.

When no rulings are required:

- Show “Desk clear.”
- Show a secondary open-deal count.
- The region opens `/v1/flow`.
- No success color or celebratory animation is used.

### Pipeline health

- Pipeline status is a compact row below the attention action.
- Live, Idle, Off, and Stopping remain ambient states.
- Issue becomes a direct “Pipeline needs attention” link to Settings.
- Status uses text plus an indicator; color is not the sole signal.

### Mandate removal

Fund name, mandate version, sectors, stages, and geography are removed from the spine. They remain available in Fund and Settings.

### Account disclosure

- Operator name becomes one disclosure trigger.
- The disclosure contains Settings and Log out.
- Scattered underlined fragments and decorative separators are removed.
- The disclosure supports keyboard navigation, Escape, outside-click dismissal, focus restoration, and appropriate ARIA state.

### Navigation labels

The user-facing workspace labels become:

- Today
- Deals
- Portfolio
- Fund strategy
- Search company

Routes remain unchanged. Keyboard shortcuts remain visible in a secondary position.

## Today

### Preserved structure

Today remains a centered command brief and continues to use the editorial product voice.

### Changes

- The desk list becomes an unmistakable interactive region with a stable action label.
- Deals becomes the primary path when attention or open work exists.
- Roman numerals are removed from workspace doors.
- Supporting metadata meets the global contrast and size floors.
- Footer actions reduce to Search, Settings, and Account.
- Date and activity digest remain secondary and do not compete with the main situation statement.
- Entry motion is reduced to a short page-level transition or removed.

### Empty and first-run states

- “The desk is clear” remains the primary no-attention state.
- First-run mandate setup remains a clear blocking action.
- If the pipeline is Off or in Issue, Today provides a direct recovery path without exposing environment-variable terminology.

## Deals workspace

### Layout

Desktop remains a queue plus decision workspace. The queue receives enough width for company, attention reason, and decision state to scan without truncation. The decision workspace prioritizes evidence over model scoring.

Mobile remains queue-first and opens the decision workspace as a sheet or takeover.

### Queue hierarchy

Each row prioritizes:

1. Company name
2. Attention or current-state reason
3. Recommendation or review state
4. Essential sector/stage metadata

Decorative row numbers and redundant score fragments are reduced or removed. Selection remains obvious without relying on a thin side stripe alone.

### Decision brief

The decision workspace begins with:

1. Company identity and current recommendation
2. “Why now” or attention reason
3. Decisive evidence
4. Principal uncertainty or contrary evidence
5. What would change the call
6. Compact model signals: conviction, thesis fit, reviewer agreement, confidence
7. Human ruling controls
8. Full memo and evidence ledger

The conviction score is no longer a hero metric. It appears as one compact signal among other model outputs.

### Ruling controls

- The current human decision state is explicit.
- Ruling actions remain available while evidence scrolls on desktop.
- Mobile exposes the ruling action in a thumb-reachable sticky region within the decision sheet.
- High-risk acknowledgement remains enforced.
- Success feedback states what changed and what happens next.
- If reversal is unsupported, the UI states that constraint before submission.

### Filters

- Priority, Need ruling, New, Stale, and All remain the primary queue views.
- Advanced filters remain progressively disclosed.
- Active filters are summarized and can be cleared in one action.
- Filter controls meet minimum touch-target and contrast requirements.

## Portfolio

### Purpose

Portfolio answers: what the fund believes, where conviction is concentrated, what is deteriorating, and what requires monitoring.

### Desktop composition

- Summary readouts and meaningful exposure changes occupy the opening region.
- Conviction positions form the primary column.
- Watchlist and urgent signals form a dedicated attention column.
- Concentration receives a readable visualization with explicit scale and values.
- Sections grow with content; the page avoids compressing all information into the top third of the viewport.

### Content hierarchy

- Position rows prioritize company, thesis/recommendation state, and relevant movement.
- Watchlist entries explain why an item is being watched and whether it is stale.
- Signals use clear event hierarchy: company, event, time, consequence.
- Empty states explain how content arrives and provide a relevant next action.

## Fund strategy

### Purpose

Fund strategy explains what the system is optimizing for, whether it is following the mandate, and how its behavior is changing.

### Information architecture

The five facets become:

- Strategy
- Decision record
- Patterns
- Calibration
- Agent learning

The routes and existing data contracts remain unchanged unless a later implementation plan identifies a necessary addressability improvement.

### Strategy view

- Fund thesis and mandate constraints remain prominent.
- Alignment, drift, and reviewed counts are secondary diagnostics.
- Version history clearly shows the live version and previous versions.
- Mandate facts use a structured, scannable layout rather than a long editorial document when the content is primarily data.

## Settings

### Mental model

Settings presents one lifecycle:

`Draft changes → Review effects → Publish`

Existing backend saves and publication endpoints may remain separate. The UI must explain their relationship as one coherent workflow.

### Structure

- Section order in the DOM matches visual and keyboard order.
- Major sections may be navigated independently on mobile rather than forming one enormous page.
- A sticky summary identifies unsaved changes.
- Review effects names affected pipeline stages and whether a change requires publication.
- Live version and draft state remain visible without competing with the form.

### Publication

- “Save draft” persists editable configuration without implying that it is live.
- “Review effects” summarizes changes and validation.
- “Publish changes” performs the required publication steps or clearly sequences them.
- Partial failure identifies which operation succeeded, which failed, and how to recover without losing the draft.
- Version history and last publication time are visible after success.

### Validation

- Validation is inline and placed near the source field.
- Cross-field errors also appear in the review summary.
- Disabled publication states explain what must be corrected.

## Search company

The existing full-screen Dispatch experience remains structurally intact but adopts the new navigation label and global legibility rules.

- Progress stages include Identify, Review, Decide, and Memo where applicable.
- Active and background lookups remain recoverable across navigation.
- Errors use user-facing recovery language.
- Developer configuration details never appear in operator-facing errors.

## Responsive behavior

### Desktop

- The spine remains fixed and compact.
- Workspace layouts use available width for evidence, comparison, and exceptions.
- Maximum widths are applied to prose, not to data layouts that benefit from space.

### Tablet and mobile

- Primary navigation remains conventional and label-based.
- The attention action appears in the menu/header without reproducing the full desktop spine.
- Deals is queue-first; decision detail opens as a sheet/takeover.
- Portfolio and Fund stack sections in priority order.
- Settings uses section navigation and preserves draft state between sections.
- All primary touch targets are at least 44px in one dimension where practical and never depend on hover.

## Accessibility

- Meet WCAG AA contrast for all meaningful text and controls.
- Maintain visible focus indicators on both paper and Oxford surfaces.
- Preserve logical heading order and landmarks.
- Ensure visual order matches DOM and keyboard order.
- Interactive readouts expose their action in accessible names.
- Status changes use live regions only when interruption is useful.
- Account disclosure and mobile decision sheets manage focus correctly.
- Meaning is never communicated by color alone.
- Zoom at 200% does not hide actions or create two-dimensional scrolling in primary workflows.

## Error and loading states

- Skeletons match the final content layout for queue, decision brief, Portfolio, Fund, and Settings.
- Empty states state why content is absent and provide the next relevant action.
- Operator-facing errors describe the failed task and recovery action.
- Environment names, CORS terminology, API URLs, stack traces, and backend implementation details remain in logs, not the UI.
- A failed save or publication preserves user input.

## Component boundaries

Implementation should prefer focused components with clear responsibilities:

- `SpineAttentionAction`: attention count, clear state, and queue navigation
- `SpinePipelineStatus`: ambient health or issue recovery link
- `SpineAccountMenu`: operator disclosure, Settings, and Log out
- `DecisionBrief`: evidence-first summary for the selected deal
- `DecisionSignals`: compact model outputs
- `StickyRulingControls`: desktop and mobile ruling affordance
- `PortfolioOverview`: composition and exposure summary
- `PortfolioAttention`: watchlist and signals
- `SettingsChangeSummary`: draft/live differences and affected stages
- `SettingsPublishFlow`: review, validation, publication, and partial-failure recovery

Existing components may be refactored into these boundaries without changing data-fetching ownership unless necessary.

## Data flow

- `AppFrame` continues to own global navigation chrome, Dispatch state, telemetry queries, and spine-level derived state.
- `AppSpine` receives a simplified attention model, pipeline health model, navigation callbacks, and operator actions.
- Deals continues to own selected-startup state and detail fetching.
- Decision brief content is derived from existing startup, review, partner, evidence, and memo data.
- Settings continues to own the draft configuration; a derived change model feeds the summary and publication flow.
- No new direct API calls are introduced outside `src/api/`.

## Testing strategy

### Unit and component tests

- Attention action states: rulings, desk clear, pipeline Issue, pipeline Off
- Account disclosure keyboard behavior and focus restoration
- Navigation labels and route mappings
- Decision brief evidence ordering and missing-data fallbacks
- Ruling controls, acknowledgement gate, success, and failure feedback
- Settings draft/live derivation, validation, publication sequencing, and partial failures
- User-facing error-message mapping

### Accessibility tests

- Keyboard navigation through spine, queue, decision sheet, and Settings publication
- Focus trap and restoration for disclosures and takeovers
- Automated contrast checks for canonical text tokens
- Accessible names for interactive readouts and status controls
- DOM order verification for Settings sections

### Responsive and visual tests

- Today, Deals, Portfolio, Fund strategy, Settings, and Search at mobile, tablet, laptop, and wide desktop viewports
- Long company names, long mandate names, zero items, one item, dense data, and 200% zoom
- Reduced-motion screenshots and interaction checks
- No horizontal overflow in primary routes

### Regression tests

- Existing Clerk auth shell and protected routes
- Dispatch persistence across navigation
- Deep links into Deals
- Fund thesis hard gate and Settings publication behavior
- PDF/memo actions and ruling resolution

## Delivery phases

### Phase 1: Global legibility and chrome

Typography/contrast floors, border hierarchy, navigation language, action-center spine, account disclosure, error copy, and motion baseline.

### Phase 2: Deals decision experience

Queue hierarchy, evidence-first decision brief, compact signals, sticky ruling controls, responsive decision sheet, and decision feedback.

### Phase 3: Today and Portfolio

Clearer primary action, simplified footer, full-canvas Portfolio composition, signal hierarchy, and responsive stacking.

### Phase 4: Fund strategy and Settings

Facet language, structured mandate view, draft/review/publish lifecycle, publication recovery, and mobile section navigation.

### Phase 5: Verification and polish

Full visual regression, accessibility pass, performance verification, copy consistency, edge cases, and final motion polish.

## Acceptance criteria

- The lower spine contains no mandate details or boxed telemetry slab.
- A user can identify the primary human action in the spine within five seconds.
- Meaningful text meets the global size and contrast floors.
- Deals presents decisive evidence and uncertainty before prominent model scores.
- Conviction is a secondary compact signal rather than a hero metric.
- Workspace labels predict their contents without prior product knowledge.
- Settings clearly distinguishes draft, reviewed effects, and live publication.
- Visual and DOM order match in Settings.
- Repeated workspace entry delays are removed.
- Primary mobile actions are touch-accessible and do not depend on hover.
- Operator-facing errors contain no environment-variable or CORS terminology.
- Existing authentication, data fetching, deep links, Dispatch persistence, and pipeline gates continue to work.

## Non-goals

- Replacing the Oxford/paper brand palette
- Migrating React, Tailwind, TanStack Query, Clerk, or Framer Motion
- Changing backend investment logic
- Reworking the route architecture
- Adding new analytics or pipeline capabilities solely to fill visual space
- Introducing decorative effects, rounded-card SaaS patterns, or animation libraries
