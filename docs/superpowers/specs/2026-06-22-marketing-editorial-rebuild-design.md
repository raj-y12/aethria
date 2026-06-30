# Marketing homepage — editorial rebuild ("C with a hint of A")

**Date:** 2026-06-22
**Surface:** `web-front-end` (public marketing site, route `/home`)
**Goal:** The current marketing page describes the product in elegant-but-vague language, zebra-stripes between paper and dark-oxford bands, and is structured like tasteful SaaS sections. Rebuild it into a stark, confident editorial page in the spirit of Seedcamp Fund VII — rendered in Aethria's own paper/oxford palette, not Seedcamp's dark theme.

## Problem (user-confirmed)

Three things are wrong with the page today:
1. **Copy is too vague** — "made inspectable", "judgment with memory" read well but a cold visitor doesn't learn what the product *does*.
2. **Structure feels generic** — alternating text+card sections + a 4-column pipeline grid read as standard SaaS, not an editorial index.
3. **Visually inconsistent** — two dark-oxford bands (Mandate, ReviewDisagreement) break an otherwise continuous warm-paper scroll.

User is satisfied with the current level of product-UI showcase (keep the demo components), and wants to **keep** the headline "Private market judgment, made inspectable." with a concrete sub-line under it.

## Direction

One continuous warm-paper canvas, top to bottom. Sections divided **only** by edge-to-edge 1px hairlines (`--section-divider`) — no background-colour changes anywhere. Giant editorial serif statements; mechanical mono for labels/numerals/stamps. No rounded corners (already enforced globally). Keep working `@aethria/product-chrome` demo components and existing motion/`ScrollReveal` patterns.

## Section-by-section

1. **Hero** — keep `SiteHeader`. Mono "ledger build-stamp" eyebrow (e.g. `[ FUND INTELLIGENCE · V2 · BY INVITATION ]`) replacing the plain eyebrow. Headline stays `Private market judgment, made inspectable.` Add **one concrete sub-line** stating plainly what it does ("Aethria sources real startups against your fund thesis, runs three independent reviews on each, and records an invest / pass / monitor decision — with the evidence trail attached."). Keep `Request access` CTA + `MarketTape`.

2. **The index (replaces `PipelineSection` grid)** — convert the 4-column phase grid into a full-width **vertical index**: four stacked rows, each an edge-to-edge 1px hairline row with deep padding, a massive asymmetric mono numeral (`01`–`04`) anchoring the left, stage name in mono caps, and one blunt sentence. Keep the `System composition` metrics (4 / 3 / 6 / 1) and `IntelligenceMap` below it, but on continuous paper. Reuse `.record-index-row` hairline class already in `index.css`.

3. **Full-bleed product slice — "what one decision looks like"** — keep `DashboardPreview` (already a full-bleed-ish slice with the oxford spine strip); leave structure, tighten copy to be concrete about the record.

4. **Reviewer disagreement** — keep the content and proof, but **convert from dark oxford to paper** (`ReviewDisagreement.tsx`): paper background, oxford ink, hairline-divided cards instead of inverse-on-dark. This removes the second zebra band.

5. **On-demand lookup** — keep; convert any inverse styling; add a borderless `LookupCommandBar` query line echoing the real product. Paper.

6. **Mandate** — convert `#mandate` section from dark oxford band to paper; swap `DEMO_MANDATE_DARK` → `DEMO_MANDATE_PAPER`; fold into flow as a short concrete beat ("It only looks for what you tell it to.").

7. **Closing CTA + `NewsletterBand` + footer** — keep; tighten copy.

## Copy principle

Every section opener earns its place by saying something concrete a VC cares about (what runs, what's recorded, what's preserved) before any editorial flourish. Mono stamps and numerals carry the "technical luxury" texture; the serif carries the confidence.

## Out of scope

- No palette/token changes, no new fonts, no rounded corners (already 0).
- No backend, auth, or routing changes.
- Not rebuilding the product-chrome demo components — reuse as-is.

## Verification

User runs `web-front-end` locally (`npm run dev`) and reviews. We additionally typecheck/build to confirm no TS or import regressions before handing off.
