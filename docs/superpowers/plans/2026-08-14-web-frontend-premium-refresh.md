# Aethria web frontend premium refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the public Aethria web frontend so it feels like a high-quality, forward-looking intelligence company while preserving the strongest parts of the existing Gallery of Instruments direction and all current public behavior.

**Architecture:** Keep React, Vite, vite-react-ssg, Framer Motion, Lenis, and the existing route structure. Refactor the shared marketing shell and compose HomePage and TeamPage from distinct visual scenes instead of repeating plate-shaped sections. Use existing product primitives and static content to create product evidence without adding backend APIs, remote product embeds, or new dependencies.

**Tech Stack:** React 18, TypeScript, Vite, vite-react-ssg, vanilla CSS with existing design tokens, Framer Motion, Lenis, existing Fontsource packages.

**Spec:** `docs/superpowers/specs/2026-08-14-web-frontend-premium-refresh-design.md`

## Global Constraints

- Preserve the existing public routes: `/`, `/home`, `/request-access`, and `/team`.
- Preserve access modal/form behavior, route metadata, reduced-motion support, and SSG output.
- Instrument Sans is the default voice; Space Mono is for labels and technical metadata; Playfair Display is reserved for rare thesis moments.
- Use the existing grey stock, oxford navy, verdigris, and restrained heritage-gold palette.
- Do not add a dependency, backend endpoint, remote product embed, or new animation library.
- Do not invent customer logos, metrics, awards, or unsupported company claims.
- Keep `fetch` and product data boundaries unchanged; this is a public marketing composition task.
- No commits, branches, pushes, or unrelated cleanup; preserve the existing dirty worktree.

### Task 1: Establish the refresh regression contract

**Files:**
- Modify: `web-front-end/scripts/check-marketing.mjs`
- Modify: `web-front-end/src/index.css`
- Test: existing `web-front-end/scripts/check-marketing.mjs`, `check-contrast.mjs`, and `check-bundle.mjs`

**Interfaces:**
- Produces stable marketing markers for the new home and team structures.
- Produces named CSS surface modes that later page compositions consume: `stock-editorial`, `oxford-intelligence`, `product-evidence`, `image-led`, and `quiet-transition`.

- [x] **Step 1: Add failing marketing assertions before page implementation**

Add checks for these exact prerendered markers:

```js
['Aethria', 'Fund thesis', 'Evidence trail', 'Human decision'].every((marker) => html.includes(marker))
['Aethria keeps venture judgment on the record.', 'Decision record', 'Show the source'].every((marker) =>
  teamHtml.includes(marker)
)
```

Also assert that the home HTML no longer contains the old repeated plate labels used as the primary page structure, while retaining the real product labels `Market`, `Product`, `Technical`, `Execution`, and `Defensibility`.

- [x] **Step 2: Run the guard and verify it fails against the current composition**

Run:

```bash
cd web-front-end && npm run check:marketing
```

Expected: FAIL because the new scene markers are not yet present.

- [x] **Step 3: Add the shared surface-mode token layer**

Add CSS classes in `web-front-end/src/index.css` using existing variables only:

```css
.surface-stock-editorial { background: var(--surface-base); color: var(--text-primary); }
.surface-oxford-intelligence { background: var(--surface-strong); color: var(--text-inverse); }
.surface-product-evidence { background: var(--stock-2); color: var(--text-primary); }
.surface-image-led { background: var(--color-oxford); color: var(--text-inverse); }
.surface-quiet-transition { background: var(--surface-base); color: var(--text-primary); }
```

Use these as composition hooks, not as a second token system.

- [x] **Step 4: Run contrast and lint checks for the token layer**

Run:

```bash
cd web-front-end && npm run lint && npm run check:contrast
```

Expected: both pass.

### Task 2: Refine the shared marketing shell

**Files:**
- Modify: `web-front-end/src/components/GalleryFrame.tsx`
- Modify: `web-front-end/src/components/AnimatedRoutes.tsx`
- Modify: `web-front-end/src/index.css`
- Test: `web-front-end/scripts/check-marketing.mjs`

**Interfaces:**
- `GalleryFrame` continues to accept `active`, `enter`, and `onAccess`.
- `AnimatedRoutes` continues to own public route selection and page transitions.

