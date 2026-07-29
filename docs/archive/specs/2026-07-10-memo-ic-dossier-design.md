# Investment Memo — Modern IC Dossier Design

## Objective

Redesign the investment memo as a modern investment-committee dossier. The result should feel editorial and authoritative without imitating a vintage newspaper. It must use Aethria's existing typography, fit the real embedded memo column, preserve the current content order, and make the committee decision easier to form and record.

## Approved direction

The approved visual direction is the adapted IC dossier shown in the brainstorming companion.

Its newspaper influence comes from:

- a strong recommendation lede;
- compact issue and mandate metadata;
- numbered document sections;
- restrained editorial pacing;
- a concise decision record beside the opening judgment;
- dense, legible rows for evidence and scores.

It must not rely on decorative double rules, repeated boxed cards, ornamental mastheads, faux-print typography, or continuous broadsheet columns.

## Constraints

- Preserve the current content sequence:
  1. Recommendation
  2. Snapshot
  3. Why Now
  4. What Limits Conviction
  5. Assessment
  6. Risks
  7. Ruling
  8. Appendix
- Preserve existing conditional rendering and data sources.
- Preserve existing memo interactions, including disclosures, risk acknowledgement, ruling choices, rationale, submit behavior, PDF download, add-context, and close actions.
- Preserve the house fonts already defined by the memo tokens:
  - Figtree Variable for UI and body copy;
  - Space Mono for labels, metadata, and numeric readouts;
  - Playfair Display only where it already serves a deliberate display role; do not expand its use.
- Support both the embedded workspace memo and the wider standalone/modal view.
- Treat `44rem` as the primary embedded reading measure. Do not design the document around a wide desktop canvas that the product does not provide.
- Preserve responsive behavior and readable single-column flow on narrow containers.

## Layout architecture

### 1. Memo chrome and company identity

Keep the existing masthead actions, but simplify the visual framing. The action bar remains product UI rather than newspaper decoration. Company identity, stage, geography, and memo metadata should read as a compact dossier header with generous space below it.

### 2. Recommendation opening

The opening becomes the document's strongest hierarchy:

- recommendation label;
- large plain-language verdict;
- standfirst explaining the recommendation;
- “What decides it” question;
- compact decision record containing conviction, reviewer alignment, mandate fit, blocker, and next move when those values are available.

At the embedded width, the opening may use a restrained two-column grid only while both columns remain useful. Below the container breakpoint it collapses to one column. The decision record uses one subtle vertical separator at most.

When `coverOverride` supplies the Flow decision stage, preserve that ownership. The redesigned document body must integrate with the override rather than duplicate its identity or ruling controls.

### 3. Sequential dossier sections

Major sections remain vertically ordered and full-width. The redesign must not place separate major sections side by side merely to simulate a newspaper.

Each major section uses:

- a small mono sequence number;
- a concise section title;
- consistent top spacing;
- little or no top border;
- content-specific internal layout.

Only introduce separators where they clarify repeated data rows. Avoid a horizontal rule above every section.

### 4. Content-specific treatments

- **Snapshot:** compact definition rows with stable label and value columns; collapse to stacked rows at narrow widths.
- **Why Now:** an ordered investment case. The first point may receive stronger typographic emphasis, with subsequent points remaining concise and scannable.
- **What Limits Conviction:** ranked objections with severity and statement, presented as a short adverse-case register rather than decorative cards.
- **Assessment:** compact score strip when space permits, followed by reviewer consensus, path-to-nine, operating readouts, and thesis alignment in the existing order. Dense score data may use columns; long reasoning does not.
- **Risks:** aligned severity, claim, and evidence/meta columns. Use light row separators only between entries.
- **Ruling:** retain the existing functional ruling component. Give it stronger contrast and a clear terminal position in the main memo, without making it visually detached from the document.
- **Appendix:** preserve the disclosure sequence and collapsed behavior. Present it as a quiet document index with restrained separators and metadata aligned to the opposite edge.

## Visual system

- Use the existing Oxford/navy ink, warm paper surface, and coral action accent.
- Let spacing, weight, and alignment create hierarchy.
- Reserve coral for the recommendation/action emphasis, numbered wayfinding, exceptions, and high-severity signals.
- Remove redundant borders and doubled hairlines.
- Avoid rounded card stacks inside the memo. Small radii are acceptable only for true controls or an intentional contained action surface.
- Keep body text left-aligned with a readable measure; do not justify prose or enable hyphenation.
- Keep numeric information in the mono role and narrative information in the UI/body role.

## Responsive behavior

- Primary target: embedded memo at approximately `44rem` maximum content width.
- Wider modal: allow additional breathing room, but do not radically rearrange the reading order.
- At approximately `620px` container width, collapse the opening grid and any label/value structures that would squeeze narrative copy.
- At approximately `440px`, ruling choices stack when needed and all metadata may wrap naturally.
- Do not use CSS multi-column flow for interactive or structured content.

## Motion and interaction

- Preserve the existing single document fade and reduced-motion handling.
- Do not add per-section entrance animation.
- Disclosure and ruling interactions retain their existing behavior and accessibility semantics.
- Hover and focus states should remain quiet, fast, and clearly visible.

## Accessibility

- Preserve the article, region, section, heading, disclosure, list, and form semantics already present.
- Maintain visible focus states and keyboard operation for all actions and disclosures.
- Do not communicate recommendation, severity, or selected ruling by color alone.
- Maintain sufficient contrast on the warm paper and navy ruling surfaces.

## Implementation boundaries

The first implementation pass should primarily reshape existing memo CSS and make only the smallest JSX changes required for grouping, section numbering, and the recommendation decision record. It should not change backend data contracts, memo generation, recommendation logic, or content ordering.

The current uncommitted changes in `InvestmentMemoContent.css`, `DocketCaseRow.tsx`, and `density.ts` are user work and must be preserved. Any overlap with the memo stylesheet must be reviewed deliberately rather than overwritten.

## Verification

- Run the frontend type check and production build.
- Exercise the memo with complete, partial, pending, failed, and already-decided data states.
- Check embedded, standalone/modal, tablet, and mobile widths.
- Verify ruling selection, risk acknowledgement, rationale entry, submission, disclosures, PDF download, add-context, and close actions.
- Compare the rendered memo against the approved adapted IC dossier for hierarchy, density, content order, and restraint.
