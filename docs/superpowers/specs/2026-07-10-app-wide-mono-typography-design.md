# App-Wide Memo-Calibrated Mono Typography

Date: 2026-07-10

## Objective

Make the investment memo's Space Mono styling the shared utility language across the entire Aethria frontend. Match the memo's compact scale, Oxford opacity ladder, controlled tracking, tight line-height, uppercase label treatment, and tabular numeric treatment without changing the roles of Playfair Display or Figtree Variable.

The result should feel like one institution authored every screen. This is a calibration pass, not a conversion of body copy to monospace.

## Approved Direction

Use a **role-calibrated memo system**.

The memo remains the source of truth, translated into five reusable mono roles:

1. **Label** — compact uppercase taxonomy and section identifiers.
2. **Metadata** — dates, secondary context, helper state, and quiet system detail.
3. **Data** — numeric values, scores, counts, ranges, and timestamps where the value is primary.
4. **Status** — verdicts, live/draft state, pipeline state, and compact categorical outcomes.
5. **Action** — navigation controls, text buttons, tabs, filters, and compact commands.

This role mapping prevents the literal 10px memo label treatment from making every operational control too faint while retaining the memo's visual character.

## Typography Tokens

All roles use the existing `--font-mono` / Space Mono stack.

### Mono Label

- Size: `10px`
- Line-height: `1.45`
- Weight: `400`
- Letter-spacing: `0.09em`
- Transform: uppercase
- Default colour: Oxford at `42%`
- Use for: section labels, field labels, table headings, rail headings, small taxonomy, and eyebrows.

### Mono Metadata

- Size: `11px`
- Line-height: `1.5`
- Weight: `400`
- Letter-spacing: `0.04em`
- Transform: none by default
- Default colour: Oxford at `52%`
- Use for: dates, email/user identifiers, supporting counts, descriptions of state, source metadata, and compact helper text.
- Long explanatory hints remain Figtree; metadata is not a replacement for body prose.

### Mono Data

- Size: `13px`
- Line-height: `1.35`
- Weight: `600`
- Letter-spacing: `-0.015em`
- Numeric setting: tabular numerals
- Default colour: Oxford at `82%`
- Use for: counts, scores, percentages, ranges, budget values, and compact KPI values.
- Large KPI values may scale up while retaining the same weight, tracking, and opacity logic.

### Mono Status

- Size: `10px`
- Line-height: `1.4`
- Weight: `600`
- Letter-spacing: `0.075em`
- Transform: uppercase
- Default colour: Oxford at `62%`
- Use for: verdicts, pipeline stages, live/draft, pending/resolved, warnings, and compact badges.
- Existing semantic status colours remain authoritative; this token controls typography, not meaning.

### Mono Action

- Size: `10px`
- Line-height: `1.4`
- Weight: `400` by default, `600` for a selected or primary text action
- Letter-spacing: `0.075em`
- Transform: uppercase
- Default colour: Oxford at `72%`
- Use for: tabs, filters, compact buttons, navigation links, menu actions, and text commands.
- Interactive targets remain at least `36px`, and primary/mobile controls remain at least `44px`, regardless of text size.

## Inverse Treatment

On the Oxford spine, system bar, and other dark surfaces, the five roles keep identical size, line-height, weight, and tracking. Only colour changes:

- Label: paper/white at `56%`
- Metadata: paper/white at `64%`
- Data: paper/white at `88%`
- Status: paper/white at `72%`, unless a semantic status colour applies
- Action: paper/white at `72%`, rising to `94%` for hover, focus, selected, or primary state

## Shared Utilities and Architecture

The implementation should centralize these roles in `app-front-end/src/index.css` and the design-system token modules.

- Recalibrate existing `.type-label-section`, `.type-label-tab`, `.type-meta`, and `.type-data` utilities to the approved roles.
- Add shared `.type-status` and `.type-action` utilities.
- Add inverse modifiers only where a semantic utility avoids repeated Tailwind strings.
- Update `design-system/ui-text.ts`, `railEditorial.ts`, `productSystem.tsx`, `verdictBadgeTokens.ts`, `tokens.ts`, and Clerk appearance values to reference the same decisions.
- Prefer shared role classes over new one-off combinations of `font-mono`, arbitrary font size, tracking, opacity, transform, and line-height.
- Keep semantic colour classes local to the component when state meaning requires them.

## Surface-by-Surface Application

### Application Shell

Apply the role system to `AppSpine`, `SystemBar`, `MobileHeader`, `RoomHeader`, account controls, global navigation, timestamps, pipeline status, and system counts.