- [x] **Step 1: Audit current frame behavior before changing it**

Confirm `GalleryFrame` still owns the wordmark, current route state, Dublin clock, edition label, and access action. Confirm `AnimatedRoutes` still wraps public pages in the existing `AnimatePresence` transition.

- [x] **Step 2: Add a shell state class for content-heavy pages**

Extend `GalleryFrame` with an optional `quiet?: boolean` prop, defaulting to `false`. When `quiet` is true, add `frame-quiet` to the root shell class while retaining all existing link behavior and `aria-current` semantics.

- [x] **Step 3: Implement the quiet shell treatment**

Add CSS so `.frame-quiet .frame` lowers visual emphasis on content-heavy scenes without hiding navigation or reducing contrast. Use opacity, color, and transition changes only; do not animate layout properties.

- [x] **Step 4: Use the quiet shell on TeamPage only**

Pass `quiet` from `TeamPage` while leaving HomePage’s arrival frame unchanged. Do not change the private route behavior.

- [x] **Step 5: Verify navigation and static output**

Run:

```bash
cd web-front-end && npm run build && npm run check:marketing
```

Expected: build succeeds, active navigation remains present, and the route-specific team HTML is emitted.

### Task 3: Recompose the HomePage around product evidence

**Files:**
- Modify: `web-front-end/src/HomePage.tsx`
- Modify: `web-front-end/src/components/HeroPlate.tsx`
- Modify: `web-front-end/src/components/plates/RecordPlate.tsx`
- Modify: `web-front-end/src/components/plates/ReviewPlate.tsx`
- Modify: `web-front-end/src/components/plates/MarketPlate.tsx`
- Modify: `web-front-end/src/components/plates/NewsroomPlate.tsx`
- Modify: `web-front-end/src/components/plates/CorrectionsPlate.tsx`
- Modify: `web-front-end/src/components/plates/QueryPlate.tsx`
- Modify: `web-front-end/src/components/plates/HoldingsPlate.tsx`
- Modify: `web-front-end/src/components/plates/AccessPlate.tsx`
- Modify: `web-front-end/src/index.css`
- Test: `web-front-end/scripts/check-marketing.mjs`

**Interfaces:**
- Plate components retain their current props and remain independently renderable.
- Existing market, review, record, newsroom, correction, query, holdings, and access content remains available.

- [x] **Step 1: Mark the current home scene boundaries**

Identify the current hero and eight plate mounts in `HomePage.tsx`. Preserve their content and action handlers while removing the assumption that every section must use the same visual height, padding, or centered alignment.

- [x] **Step 2: Update the hero to use a technical thesis and product evidence**

Keep the first viewport’s existing product claim, but add a compact evidence rail with these exact labels:

```text
FUND THESIS
EVIDENCE TRAIL
HUMAN DECISION
```

The rail must be semantic HTML, visible without hover, and rendered with Instrument Sans plus Space Mono labels. Playfair may appear only in the primary thesis statement if the composition needs it.

- [x] **Step 3: Give the record and review scenes distinct jobs**

Make the record scene the oxford “institutional memory” chapter. Make the review scene the product-evidence chapter with visible source/reviewer relationships. Avoid matching card borders and identical three-column layouts.

- [x] **Step 4: Recompose market and newsroom scenes as image/data-led chapters**

Let the map become the visual anchor of the market scene. Let newsroom content use an asymmetric list with one lead story and supporting entries. Keep existing content and links; change only composition and visual hierarchy.

- [x] **Step 5: Make the final access scene quieter and more credible**

Retain the existing access form and validation behavior. Remove redundant decorative framing around the action and ensure the final CTA is the strongest action in the final viewport.

- [x] **Step 6: Add responsive and reduced-motion styles**

At widths below `820px`, collapse scenes into a single readable column. At widths below `560px`, keep all product evidence readable without horizontal overflow. Reuse existing reduced-motion selectors and do not introduce always-on animation.

- [x] **Step 7: Build and inspect home markers**

Run:

```bash
cd web-front-end && npm run build && npm run check:marketing && npm run check:contrast
```

Expected: all pass and `dist/home.html` contains the evidence-rail markers.

### Task 4: Recompose the TeamPage as an institutional company profile

