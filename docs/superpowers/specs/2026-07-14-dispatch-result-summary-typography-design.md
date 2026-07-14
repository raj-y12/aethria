# Dispatch Result Summary Typography

## Goal

Reduce the visual weight and vertical footprint of the dispatch result card shown after a company lookup, while preserving its existing editorial hierarchy.

## Context

The dispatch takeover renders `LookupResultSnapshot` with `size="lg"`. In that variant, the result summary is currently styled as an 18–23px responsive serif standfirst with a 1.45 line-height. Long investment summaries therefore dominate the card and push supporting scores and actions down the viewport.

## Considered approaches

1. **Balanced serif reduction (selected):** retain the display serif but reduce the responsive range to 16–18px and set a 1.4 line-height. This preserves the product's editorial character while making long summaries materially more compact.
2. **Convert the summary to UI sans:** use a 15–16px sans-serif body style. This would maximize density, but would flatten the hierarchy and make the central investment finding feel like ordinary supporting copy.
3. **Shrink the whole card:** reduce the company name, summary, scores, and padding together. This would save more space, but would weaken useful hierarchy and change more than the reported problem requires.

## Design

Only the large, non-memo snapshot summary typography changes. The summary remains serif and responsive, with a 16px minimum and an 18px maximum. Its line-height becomes 1.4. Company name, metadata, verdict, score labels, score values, card padding, memo variant, default snapshot variant, and compact variant remain unchanged.

The change is implemented in the shared `LookupResultSnapshot` component because the large dispatch variant owns the oversized style. Scoping through the existing `lg` condition prevents the marketing memo and smaller snapshot uses from changing.

## Responsive and accessibility behavior

The summary remains fluid across viewport sizes and retains the existing color contrast and semantic paragraph markup. No content is truncated, clamped, or hidden.

## Verification

- Run the product-chrome and frontend type/test checks that cover the component.
- Confirm the large snapshot still uses the display font and the new bounded font-size range.
- Confirm default, compact, and memo variants retain their existing classes.
- Visually inspect the dispatch result at desktop width, focusing on summary density and retained hierarchy.

## Out of scope

- Rewriting or truncating generated investment summaries.
- Changing the dispatch takeover title.
- Resizing the company name, scores, labels, button, or card container.
- Altering memo typography.