- Navigation and compact commands use Mono Action.
- Rail and section headings use Mono Label.
- Identity/time detail uses Mono Metadata.
- Counts use Mono Data.
- Pipeline and connection state use Mono Status.

### Home and Flow

Apply the roles to Home page system state, queue navigation, decision queue headings, filters, dispatch controls, selected-deal metadata, and action links.

- Company names and explanatory copy remain Figtree or Playfair according to their existing role.
- Queue metadata becomes quieter and more consistent with the memo.
- Verdict typography uses Mono Status with existing semantic colour tokens.

### Portfolio and Fund

Apply Mono Label to table/column headings and section taxonomy, Mono Metadata to sector/stage/context detail, Mono Data to scores and counts, and Mono Action to navigation and controls.

- Portfolio company identity remains Figtree.
- Fund editorial headings remain Playfair.
- Numeric hierarchy should match memo conviction/score support rather than becoming oversized dashboard typography.

### Settings

Settings contains the largest concentration of fragmented mono strings and is the main consolidation target.

- Section navigation, tabs, field labels, input suffixes, draft/live state, score ranges, totals, and action controls map to the five roles.
- Explanatory field hints and policy descriptions remain Figtree body text where they exceed compact metadata length.
- Numeric inputs use Mono Data but retain normal form-control accessibility and alignment.

### System Intelligence and Dispatch

Apply Mono Label to feed headings and signal taxonomy, Mono Metadata to time/source context, Mono Status to running/complete/error state, Mono Data to counts, and Mono Action to retry/open/dismiss commands.

- Signal descriptions and intelligence narratives remain Figtree.
- Error explanations remain readable body text; only the error category/status uses mono.

### Authentication and Admin

Apply the same utilities to login, Clerk appearance, institutional footer, admin login, and admin dashboard.

- Form labels use Mono Label.
- Form actions use Mono Action.
- Authentication/admin state uses Mono Status.
- User IDs, timestamps, and compact support context use Mono Metadata.
- Admin table values use Mono Data only when numeric; user-facing names remain Figtree.

### Memo

The memo is the reference implementation and should not be globally restyled by broad selectors. Its local tokens remain intact. Shared utilities may converge with the same numeric values, but memo-specific selectors continue to own memo layout and component exceptions.

## Migration Rules

Replace fragmented combinations when they represent one of the five roles. Examples include one-off strings containing:

- `font-mono text-[9.5px|10px|11px|12px|15px]`
- `tracking-[0.04em|0.06em|0.08em|0.10em|0.12em|0.14em|0.18em|0.2em]`
- repeated `uppercase` and opacity combinations
- page-specific tabular number styling

Do not mechanically replace:

- brand/wordmark typography;
- Playfair editorial headlines;
- Figtree body and explanatory copy;
- code, raw identifiers, or debugging output whose monospace use is semantic rather than part of the UI role system;
- large numeric displays that intentionally scale beyond the base Mono Data size, though their weight/tracking/opacity should align.

## Accessibility and Responsive Behaviour

- Mono labels must not carry essential meaning through low contrast alone.
- Interactive controls retain visible keyboard focus and adequate hit targets.
- The 10px label/status size is reserved for short text; long text moves to Mono Metadata or Figtree body copy.
- No control should truncate an essential status solely because the standard role has tighter tracking.
- On small screens, maintain role sizes unless a component already requires a larger touch/control treatment; do not shrink below the approved base sizes.
- Tabular numerals remain enabled for changing and aligned numeric data to avoid width jitter.

## Verification

### Automated

- Add token/utility regression tests covering the five exact role definitions.
- Update component tests only where shared class contracts intentionally change.
- Run the full frontend test suite, lint, and production build.
- Search for remaining arbitrary mono combinations and classify each as intentional or migrate it.

### Visual

Verify every major route and shared shell at desktop and mobile widths:

- Home
- Flow / decision queue
- Open investment memo
- Portfolio
- Fund
- Settings
- System intelligence and dispatch states
- Login and Clerk surfaces
- Admin login and dashboard

Review normal, selected, hover, focus, disabled, loading, error, and inverse states. Success means the app's compact utility typography visibly matches the memo while body copy and display hierarchy remain unchanged.

## Out of Scope

- Changing the three font families.
- Changing the memo's document layout or section hierarchy.
- Converting body copy or company names to Space Mono.
- Redesigning colour semantics, page layout, component geometry, or animation.
- Changing backend behavior, data, or API contracts.
- Restyling the generated IC pack PDF.