**Files:**
- Modify: `web-front-end/src/TeamPage.tsx`
- Modify: `web-front-end/src/index.css`
- Use: `web-front-end/public/raj-yendamuri.jpg`
- Test: `web-front-end/scripts/check-marketing.mjs`

**Interfaces:**
- Preserve `AccessModal`, founder links, route metadata synchronization, and the existing image asset path.
- Preserve the approved copy flow: thesis, founder/origin, decision record, working principles, invitation.

- [x] **Step 1: Add the failing team assertions**

Assert these exact markers in `dist/team.html`:

```js
['Aethria keeps venture judgment on the record.', 'Decision record', 'Show the source'].every((marker) =>
  teamHtml.includes(marker)
)
```

Also assert that `teamHtml` includes `/raj-yendamuri.jpg` and does not include the placeholder class `team-photo-placeholder`.

- [x] **Step 2: Build the institutional hero**

Use the founder image as a large image-led scene with restrained oxford framing. Keep the circular crop only if it supports the composition; otherwise use a larger editorial crop with the circle as a secondary identity marker. Do not use a generic avatar-card layout.

- [x] **Step 3: Make the decision record feel like a product specimen**

Keep the `FUND THESIS → EVIDENCE → HUMAN DECISION` relationship, but place it in a real-looking record surface with metadata, source lines, and a restrained status treatment. Do not invent metrics or customer proof.

- [x] **Step 4: Make the principles a typographic sequence, not equal cards**

Use a staggered or offset composition for `Show the source`, `Keep the person in charge`, and `Make every decision useful later`. Preserve plain language and body copy.

- [x] **Step 5: Keep one closing invitation**

Use one primary `Start a conversation` CTA at the end. Keep LinkedIn and GitHub as secondary verification links near the founder identity.

- [x] **Step 6: Verify team output and metadata**

Run:

```bash
cd web-front-end && npm run build && npm run check:marketing && npm run check:contrast
```

Expected: team HTML includes the real image path, route-specific title/description/canonical, and all approved content markers.

### Task 5: Reduce decorative repetition and finalize polish

**Files:**
- Modify: `web-front-end/src/index.css`
- Modify: `web-front-end/src/components/GalleryLoader.tsx` only if the final arrival sequence duplicates the refreshed shell
- Modify: `web-front-end/src/components/AnimatedRoutes.tsx` only if the final page transition duplicates the arrival sequence

**Interfaces:**
- Preserve all existing motion callbacks and session-storage behavior.
- Preserve `prefers-reduced-motion` behavior and public route transitions.

- [x] **Step 1: Search for repeated slide-deck treatments**

Review selectors for identical `min-height`, identical centered layouts, repeated border-card wrappers, and Playfair usage. Remove only repetition introduced by the marketing refresh; do not refactor unrelated authenticated-app styles.

- [x] **Step 2: Apply the typography calibration**

Search `web-front-end/src` for `font-display` usage. Keep Playfair in hero thesis/pull-quote contexts only; use `font-sans` for navigation, section headings, buttons, and most body content.

- [x] **Step 3: Add final focus, hover, and pressed states**

Ensure primary links and buttons have visible `:focus-visible`, hover, and `:active` treatment. Use transforms and opacity rather than layout animation.

- [x] **Step 4: Run the full web verification gate**

Run:

```bash
cd web-front-end
npm run lint
npm run build
npm run check:bundle
npm run check:marketing
npm run check:contrast
npm run check:waitlist
git diff --check
```

Expected: every command exits successfully. A Vite advisory about the existing approximately 500 KB client chunk may remain, but `check:bundle` must pass.

## Final review checklist

- [x] First viewport reads as technology/intelligence company, not a presentation cover.
- [x] Slide-deck strengths remain visible through pacing, labels, and evidence framing.
- [x] Playfair is selective and no longer carries the entire visual identity.
- [x] Home has distinct scenes for thesis, product evidence, market intelligence, institutional memory, research, and access.
- [x] Team has a real founder image, company credibility, decision-record artifact, principles, and one closing invitation.
- [x] No unsupported proof, metrics, logos, or remote product embed was introduced.
- [x] Mobile, keyboard focus, and reduced-motion behavior remain intentional.
